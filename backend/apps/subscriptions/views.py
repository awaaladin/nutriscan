from django.conf import settings
from django.db import IntegrityError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scans.models import Scan

from .models import Subscription
from .play_client import PlayNotConfigured, PlayVerificationError, get_verifier
from .serializers import SubscriptionSerializer, VerifyPurchaseSerializer
from .services import apply_play_state, refresh_pro_status


class VerifySubscriptionView(APIView):
    """Grants Pro only after Google Play confirms the purchase token.

    The client sends a token from Play Billing; this looks it up with the
    Play Developer API, derives the plan from the product Google reports,
    acknowledges the purchase, and records the real expiry. A token can belong
    to only one account, so a token copied from another user's device can't be
    replayed here."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = VerifyPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["purchase_token"]

        if Subscription.objects.filter(play_purchase_token=token).exclude(user=request.user).exists():
            return Response(
                {"detail": "This purchase is already linked to another account."},
                status=status.HTTP_409_CONFLICT,
            )

        verifier = get_verifier()
        try:
            play = verifier.get_subscription(token)
        except PlayNotConfigured:
            return Response(
                {"detail": "Subscriptions aren't available right now. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except PlayVerificationError:
            return Response({"detail": "We couldn't verify that purchase."}, status=status.HTTP_400_BAD_REQUEST)

        plan = settings.PLAY_PRODUCT_PLANS.get(play.product_id)
        if plan is None:
            return Response({"detail": "Unrecognised subscription product."}, status=status.HTTP_400_BAD_REQUEST)

        if not play.acknowledged:
            try:
                verifier.acknowledge(play.product_id, token)
            except PlayVerificationError:
                return Response(
                    {"detail": "We couldn't confirm that purchase with Google yet. Please try again."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        try:
            subscription, _ = Subscription.objects.update_or_create(
                user=request.user,
                defaults={"plan": plan, "play_purchase_token": token, "play_product_id": play.product_id},
            )
        except IntegrityError:
            return Response(
                {"detail": "This purchase is already linked to another account."},
                status=status.HTTP_409_CONFLICT,
            )
        apply_play_state(subscription, play, request.user)
        if not request.user.is_pro:
            return Response(
                {"detail": "That subscription isn't active.", **SubscriptionSerializer(subscription).data},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        return Response(SubscriptionSerializer(subscription).data)


class ProInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        refresh_pro_status(request.user)
        if not request.user.is_pro:
            return Response({"detail": "Pro subscription required."}, status=403)

        recent_scans = list(
            Scan.objects.filter(user=request.user).select_related("product").order_by("-scanned_at")[:30]
        )

        flag_counts = {}
        avoid_products = []
        for scan in recent_scans:
            for flag in scan.flags:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
            if scan.diabetic_risk == "Avoid" and request.user.is_diabetic:
                avoid_products.append({"barcode": scan.product.barcode, "name": scan.product.name})

        patterns = [
            f"{count} of your last {len(recent_scans)} scans were flagged for {flag.replace('_', ' ')}"
            for flag, count in sorted(flag_counts.items(), key=lambda kv: -kv[1])
            if count >= 3
        ]

        return Response({"avoid_list": avoid_products, "patterns": patterns})

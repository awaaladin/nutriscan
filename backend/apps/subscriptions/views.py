from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scans.models import Scan

from .models import Subscription
from .serializers import SubscriptionSerializer, VerifyPurchaseSerializer


class VerifySubscriptionView(APIView):
    """
    TODO: this is a stub. Before launch, replace the trust-the-client logic
    below with a real call to the Google Play Developer API
    (purchases.subscriptions.get) to verify purchase_token server-side, and
    wire up Real-Time Developer Notifications for renewals/cancellations
    instead of trusting a single client-reported verify call.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = VerifyPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        duration = timedelta(days=365 if data["plan"] == Subscription.Plan.YEARLY else 30)
        subscription, _ = Subscription.objects.update_or_create(
            user=request.user,
            defaults={
                "plan": data["plan"],
                "status": Subscription.Status.ACTIVE,
                "play_purchase_token": data["purchase_token"],
                "play_product_id": data["product_id"],
                "expires_at": timezone.now() + duration,
            },
        )
        request.user.is_pro = True
        request.user.save(update_fields=["is_pro"])
        return Response(SubscriptionSerializer(subscription).data)


class ProInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
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

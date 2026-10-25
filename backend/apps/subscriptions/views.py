import json
import logging

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import escape
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scans.models import Scan

from . import credits, paystack
from .models import PaystackPayment, Subscription
from .play_client import PlayNotConfigured, PlayVerificationError, get_verifier
from .serializers import PaystackCheckoutSerializer, SubscriptionSerializer, VerifyPurchaseSerializer
from .services import apply_paystack_transaction, apply_play_state, refresh_pro_status

log = logging.getLogger(__name__)


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


def _verify_with_paystack(payment):
    if payment.status != PaystackPayment.Status.PENDING:
        return payment
    try:
        data = paystack.verify_transaction(payment.reference)
    except paystack.PaystackError as exc:
        log.warning("Paystack verify failed for %s: %s", payment.reference, exc)
        return payment
    return apply_paystack_transaction(payment.reference, data) or payment


# What each plan includes, shown on the plans screen. Each tier includes everything below it.
TIER_FEATURES = {
    "pro": [
        "Research mode: answers from trusted health sources, with links",
        "Your personal avoid-list and scan patterns",
        "Weight tracker with BMI and goal progress",
    ],
    "plus": [
        "Everything in Pro",
        "Blood pressure tracker with targets",
        "7-day Nigerian meal plans built around your goal and budget",
        "Weekly AI progress report from your readings and scans",
    ],
    "care": [
        "Everything in Pro Plus",
        "Blood sugar tracker: fasting and after-meal targets, trends",
        "Meal plans and reports tuned to your glucose readings",
        "Doctor-visit summary you can share",
    ],
}


def _price_ngn(tier: str, plan: str) -> int:
    monthly = settings.PRO_TIERS[tier]["monthly_ngn"]
    return monthly if plan == Subscription.Plan.MONTHLY else monthly * settings.YEARLY_MONTHS_CHARGED


class PaystackPlansView(APIView):
    """Plans, prices and credits for the web checkout, so the app shows what Paystack will charge."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tiers = [
            {
                "tier": tier,
                "label": info["label"],
                "monthly_ngn": info["monthly_ngn"],
                "yearly_ngn": _price_ngn(tier, Subscription.Plan.YEARLY),
                "monthly_credits": info["monthly_credits"],
                "features": TIER_FEATURES[tier],
            }
            for tier, info in settings.PRO_TIERS.items()
        ]
        return Response({
            "tiers": tiers,
            "free_monthly_credits": settings.FREE_MONTHLY_CREDITS,
            "topup": settings.CREDIT_TOPUP,
            "credit_costs": settings.AI_CREDIT_COSTS,
            "balance": credits.balance(request.user),
        })


class CreditsView(APIView):
    """GET /api/credits/ -- what the user has left this month."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(credits.balance(request.user))


class PaystackCheckoutView(APIView):
    """Starts a Paystack checkout for one prepaid plan period or a credit top-up. The app opens
    authorization_url in the browser; Paystack sends the payer back to PaystackReturnView."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaystackCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not request.user.email:
            email = data.get("email")
            if not email:
                return Response(
                    {"detail": "Enter your email address for the payment receipt.", "reason": "email_required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request.user.email = email
            request.user.save(update_fields=["email"])

        if data["kind"] == PaystackPayment.Kind.CREDITS:
            topup = settings.CREDIT_TOPUP
            purpose = paystack.CREDITS_PURPOSE
            payment = PaystackPayment(
                user=request.user, kind=PaystackPayment.Kind.CREDITS, credits=topup["credits"],
                reference=paystack.make_reference(purpose), amount_kobo=topup["price_ngn"] * 100,
            )
            label = f"NutriScan AI credits ({topup['credits']})"
            extra = {"credits": topup["credits"]}
        else:
            tier, plan = data["tier"], data["plan"]
            current = credits.tier_of(request.user)
            if credits.TIER_RANK[current] > credits.TIER_RANK[tier]:
                expires = Subscription.objects.get(user=request.user).expires_at
                return Response(
                    {
                        "detail": f"You're on NutriScan {settings.PRO_TIERS[current]['label']} until "
                                  f"{timezone.localtime(expires):%d %b %Y}. You can switch to a smaller plan after that.",
                        "reason": "downgrade_while_active",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            purpose = paystack.plan_purpose(tier, plan)
            payment = PaystackPayment(
                user=request.user, plan=plan, tier=tier, reference=paystack.make_reference(purpose),
                amount_kobo=_price_ngn(tier, plan) * 100,
            )
            label = f"NutriScan {settings.PRO_TIERS[tier]['label']} ({Subscription.Plan(plan).label})"
            extra = {"tier": tier, "plan": plan}

        try:
            result = paystack.initialize_transaction(
                email=request.user.email,
                amount_kobo=payment.amount_kobo,
                reference=payment.reference,
                callback_url=f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/subscription/paystack/return/",
                metadata=paystack.paystack_metadata(purpose, label, user_id=request.user.id, **extra),
            )
        except paystack.PaystackNotConfigured:
            return Response(
                {"detail": "Payments aren't available right now. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except paystack.PaystackError as exc:
            log.error("Paystack initialize failed for %s: %s", payment.reference, exc)
            return Response({"detail": "Payment couldn't be started. Please try again."}, status=status.HTTP_502_BAD_GATEWAY)

        payment.authorization_url = result["authorization_url"]
        payment.save()
        return Response(
            {"reference": payment.reference, "authorization_url": payment.authorization_url},
            status=status.HTTP_201_CREATED,
        )


class PaystackVerifyView(APIView):
    """The app calls this after the browser checkout, so Pro switches on without waiting for the webhook."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, reference):
        payment = PaystackPayment.objects.filter(reference=reference, user=request.user).first()
        if payment is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        payment = _verify_with_paystack(payment)
        request.user.refresh_from_db(fields=["is_pro"])
        return Response({"reference": payment.reference, "status": payment.status, "is_pro": request.user.is_pro})


class PaystackReturnView(APIView):
    """Where Paystack's checkout sends the payer's browser. Confirms with Paystack (no login
    needed: it only ever applies what Paystack itself reports) and says what to do next."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        reference = request.query_params.get("reference", "")
        payment = PaystackPayment.objects.filter(reference=reference).first() if reference else None
        if payment is not None:
            payment = _verify_with_paystack(payment)

        if payment is not None and payment.status == PaystackPayment.Status.SUCCESS:
            title, message = "Payment received", "Thank you. Your purchase is active. You can go back to the NutriScan app."
        elif payment is not None and payment.status == PaystackPayment.Status.FAILED:
            title, message = "Payment not accepted", "Please contact support with your reference."
        else:
            title, message = "Payment not confirmed yet", "If you paid, it will switch on within a few minutes."
        page = (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{title} | NutriScan</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:28rem;margin:4rem auto;padding:0 1rem;"
            "text-align:center}code{background:#eef5ee;padding:.15rem .4rem;border-radius:.3rem}</style></head>"
            f"<body><h1>{title}</h1><p>{message}</p><p>Reference: <code>{escape(reference)}</code></p></body></html>"
        )
        return HttpResponse(page)


class PaystackWebhookView(APIView):
    """Paystack events, forwarded by the shared account's webhook router. Authenticated by the
    HMAC signature, not by user credentials."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    def post(self, request):
        raw = request.body
        if not paystack.verify_webhook_signature(raw, request.headers.get("x-paystack-signature", "")):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = json.loads(raw)
        except ValueError:
            return Response({"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST)

        data = payload.get("data") or {}
        if payload.get("event") == "charge.success" and paystack.is_ours(data.get("reference")):
            apply_paystack_transaction(data["reference"], data)
        # Anything else (another app's reference, an event we don't act on) is acknowledged so
        # Paystack doesn't keep retrying it.
        return Response({"received": True})

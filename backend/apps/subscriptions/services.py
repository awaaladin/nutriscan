import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import PaystackPayment, Subscription
from .play_client import PlayNotConfigured, PlayVerificationError, get_verifier

log = logging.getLogger(__name__)


def apply_play_state(subscription: Subscription, play, user) -> Subscription:
    """Copies Google's view of the subscription onto our row and the user's
    is_pro flag. Entitlement requires both a paid state and a future expiry."""
    now = timezone.now()
    entitled = play.entitled and play.expires_at > now
    subscription.expires_at = play.expires_at
    subscription.status = Subscription.Status.ACTIVE if entitled else Subscription.Status.EXPIRED
    subscription.save()

    # Update the caller's own user instance, not subscription.user: they are
    # different objects, and the in-flight request must see the new value.
    if user.is_pro != entitled:
        user.is_pro = entitled
        user.save(update_fields=["is_pro"])
    return subscription


def refresh_pro_status(user) -> None:
    """Keeps is_pro honest without a push webhook: once a stored expiry has
    passed, ask Google again -- a renewal extends it, a lapse revokes Pro.
    Never grants Pro from anything except Google's answer."""
    if not user.is_pro:
        return
    subscription = Subscription.objects.filter(user=user).first()
    if subscription is None:
        user.is_pro = False
        user.save(update_fields=["is_pro"])
        return
    if subscription.expires_at and subscription.expires_at > timezone.now():
        return
    if not subscription.play_purchase_token:
        # Prepaid through Paystack (or nothing at all): there's no renewal to ask anyone about.
        subscription.status = Subscription.Status.EXPIRED
        subscription.save(update_fields=["status", "updated_at"])
        user.is_pro = False
        user.save(update_fields=["is_pro"])
        return
    try:
        play = get_verifier().get_subscription(subscription.play_purchase_token)
    except (PlayNotConfigured, PlayVerificationError):
        # Can't confirm renewal right now; an expired entitlement is not honoured.
        user.is_pro = False
        user.save(update_fields=["is_pro"])
        return
    apply_play_state(subscription, play, user)


@transaction.atomic
def apply_paystack_transaction(reference: str, data: dict) -> PaystackPayment | None:
    """Applies Paystack's view of a transaction to its payment. The row lock plus the PENDING
    check make it idempotent: the webhook, the return page and the app's verify call can all
    report the same charge and Pro is still extended once. Only a successful NGN charge of at
    least the price counts; Pro is never granted from anything but Paystack's answer."""
    payment = PaystackPayment.objects.select_for_update().select_related("user").filter(reference=reference).first()
    if payment is None or payment.status != PaystackPayment.Status.PENDING or data.get("status") != "success":
        return payment

    if data.get("currency", "NGN") != "NGN" or int(data.get("amount") or 0) < payment.amount_kobo:
        log.error("Paystack %s: expected %s kobo NGN, got %s %s", reference, payment.amount_kobo,
                  data.get("amount"), data.get("currency"))
        payment.status = PaystackPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return payment

    now = timezone.now()
    payment.status = PaystackPayment.Status.SUCCESS
    payment.paid_at = now
    payment.paystack_transaction_id = str(data.get("id") or "")
    payment.save(update_fields=["status", "paid_at", "paystack_transaction_id"])

    subscription, _ = Subscription.objects.select_for_update().get_or_create(user=payment.user)
    still_running = subscription.is_active and subscription.expires_at and subscription.expires_at > now
    start = subscription.expires_at if still_running else now
    subscription.plan = payment.plan
    subscription.status = Subscription.Status.ACTIVE
    subscription.expires_at = start + timedelta(days=settings.PAYSTACK_PLAN_DAYS[payment.plan])
    subscription.save()

    if not payment.user.is_pro:
        payment.user.is_pro = True
        payment.user.save(update_fields=["is_pro"])
    return payment

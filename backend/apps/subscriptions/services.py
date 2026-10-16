from django.utils import timezone

from .models import Subscription
from .play_client import PlayNotConfigured, PlayVerificationError, get_verifier


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
    if subscription is None or not subscription.play_purchase_token:
        user.is_pro = False
        user.save(update_fields=["is_pro"])
        return
    if subscription.expires_at and subscription.expires_at > timezone.now():
        return
    try:
        play = get_verifier().get_subscription(subscription.play_purchase_token)
    except (PlayNotConfigured, PlayVerificationError):
        # Can't confirm renewal right now; an expired entitlement is not honoured.
        user.is_pro = False
        user.save(update_fields=["is_pro"])
        return
    apply_play_state(subscription, play, user)

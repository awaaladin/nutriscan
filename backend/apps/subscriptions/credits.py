"""AI credits: how much AI each plan includes, and fair use within it.

Every AI action costs credits (settings.AI_CREDIT_COSTS). Each calendar month (Lagos time) a
user gets their plan's allowance; bought top-up credits (User.bonus_credits) are spent only
after it runs out and never expire. One credit is budgeted at about N5 of Gemini cost, which is
what keeps every plan profitable even for a member who uses all of it (docs/pricing.md).

Two limits, both stated honestly to the user:
  - out of credits for the month -> 402, with when it renews and the top-up/upgrade options;
  - more than AI_CREDITS_PER_HOUR in a rolling hour -> 429 with the minutes until it's ready.

Credits are charged only after an answer is delivered: a failed AI call costs nothing.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import AiUsage, Subscription, Tier

TIER_RANK = {"free": 0, Tier.PRO: 1, Tier.PLUS: 2, Tier.CARE: 3}


class CreditError(Exception):
    def __init__(self, status: int, reason: str, detail: str, **extra):
        super().__init__(detail)
        self.status, self.reason, self.detail, self.extra = status, reason, detail, extra

    def as_response_data(self) -> dict:
        return {"detail": self.detail, "reason": self.reason, **self.extra}


def tier_of(user) -> str:
    """The user's paid tier ("pro", "plus", "care") or "free". Expiry is re-checked first."""
    from .services import refresh_pro_status

    refresh_pro_status(user)
    if not user.is_pro:
        return "free"
    subscription = Subscription.objects.filter(user=user).only("tier").first()
    return subscription.tier if subscription else "free"


def has_tier(user, required: str) -> bool:
    return TIER_RANK[tier_of(user)] >= TIER_RANK[required]


def require_tier(user, required: str, feature: str):
    if not has_tier(user, required):
        label = settings.PRO_TIERS[required]["label"]
        raise CreditError(
            403, "upgrade_required", f"{feature} is part of NutriScan {label}.", required_tier=required,
        )


def monthly_allowance(tier: str) -> int:
    return settings.FREE_MONTHLY_CREDITS if tier == "free" else settings.PRO_TIERS[tier]["monthly_credits"]


def _month_start(now=None):
    local = timezone.localtime(now or timezone.now())
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month_start(now=None):
    start = _month_start(now)
    return (start + timedelta(days=32)).replace(day=1)


def balance(user) -> dict:
    tier = tier_of(user)
    allowance = monthly_allowance(tier)
    used = AiUsage.objects.filter(user=user, created_at__gte=_month_start()).aggregate(n=Sum("credits"))["n"] or 0
    return {
        "tier": tier,
        "monthly_allowance": allowance,
        "used_this_month": used,
        "monthly_remaining": max(allowance - used, 0),
        "bonus_credits": user.bonus_credits,
        "total_remaining": max(allowance - used, 0) + user.bonus_credits,
        "renews_on": _next_month_start().date().isoformat(),
        "costs": settings.AI_CREDIT_COSTS,
    }


def ensure_can_spend(user, action: str) -> dict:
    """Raises CreditError unless the user can afford `action` right now. Returns the balance."""
    cost = settings.AI_CREDIT_COSTS[action]
    state = balance(user)
    if cost == 0:
        return state

    hour_ago = timezone.now() - timedelta(hours=1)
    recent = list(
        AiUsage.objects.filter(user=user, created_at__gte=hour_ago)
        .exclude(credits=0, bonus_credits=0)
        .order_by("created_at")
        .values_list("created_at", "credits", "bonus_credits")
    )
    spent = sum(c + b for _, c, b in recent)
    if spent + cost > settings.AI_CREDITS_PER_HOUR:
        # Ready again once enough of the last hour's use has aged out of the window.
        need, freed, ready_at = spent + cost - settings.AI_CREDITS_PER_HOUR, 0, timezone.now()
        for created_at, c, b in recent:
            freed += c + b
            ready_at = created_at + timedelta(hours=1)
            if freed >= need:
                break
        minutes = max(1, int((ready_at - timezone.now()).total_seconds() // 60) + 1)
        raise CreditError(
            429, "cooldown",
            f"You've used a lot of AI in the last hour. To keep it fast for everyone, it'll be ready "
            f"again in about {minutes} minute{'s' if minutes != 1 else ''}.",
            retry_after_minutes=minutes,
        )

    if state["total_remaining"] < cost:
        tier = state["tier"]
        if tier == "free":
            detail = "You've used this month's free AI credits. Upgrade to Pro for more, or wait until they renew."
        else:
            detail = "You've used this month's AI credits. Top up for more, or wait until they renew."
        raise CreditError(402, "out_of_credits", detail, renews_on=state["renews_on"], tier=tier,
                          needed=cost, remaining=state["total_remaining"])
    return state


def _cost_usd(usage: dict) -> Decimal:
    model = (usage.get("model") or "").lower()
    prices = settings.GEMINI_PRICES_USD_PER_MILLION
    # Most specific first: "flash-lite" must not be priced as "flash".
    key = next((k for k in sorted(prices, key=len, reverse=True) if k in model), "flash")
    price_in, price_out = prices[key]
    cost = (
        usage.get("prompt_tokens", 0) * price_in / 1_000_000
        + usage.get("output_tokens", 0) * price_out / 1_000_000
        + usage.get("search_queries", 0) * settings.GEMINI_SEARCH_USD_PER_QUERY
    )
    return Decimal(str(round(cost, 6)))


@transaction.atomic
def charge(user, action: str, usage: dict = None) -> AiUsage:
    """Records one delivered AI action: takes its credits (monthly allowance first, then top-up
    credits) and logs Gemini's real usage. Never takes more than the user has left."""
    from apps.users.models import User

    user = User.objects.select_for_update().get(pk=user.pk)
    cost = settings.AI_CREDIT_COSTS[action]
    state = balance(user)
    from_allowance = min(cost, state["monthly_remaining"])
    from_bonus = min(cost - from_allowance, user.bonus_credits)
    if from_bonus:
        user.bonus_credits -= from_bonus
        user.save(update_fields=["bonus_credits"])
    usage = usage or {}
    return AiUsage.objects.create(
        user=user,
        action=action,
        tier="" if state["tier"] == "free" else state["tier"],
        credits=from_allowance,
        bonus_credits=from_bonus,
        model=(usage.get("model") or "")[:64],
        prompt_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        search_queries=usage.get("search_queries", 0),
        cost_usd=_cost_usd(usage),
    )

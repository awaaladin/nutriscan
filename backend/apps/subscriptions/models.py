from django.conf import settings
from django.db import models


class Tier(models.TextChoices):
    """What a paid plan unlocks; prices and credits are in settings.PRO_TIERS."""

    PRO = "pro", "Pro"
    PLUS = "plus", "Pro Plus"
    CARE = "care", "Pro Care"


class Subscription(models.Model):
    class Plan(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.MONTHLY)
    tier = models.CharField(max_length=8, choices=Tier.choices, default=Tier.PRO)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.EXPIRED)
    # Unique when set: one Play purchase can back only one account. Blank is
    # stored as NULL so many free users don't collide on "".
    play_purchase_token = models.CharField(max_length=512, null=True, blank=True, unique=True)
    play_product_id = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    def __str__(self):
        return f"Subscription({self.user_id}, {self.status})"


class PaystackPayment(models.Model):
    """One Paystack checkout: a prepaid plan period or a credit top-up. The reference
    (NUTRISCAN-CAREMONTH-..., NUTRISCAN-CREDITS-...) is what shows in the shared Paystack
    dashboard, so a row here can always be matched to it."""

    class Kind(models.TextChoices):
        SUBSCRIPTION = "subscription", "Plan"
        CREDITS = "credits", "Credit top-up"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    # Kept when the account is deleted (detached from the person): payment records must be
    # retained for tax and accounting.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="paystack_payments"
    )
    reference = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SUBSCRIPTION)
    plan = models.CharField(max_length=16, choices=Subscription.Plan.choices, blank=True)
    tier = models.CharField(max_length=8, choices=Tier.choices, blank=True)
    credits = models.PositiveIntegerField(default=0)
    amount_kobo = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    authorization_url = models.URLField(max_length=2048, blank=True)
    paystack_transaction_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference} ({self.status})"


class AiUsage(models.Model):
    """One AI call made for a user: what it cost them in credits and what it cost us at Google.

    Token counts are Gemini's own usageMetadata, so manage.py ai_cost_report can show real
    margins per plan. Holds no message text."""

    # Kept, detached, when the account is deleted: it holds no personal content, only costs.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ai_usage")
    action = models.CharField(max_length=32)
    tier = models.CharField(max_length=8, blank=True)  # "" = free
    credits = models.PositiveSmallIntegerField(default=0)  # from this month's allowance
    bonus_credits = models.PositiveSmallIntegerField(default=0)  # from top-ups
    model = models.CharField(max_length=64, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)  # answer + thinking, both billed as output
    search_queries = models.PositiveSmallIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"AiUsage({self.user_id}, {self.action}, {self.credits + self.bonus_credits})"

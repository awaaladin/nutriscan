from django.conf import settings
from django.db import models


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
    """One Paystack checkout for a prepaid Pro period. The reference (NUTRISCAN-PRO...) is what
    shows in the shared Paystack dashboard, so a row here can always be matched to it."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="paystack_payments")
    reference = models.CharField(max_length=100, unique=True)
    plan = models.CharField(max_length=16, choices=Subscription.Plan.choices)
    amount_kobo = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    authorization_url = models.URLField(max_length=2048, blank=True)
    paystack_transaction_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference} ({self.status})"

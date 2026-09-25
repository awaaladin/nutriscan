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
    play_purchase_token = models.CharField(max_length=512, blank=True)
    play_product_id = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    def __str__(self):
        return f"Subscription({self.user_id}, {self.status})"

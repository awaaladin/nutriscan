"""Readings a Pro member logs themselves: weight, blood pressure, blood glucose.

Health data is sensitive personal data under the NDPA, so like chats these belong to one
account, are only ever returned to it, are not registered in Django admin, and are deleted
with the account.
"""
from django.conf import settings
from django.db import models


class HealthLog(models.Model):
    class Kind(models.TextChoices):
        WEIGHT = "weight", "Weight"
        BLOOD_PRESSURE = "blood_pressure", "Blood pressure"
        GLUCOSE = "glucose", "Blood glucose"

    class Timing(models.TextChoices):
        FASTING = "fasting", "Fasting"
        BEFORE_MEAL = "before_meal", "Before a meal"
        AFTER_MEAL = "after_meal", "2 hours after a meal"
        RANDOM = "random", "Random"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="health_logs")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    # Weight in kg, or glucose in mg/dL. Blood pressure uses systolic/diastolic instead.
    value = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    timing = models.CharField(max_length=16, choices=Timing.choices, blank=True)  # glucose only
    note = models.CharField(max_length=200, blank=True)
    measured_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-measured_at", "-id"]
        indexes = [models.Index(fields=["user", "kind", "measured_at"])]

    def __str__(self):
        return f"HealthLog({self.user_id}, {self.kind})"

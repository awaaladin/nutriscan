from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Goal(models.TextChoices):
        GENERAL_HEALTH = "general_health", "General health"
        DIABETES = "diabetes", "Diabetes management"
        WEIGHT_LOSS = "weight_loss", "Weight loss"
        HYPERTENSION = "hypertension", "Hypertension management"

    primary_goal = models.CharField(max_length=32, choices=Goal.choices, default=Goal.GENERAL_HEALTH)
    is_diabetic = models.BooleanField(default=False)
    has_hypertension = models.BooleanField(default=False)
    is_pro = models.BooleanField(default=False)
    # Pharmacists, NAFDAC staff, shop owners etc. vetted by an admin; their
    # reports carry extra weight in the trust assessment.
    is_verified_reviewer = models.BooleanField(default=False)
    # Free text the user chooses to share with the assistant (allergies, conditions,
    # medicines they take) so its answers are personal. Private to the account.
    health_notes = models.TextField(blank=True, max_length=500)
    # Explicit opt-in to include this user's (anonymised) assistant chats in a
    # training dataset. Health data is sensitive personal data: off by default.
    allow_training_use = models.BooleanField(default=False)
    region = models.CharField(max_length=64, default="NG")
    # Bought top-up credits: spent after the monthly allowance, never expire.
    bonus_credits = models.PositiveIntegerField(default=0)
    # Optional, for weight goals (BMI and progress in the Pro health tools).
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    # When the user accepted the Terms and Privacy Policy, and separately gave the explicit
    # consent the NDPA requires before we process their health information. Null = not yet.
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    health_consent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username

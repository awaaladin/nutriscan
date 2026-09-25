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
    region = models.CharField(max_length=64, default="NG")

    def __str__(self):
        return self.username

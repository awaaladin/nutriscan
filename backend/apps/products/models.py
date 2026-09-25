from django.conf import settings
from django.db import models


class Product(models.Model):
    class Source(models.TextChoices):
        OPEN_FOOD_FACTS = "off", "Open Food Facts"
        COMMUNITY = "community", "Community submission"

    barcode = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.OPEN_FOOD_FACTS)

    # All nutrition values are per 100g/100ml, matching Open Food Facts convention.
    calories_kcal = models.FloatField(null=True, blank=True)
    sugar_g = models.FloatField(null=True, blank=True)
    saturated_fat_g = models.FloatField(null=True, blank=True)
    sodium_mg = models.FloatField(null=True, blank=True)
    carbohydrates_g = models.FloatField(null=True, blank=True)
    fiber_g = models.FloatField(null=True, blank=True)
    protein_g = models.FloatField(null=True, blank=True)

    ingredients_text = models.TextField(blank=True)
    additives = models.JSONField(default=list, blank=True)
    image_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.barcode})"


class ProductSubmission(models.Model):
    """A community-submitted product, used to fill Open Food Facts gaps
    for Nigerian/local products. Reviewed manually before becoming a Product."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    barcode = models.CharField(max_length=32, db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="submissions"
    )
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=255, blank=True)
    nutrition_payload = models.JSONField(default=dict)
    ingredients_text = models.TextField(blank=True)
    photo_url = models.URLField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Submission({self.barcode}, {self.status})"


class CachedExplanation(models.Model):
    """Caches LLM-generated explanations per product+result so repeat scans
    of the same product with the same score don't trigger a new LLM call."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="explanations")
    score = models.IntegerField()
    label = models.CharField(max_length=16)
    diabetic_risk = models.CharField(max_length=16)
    explanation_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "score", "label", "diabetic_risk")

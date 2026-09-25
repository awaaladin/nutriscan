from django.conf import settings
from django.db import models


class Scan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scans")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="scans")
    score = models.IntegerField()
    label = models.CharField(max_length=16)
    diabetic_risk = models.CharField(max_length=16)
    flags = models.JSONField(default=list, blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scanned_at"]

    def __str__(self):
        return f"Scan({self.product_id}, {self.label})"

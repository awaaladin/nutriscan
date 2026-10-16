from django.conf import settings
from django.db import models


class ProductReport(models.Model):
    """A user's real/fake verdict on a product, with optional evidence.

    One report per user per product (re-submitting updates it), so a single
    account can't stack votes. Hidden reports (set by admins after review)
    are excluded from the integrity percentage and the public feed."""

    class Verdict(models.TextChoices):
        REAL = "real", "Real / genuine"
        FAKE = "fake", "Fake / counterfeit"

    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="reports")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    verdict = models.CharField(max_length=8, choices=Verdict.choices)
    comment = models.TextField(blank=True, max_length=1000)
    where_bought = models.CharField(max_length=255, blank=True)
    batch_number = models.CharField(max_length=64, blank=True)
    nafdac_number = models.CharField(max_length=32, blank=True)
    is_hidden = models.BooleanField(default=False, help_text="Set by an admin after review; excluded from scoring.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="one_report_per_user_per_product"),
        ]

    def __str__(self):
        return f"Report({self.product_id}, {self.verdict}, user={self.user_id})"


class ReportPhoto(models.Model):
    report = models.ForeignKey(ProductReport, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="report_photos/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)


class ReportFlag(models.Model):
    """A user flagging someone else's report as abusive/false. Admins review
    flagged reports in Django admin and can hide them."""

    report = models.ForeignKey(ProductReport, on_delete=models.CASCADE, related_name="flags")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="report_flags")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["report", "user"], name="one_flag_per_user_per_report"),
        ]


class ProductDispute(models.Model):
    """A manufacturer or brand owner contesting how their product is shown
    (e.g. a rival mass-reporting it). Reviewed by an admin, who can hide
    reports, confirm the product as manufacturer-verified, or reject."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="disputes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="disputes")
    company_name = models.CharField(max_length=255)
    contact = models.CharField(max_length=255, help_text="Email or phone the admin can use to follow up.")
    message = models.TextField(max_length=2000)
    nafdac_number = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dispute({self.product_id}, {self.company_name}, {self.status})"

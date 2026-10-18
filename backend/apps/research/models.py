"""NutriScan's own trusted data set: what we know, where we got it, and how sure we are.

Three tables:
- ProductEvidence: every piece of data about a product, with its source. Trust is
  computed from this, never asserted: a product is only "corroborated" if two
  independent sources agree.
- DataCorrection: users telling us a value is wrong. Corrections are weighted by
  who sent them and only applied when enough credible people agree (or an admin
  approves), so one account can't rewrite the data set.
- KnowledgeEntry: reviewed question/answer pairs the assistant retrieves from.
  This is how the cloud AI "learns from our users" today without a training run:
  it answers from our approved entries. They are also the training-ready export.
"""
from django.conf import settings
from django.db import models


class ProductEvidence(models.Model):
    class SourceType(models.TextChoices):
        OPEN_FOOD_FACTS = "open_food_facts", "Open Food Facts"
        LABEL_PHOTO = "label_photo", "Label photo read by AI"
        WEB_AI = "web_ai", "AI web research (with sources)"
        COMMUNITY = "community", "Community correction"
        USER_TYPED = "user_typed", "Typed by a user"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested (not applied)"
        AGREES = "agrees", "Agrees with our data"
        CONFLICTS = "conflicts", "Conflicts with our data"
        APPLIED = "applied", "Applied to the product"
        REFERENCE = "reference", "Reference only (different country / weak match)"

    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="evidence")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    # Where it came from: an Open Food Facts URL, a cited web page, a user id hash...
    source_ref = models.CharField(max_length=500, blank=True)
    source_label = models.CharField(max_length=200, blank=True, help_text="Human-readable, e.g. 'Peak Milk (Nigeria)'")
    # Normalised per-100g/100ml values and text the source gave.
    facts = models.JSONField(default=dict, blank=True)
    # How sure we are THIS source is about THIS product (name/brand/country match), 0-1.
    match_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUGGESTED)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["product", "source_type"])]

    def __str__(self):
        return f"Evidence({self.product_id}, {self.source_type}, {self.status})"


class DataCorrection(models.Model):
    """A user (or the research step) saying one field of a product is wrong."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="corrections")
    # Null when raised automatically by the research step after finding a conflict.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="corrections")
    field = models.CharField(max_length=32)
    current_value = models.CharField(max_length=500, blank=True)
    suggested_value = models.CharField(max_length=500)
    reason = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Correction({self.product_id}.{self.field} -> {self.suggested_value}, {self.status})"


class KnowledgeEntry(models.Model):
    """A reviewed question/answer pair. Only `approved` entries are ever used."""

    class Source(models.TextChoices):
        CURATED = "curated", "Written by an admin"
        CHAT = "chat", "Built from a consented, rated chat"

    question = models.CharField(max_length=500)
    answer = models.TextField()
    topic = models.CharField(max_length=40, blank=True, help_text="e.g. diabetes, medicines, counterfeits")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CURATED)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "knowledge entries"

    def __str__(self):
        return self.question[:60]


class ResearchRun(models.Model):
    """That research was attempted for a product, and when -- so an empty result is
    remembered too and a product isn't re-researched on every open."""

    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="research_runs")
    evidence_added = models.PositiveSmallIntegerField(default=0)
    fields_applied = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

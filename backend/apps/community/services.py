from dataclasses import asdict

from django.utils import timezone

from .integrity import IntegrityResult, compute_integrity
from .models import ProductReport

PHOTO_BONUS = 0.5
BATCH_BONUS = 0.5
VERIFIED_REVIEWER_MULTIPLIER = 3.0


def report_weight(report) -> float:
    """How much a report counts. Evidence earns weight (photos, batch number),
    brand-new accounts count for little so mass-created accounts can't swing a
    product, and vetted reviewers count extra."""
    weight = 1.0
    if report.photos.all():
        weight += PHOTO_BONUS
    if report.batch_number:
        weight += BATCH_BONUS

    age_days = (timezone.now() - report.user.date_joined).days
    if age_days < 2:
        weight *= 0.25
    elif age_days < 14:
        weight *= 0.6

    if report.user.is_verified_reviewer:
        weight *= VERIFIED_REVIEWER_MULTIPLIER
    return weight


def integrity_for_product(product) -> IntegrityResult:
    reports = (
        ProductReport.objects.filter(product=product, is_hidden=False)
        .select_related("user")
        .prefetch_related("photos")
    )
    return compute_integrity(
        barcode=product.barcode,
        in_independent_db=product.source == "off",
        nafdac_verified=product.nafdac_verified,
        manufacturer_verified=product.manufacturer_verified,
        reports=[(r.verdict, report_weight(r)) for r in reports],
    )


def integrity_dict(product) -> dict:
    return asdict(integrity_for_product(product))

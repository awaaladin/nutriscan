from dataclasses import asdict

from .integrity import IntegrityResult, compute_integrity
from .models import ProductReport


def integrity_for_product(product) -> IntegrityResult:
    votes = ProductReport.objects.filter(product=product, is_hidden=False)
    return compute_integrity(
        barcode=product.barcode,
        in_independent_db=product.source == "off",
        real_votes=votes.filter(verdict=ProductReport.Verdict.REAL).count(),
        fake_votes=votes.filter(verdict=ProductReport.Verdict.FAKE).count(),
    )


def integrity_dict(product) -> dict:
    return asdict(integrity_for_product(product))

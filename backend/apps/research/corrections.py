"""Users correcting the data set, safely.

A correction is only a vote. It is applied when the weighted agreement of credible,
independent people is high enough -- so users genuinely improve the data, but no
single account (or a pile of brand-new throwaway accounts) can rewrite it.
"""
from statistics import median
from typing import List, Optional, Tuple

from django.utils import timezone

from apps.community.nafdac import normalize_nafdac_number
from apps.products.models import Product
from apps.products.nutrition_input import NutritionInputError, clean_nutrition

from .matching import KEY_FIELDS, values_agree
from .models import DataCorrection, ProductEvidence

TEXT_FIELDS = ("nafdac_number", "ingredients_text")
CORRECTABLE = KEY_FIELDS + TEXT_FIELDS
# Total weight needed to apply a correction: three established accounts, one vetted
# reviewer, or a research conflict backed by two established accounts.
ACCEPT_WEIGHT = 3.0
RESEARCH_WEIGHT = 1.0
MAX_TEXT = 3000


def user_weight(user) -> float:
    if user is None:
        return RESEARCH_WEIGHT  # raised by the research step after a source disagreed
    age_days = (timezone.now() - user.date_joined).days
    weight = 0.25 if age_days < 2 else 0.6 if age_days < 14 else 1.0
    return weight * (3.0 if user.is_verified_reviewer else 1.0)


def _clean(field: str, raw) -> object:
    """Validated value for `field`, or ValueError with a message for the user."""
    if field not in CORRECTABLE:
        raise ValueError("That field can't be corrected.")
    if field in KEY_FIELDS:
        try:
            value = float(str(raw).replace(",", "."))
            return clean_nutrition({field: value}, strict=True)[field]
        except (ValueError, NutritionInputError) as exc:
            raise ValueError(str(exc) if isinstance(exc, NutritionInputError) else "Enter a number.")
    text = str(raw or "").strip()
    if field == "nafdac_number":
        normalized = normalize_nafdac_number(text)
        if not normalized:
            raise ValueError("That doesn't look like a NAFDAC number (e.g. A4-1234).")
        return normalized
    if not text or len(text) > MAX_TEXT:
        raise ValueError("Enter the ingredient list (up to 3000 characters).")
    return text


def _same(field: str, a, b, tight: bool = False) -> bool:
    """Whether two values count as the same. Grouping people who AGREE uses the normal
    source-agreement tolerance; deciding whether someone is correcting us at all uses
    `tight` (rounding only), or a user saying 45 where we hold 39 would be told
    "that's already the value we have"."""
    if field in KEY_FIELDS:
        a, b = float(a), float(b)
        return abs(a - b) <= max(0.005 * max(abs(a), abs(b)), 0.05) if tight else values_agree(field, a, b)
    return str(a).strip().lower() == str(b).strip().lower()


def apply_value(product: Product, field: str, value) -> None:
    setattr(product, field, value)
    product.is_estimated = True  # corrected by people, not read from a verified source
    product.save()


def _consensus(product: Product, field: str) -> Optional[Tuple[object, List[DataCorrection]]]:
    """The best-supported correction for `field` if its weighted support is enough."""
    open_ones = list(
        DataCorrection.objects.filter(product=product, field=field, status=DataCorrection.Status.OPEN).select_related("user")
    )
    best, best_weight = None, 0.0
    for anchor in open_ones:
        try:
            group = [c for c in open_ones if _same(field, _parse(field, anchor), _parse(field, c))]
        except ValueError:
            continue
        weight = sum(user_weight(c.user) for c in group)
        if weight > best_weight:
            best, best_weight = group, weight
    if not best or best_weight < ACCEPT_WEIGHT:
        return None
    values = [_parse(field, c) for c in best]
    return (round(median(values), 2) if field in KEY_FIELDS else values[0]), best


def _parse(field: str, correction: DataCorrection):
    return float(correction.suggested_value) if field in KEY_FIELDS else correction.suggested_value


def submit(user, product: Product, field: str, raw_value, reason: str = "") -> Tuple[DataCorrection, bool]:
    """Record a correction and apply it if credible people now agree.
    Returns (correction, applied). Raises ValueError with a user-facing message."""
    value = _clean(field, raw_value)
    current = getattr(product, field)
    if current is not None and str(current).strip() and _same(field, value, current, tight=True):
        raise ValueError("That's already the value we have.")

    correction, _ = DataCorrection.objects.update_or_create(
        product=product, user=user, field=field, status=DataCorrection.Status.OPEN,
        defaults={"suggested_value": str(value), "current_value": "" if current is None else str(current), "reason": reason[:300]},
    )
    outcome = _consensus(product, field)
    if outcome is None:
        return correction, False

    agreed_value, group = outcome
    apply_value(product, field, agreed_value)
    for c in group:
        c.status = DataCorrection.Status.ACCEPTED
        c.save(update_fields=["status"])
    ProductEvidence.objects.create(
        product=product, source_type=ProductEvidence.SourceType.COMMUNITY, source_label=f"{len(group)} user correction(s)",
        facts={field: agreed_value}, match_score=1.0, status=ProductEvidence.Status.APPLIED,
        note=f"Applied after {len(group)} credible users agreed.",
    )
    correction.refresh_from_db()
    return correction, True


def accept(correction: DataCorrection, by_admin: bool = True) -> None:
    """An admin accepting a correction directly."""
    value = _parse(correction.field, correction)
    apply_value(correction.product, correction.field, value)
    correction.status = DataCorrection.Status.ACCEPTED
    correction.save(update_fields=["status"])
    ProductEvidence.objects.create(
        product=correction.product, source_type=ProductEvidence.SourceType.ADMIN, source_label="admin review",
        facts={correction.field: value}, match_score=1.0, status=ProductEvidence.Status.APPLIED,
        note="Accepted by an admin.",
    )

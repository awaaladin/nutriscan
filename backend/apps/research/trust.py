"""How far to trust a product's data, and exactly why.

Computed from the evidence we hold, never asserted:

  verified      NAFDAC number confirmed on the Greenbook, or the manufacturer confirmed
  corroborated  two INDEPENDENT sources agree (e.g. a label photo and Open Food Facts)
  sourced       one reputable external source (the product came from Open Food Facts)
  unverified    a single AI/user source nobody has checked

Independent means different kinds of source: two label photos of the same pack, or two
Open Food Facts listings, are one kind of evidence, not two.
"""
from typing import List

from .models import ProductEvidence

HEADLINES = {
    "verified": "Verified data",
    "corroborated": "Corroborated by 2 sources",
    "sourced": "From Open Food Facts",
    "unverified": "Unverified data",
}
_ORIGIN_BY_PRODUCT_SOURCE = {"off": "open_food_facts", "ai_vision": "label_photo", "community": "user_typed"}
_SOURCE_NAMES = {
    "open_food_facts": "Open Food Facts",
    "label_photo": "a label photo read by AI",
    "web_ai": "AI web research",
    "community": "user corrections",
    "user_typed": "values typed by a user",
    "admin": "an admin",
}


def data_trust(product) -> dict:
    evidence: List[ProductEvidence] = list(product.evidence.all())
    origin = _ORIGIN_BY_PRODUCT_SOURCE.get(product.source)

    supporting = {e.source_type for e in evidence if e.status in (ProductEvidence.Status.AGREES, ProductEvidence.Status.APPLIED)}
    independent = set(supporting)
    if origin:
        independent.add(origin)

    conflicts = [e for e in evidence if e.status == ProductEvidence.Status.CONFLICTS]
    lines: List[str] = []
    warnings: List[str] = []

    if origin:
        suffix = "" if origin == "open_food_facts" else " (not independently checked)" if len(independent) == 1 else ""
        lines.append(f"Our record came from {_SOURCE_NAMES[origin]}{suffix}.")
    for e in evidence:
        if e.status == ProductEvidence.Status.AGREES:
            lines.append(f"{_SOURCE_NAMES.get(e.source_type, e.source_type).capitalize()} agrees: {e.source_label}.")
        elif e.status == ProductEvidence.Status.APPLIED:
            lines.append(f"Missing values were added from {_SOURCE_NAMES.get(e.source_type, e.source_type)}: {e.source_label}.")
    for e in conflicts:
        warnings.append(f"Our data differs from {_SOURCE_NAMES.get(e.source_type, e.source_type)} ({e.source_label}); under review.")
    if product.nafdac_verified:
        lines.append("Its NAFDAC registration number was confirmed on the NAFDAC Greenbook.")
    if product.manufacturer_verified:
        lines.append("The manufacturer's details were confirmed.")

    if product.nafdac_verified or product.manufacturer_verified:
        level = "verified"
    elif len(independent) >= 2:
        level = "corroborated"
    elif origin == "open_food_facts" and not product.is_estimated:
        level = "sourced"
    else:
        level = "unverified"
    if level == "unverified" and not lines:
        lines.append("We have one unchecked record for this product.")

    sources = [
        {"type": e.source_type, "label": e.source_label, "url": e.source_ref}
        for e in evidence
        if e.source_ref.startswith("http") and e.status != ProductEvidence.Status.REFERENCE
    ]
    return {
        "level": level,
        "headline": HEADLINES[level],
        "evidence": lines,
        "warnings": warnings,
        "sources": sources[:5],
        "researched_at": evidence[0].created_at if evidence else None,
    }

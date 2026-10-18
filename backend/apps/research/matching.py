"""Deciding when two records describe the SAME product, and when their numbers agree.

Pure logic, no network or Django. The rule that protects trust: a source from the
wrong country is never treated as a match. "Milo" in Australia (45 g sugar) is not
"Milo" in Nigeria; copying one onto the other would make our data worse, not better.
"""
import re
from typing import Dict, Iterable, Optional, Tuple

# GS1 prefixes (first 3 digits of a 13-digit barcode) -> Open Food Facts country tag.
# Only prefixes we are certain of; unknown prefixes simply give "country unknown".
COUNTRY_BY_PREFIX = {
    "615": "en:nigeria",
    "603": "en:ghana",
    "600": "en:south-africa",
    "601": "en:south-africa",
    "616": "en:kenya",
}

MATCH_THRESHOLD = 0.6  # below this a source is kept as reference only, never compared or applied
_STOP = {"the", "and", "of", "with", "flavour", "flavor", "flavoured", "flavored", "pack", "pcs", "new", "original"}

# Per-field absolute tolerance (same units as the field), on top of 15% relative.
ABS_TOLERANCE = {
    "sugar_g": 0.8,
    "saturated_fat_g": 0.4,
    "sodium_mg": 20.0,
    "calories_kcal": 30.0,
    "carbohydrates_g": 2.0,
    "fiber_g": 0.8,
    "protein_g": 0.8,
}
KEY_FIELDS = tuple(ABS_TOLERANCE)
RELATIVE_TOLERANCE = 0.15


def barcode_country(barcode: str) -> Optional[str]:
    digits = (barcode or "").strip()
    if len(digits) == 13 and digits.isdigit():
        return COUNTRY_BY_PREFIX.get(digits[:3])
    return None


def tokens(*texts: str) -> set:
    words = set()
    for text in texts:
        words.update(re.findall(r"[a-z0-9]+", (text or "").lower()))
    return words - _STOP


def brand_text(brands) -> str:
    if isinstance(brands, (list, tuple)):
        return " ".join(str(b) for b in brands)
    return str(brands or "")


def match_score(
    our_name: str, our_brand: str, our_country: Optional[str],
    their_name: str, their_brands, their_countries: Iterable[str],
) -> float:
    """0-1 confidence that the other record is the same product as ours."""
    ours = tokens(our_name, our_brand)
    theirs = tokens(their_name, brand_text(their_brands))
    if not ours or not theirs:
        return 0.0
    score = len(ours & theirs) / len(ours | theirs)

    our_brand_tokens, their_brand_tokens = tokens(our_brand), tokens(brand_text(their_brands))
    if our_brand_tokens and their_brand_tokens and not (our_brand_tokens & their_brand_tokens):
        score *= 0.4  # both name a brand and they differ

    countries = {c for c in their_countries if c}
    if our_country and countries:
        if our_country not in countries:
            score = min(score, 0.4)  # a different country's formulation: reference only
    elif not our_country:
        score *= 0.85  # country unknown: can't confirm it's the same market
    return round(score, 3)


def values_agree(field: str, a: float, b: float) -> bool:
    return abs(a - b) <= max(RELATIVE_TOLERANCE * max(abs(a), abs(b)), ABS_TOLERANCE.get(field, 0.0))


def agreement(ours: Dict[str, Optional[float]], theirs: Dict[str, Optional[float]]) -> Tuple[int, int, int]:
    """(fields that agree, fields that conflict, fields compared) over fields both have."""
    agree = conflict = compared = 0
    for field in KEY_FIELDS:
        a, b = ours.get(field), theirs.get(field)
        if a is None or b is None:
            continue
        compared += 1
        if values_agree(field, a, b):
            agree += 1
        else:
            conflict += 1
    return agree, conflict, compared

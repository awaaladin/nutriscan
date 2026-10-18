"""Open Food Facts as a research source: a free, open, community-built product database.

Best-effort: on any network or format problem this returns no candidates rather than
raising, so research can never break a scan.
"""
import re
from typing import List, Optional

import requests

SEARCH_URL = "https://search.openfoodfacts.org/search"
PRODUCT_URL = "https://world.openfoodfacts.org/product/{code}"
HEADERS = {"User-Agent": "NutriScan/0.2 (nutrition research; contact: nutriscan-app@example.com)"}
FIELDS = "code,product_name,brands,countries_tags,nutriments,ingredients_text"
TIMEOUT = 8


def _num(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalise_nutrition(n: Optional[dict]) -> dict:
    """Open Food Facts nutriments -> our per-100g fields. Sodium is in grams there
    (or derived from salt), ours is milligrams."""
    if not isinstance(n, dict):
        return {}
    sodium_g = _num(n.get("sodium_100g"))
    if sodium_g is None:
        salt_g = _num(n.get("salt_100g"))
        sodium_g = salt_g / 2.5 if salt_g is not None else None
    kcal = _num(n.get("energy-kcal_100g"))
    if kcal is None:
        kj = _num(n.get("energy-kj_100g"))
        kcal = kj / 4.184 if kj is not None else None
    values = {
        "calories_kcal": kcal,
        "sugar_g": _num(n.get("sugars_100g")),
        "saturated_fat_g": _num(n.get("saturated-fat_100g")),
        "sodium_mg": sodium_g * 1000 if sodium_g is not None else None,
        "carbohydrates_g": _num(n.get("carbohydrates_100g")),
        "fiber_g": _num(n.get("fiber_100g")),
        "protein_g": _num(n.get("proteins_100g")),
    }
    return {k: round(v, 2) for k, v in values.items() if v is not None}


def clean_text(text: str) -> str:
    """Drop emoji and control characters that sometimes ride along in names."""
    return re.sub(r"[^\w\s\-.,&()'/%+]", "", text or "", flags=re.UNICODE).strip()


def search(query: str, limit: int = 8) -> List[dict]:
    query = clean_text(query)
    if len(query) < 3:
        return []
    try:
        response = requests.get(
            SEARCH_URL, params={"q": query, "page_size": limit, "fields": FIELDS}, headers=HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
    except (requests.RequestException, ValueError):
        return []

    candidates = []
    for hit in hits:
        code = hit.get("code")
        if not code:
            continue
        candidates.append(
            {
                "code": str(code),
                "name": hit.get("product_name") or "",
                "brands": hit.get("brands") or [],
                "countries": hit.get("countries_tags") or [],
                "facts": normalise_nutrition(hit.get("nutriments")),
                "ingredients_text": (hit.get("ingredients_text") or "").strip(),
                "url": PRODUCT_URL.format(code=code),
            }
        )
    return candidates

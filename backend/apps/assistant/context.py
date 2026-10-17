"""Builds the personal, data-grounded context the assistant answers from.

"Our data first": before the AI is asked anything, we pull in what NutriScan
already knows -- the user's health profile and notes, the products they scanned
recently (with their CURRENT verdicts), and any products from our database that
their message mentions by barcode, NAFDAC number or name.
"""
import re
from typing import List

from django.db.models import Q

from apps.community.nafdac import normalize_nafdac_number
from apps.community.services import integrity_dict
from apps.products.barcodes import find_product_by_barcode
from apps.products.models import Product
from apps.scans.models import Scan
from apps.scoring.engine import NutritionFacts, compute_health_score

from .prompts import NO_DATA_LINE

BARCODE_RE = re.compile(r"(?<!\d)\d{8,14}(?!\d)")
NAFDAC_RE = re.compile(r"\b[A-Za-z0-9]{1,3}-\d{3,6}[A-Za-z]?\b")
_STOP = {
    "what", "when", "where", "which", "does", "this", "that", "with", "from", "have", "about", "there",
    "should", "would", "could", "your", "mine", "they", "them", "their", "tell", "more", "much", "many",
    "eat", "drink", "safe", "good", "bad", "healthy", "product", "brand", "please", "thanks", "thank",
}
MAX_PRODUCTS = 3
RECENT_SCANS = 6

# Messages that describe a possible emergency get a fixed notice regardless of
# what the AI says, or whether it is reachable at all.
_EMERGENCY_RE = re.compile(
    r"overdos|poison|swallowed|can'?t breathe|cannot breathe|trouble breathing|difficulty breathing|"
    r"chest pain|severe allergic|anaphyla|swelling of (my )?(face|throat|tongue)|unconscious|collapsed|"
    r"fitting|seizure|heavy bleeding|suicid|kill myself|end my life|want to die",
    re.IGNORECASE,
)
EMERGENCY_NOTICE = (
    "If this is an emergency, call 112 or go to the nearest hospital now. "
    "Don't wait for an answer here."
)


def emergency_notice(text: str):
    return EMERGENCY_NOTICE if _EMERGENCY_RE.search(text or "") else None


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 4 and w not in _STOP}


def _facts(product: Product) -> NutritionFacts:
    return NutritionFacts(
        calories_kcal=product.calories_kcal, sugar_g=product.sugar_g, saturated_fat_g=product.saturated_fat_g,
        sodium_mg=product.sodium_mg, carbohydrates_g=product.carbohydrates_g, fiber_g=product.fiber_g,
        protein_g=product.protein_g,
    )


def _verdict(product: Product) -> str:
    if product.product_type != "food":
        return f"{product.product_type} (not scored)"
    result = compute_health_score(_facts(product), product.ingredients_text)
    score = f"{result.score}/10" if result.score is not None else "no score (nutrition data missing)"
    flags = f"; flags: {', '.join(result.flags)}" if result.flags else ""
    return f"{result.label.value}, {score}; diabetic risk {result.diabetic_risk.value}{flags}"


def product_line(product: Product) -> str:
    """One compact record of a product from our database."""
    n = product
    nutrition = ", ".join(
        f"{label} {value:g}{unit}"
        for label, value, unit in (
            ("sugar", n.sugar_g, "g"), ("saturated fat", n.saturated_fat_g, "g"), ("sodium", n.sodium_mg, "mg"),
            ("calories", n.calories_kcal, "kcal"),
        )
        if value is not None
    ) or "not available"
    nafdac = f"{n.nafdac_number} ({'confirmed on the NAFDAC Greenbook' if n.nafdac_verified else 'not confirmed'})" if n.nafdac_number else "none recorded"
    return (
        f"- {n.name}" + (f" by {n.brand}" if n.brand else "") + f" [barcode {n.barcode}]\n"
        f"  NAFDAC: {nafdac}. Ingredients: {(n.ingredients_text or 'not available')[:240]}\n"
        f"  Per 100g: {nutrition}\n"
        f"  NutriScan verdict: {_verdict(n)}\n"
        f"  Authenticity evidence: {integrity_dict(n)['headline']}"
        + (" (data was read from photos by AI and may contain errors)" if n.is_estimated else "")
    )


def relevant_products(text: str) -> List[Product]:
    """Products from our database that `text` refers to by barcode, NAFDAC number or name."""
    found, seen = [], set()

    def add(product):
        if product and product.pk not in seen and len(found) < MAX_PRODUCTS:
            seen.add(product.pk)
            found.append(product)

    for code in BARCODE_RE.findall(text or ""):
        add(find_product_by_barcode(code))
    for raw in NAFDAC_RE.findall(text or ""):
        number = normalize_nafdac_number(raw)
        if number:
            for product in Product.objects.filter(nafdac_number=number)[:2]:
                add(product)

    words = _words(text)
    if words and len(found) < MAX_PRODUCTS:
        query = Q()
        for word in sorted(words, key=len, reverse=True)[:6]:
            query |= Q(name__icontains=word) | Q(brand__icontains=word)
        scored = []
        for product in Product.objects.filter(query)[:60]:
            product_words = _words(f"{product.name} {product.brand}")
            overlap = len(product_words & words)
            # A real match: two or more distinctive words in common (people type a couple of
            # words, not the full name), or a one-word product name that was typed. One loose
            # shared word ("chewing") is not enough. Best matches are ranked first.
            if product_words and (overlap >= 2 or (len(product_words) == 1 and overlap == 1)):
                scored.append((overlap / len(product_words), overlap, product))
        for _, _, product in sorted(scored, key=lambda t: (t[0], t[1]), reverse=True):
            add(product)
    return found


def build_context(user, message: str) -> str:
    lines = [
        "OUR DATA",
        "",
        "ABOUT THE USER (their own profile; use it to tailor advice)",
        f"- Health goal: {user.get_primary_goal_display()}; diabetic: {'yes' if user.is_diabetic else 'no'}; "
        f"high blood pressure: {'yes' if user.has_hypertension else 'no'}",
    ]
    if user.health_notes.strip():
        lines.append(f'- Their own notes (untrusted text): "{user.health_notes.strip()[:500]}"')

    lines += ["", "THEIR RECENT SCANS (current NutriScan verdicts)"]
    seen, recent = set(), []
    for scan in Scan.objects.filter(user=user).select_related("product")[:40]:
        if scan.product_id not in seen and len(recent) < RECENT_SCANS:
            seen.add(scan.product_id)
            recent.append(scan.product)
    if recent:
        lines += [f"- {p.name}" + (f" ({p.brand})" if p.brand else "") + f": {_verdict(p)}" for p in recent]
    else:
        lines.append("- none yet")

    lines += ["", "PRODUCTS FROM OUR DATABASE THAT THEIR MESSAGE MENTIONS"]
    products = relevant_products(message)
    lines += [product_line(p) for p in products] if products else [NO_DATA_LINE]
    return "\n".join(lines)

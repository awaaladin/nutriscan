"""Deterministic WHO-threshold health scoring and diabetic risk tiering.

This module has no Django or network dependencies on purpose: it is the
single source of truth for health claims made by NutriScan, and must stay
pure/unit-testable. LLM output is explanation-only and must never override
these results (see apps.integrations.llm_explanations).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class HealthLabel(str, Enum):
    GOOD = "Good"
    MODERATE = "Moderate"
    AVOID = "Avoid"
    # Not enough nutrition data to honestly call it Good (see compute_health_score).
    INCOMPLETE = "Incomplete"


class DiabeticRisk(str, Enum):
    SAFE = "Safe"
    MODERATE = "Moderate"
    AVOID = "Avoid"


# Ingredient-list keywords treated as refined-carbohydrate indicators for the
# diabetic risk check. Matching is substring-based over the lowercased
# ingredients text.
REFINED_CARB_KEYWORDS = [
    "sugar",
    "glucose syrup",
    "corn syrup",
    "high fructose corn syrup",
    "maltodextrin",
    "dextrose",
    "white flour",
    "refined flour",
    "invert syrup",
    "fructose",
    "sucrose",
]

# WHO/FSA-style per-100g thresholds. Values at or below `moderate` are "low";
# above `moderate` but at or below `high` are "moderate"; above `high` is "high".
SUGAR_MODERATE_G, SUGAR_HIGH_G = 5.0, 10.0
SATURATED_FAT_MODERATE_G, SATURATED_FAT_HIGH_G = 1.5, 5.0
SODIUM_MODERATE_MG, SODIUM_HIGH_MG = 120.0, 400.0

# Highest score a product with any "high" nutrient can have (the top of Moderate).
HIGH_FLAG_SCORE_CAP = 6

DIABETIC_SUGAR_AVOID_G = 22.5
DIABETIC_SUGAR_MODERATE_G = 10.0


@dataclass
class NutritionFacts:
    """All values are per 100g/100ml, matching Open Food Facts convention."""

    calories_kcal: Optional[float] = None
    sugar_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    carbohydrates_g: Optional[float] = None
    fiber_g: Optional[float] = None
    protein_g: Optional[float] = None


@dataclass
class HealthScoreResult:
    # None when the label is INCOMPLETE: there is no honest number to show.
    score: Optional[int]
    label: HealthLabel
    diabetic_risk: DiabeticRisk
    flags: list = field(default_factory=list)
    insufficient_data: bool = False
    # Which of "sugar", "saturated_fat", "sodium" were not available.
    missing: list = field(default_factory=list)


def _tier(value: Optional[float], moderate: float, high: float):
    """Return (penalty_points, tier_name_or_None). tier is None if value missing."""
    if value is None:
        return 0, None
    if value > high:
        return 3, "high"
    if value > moderate:
        return 1, "moderate"
    return 0, "low"


def compute_diabetic_risk(nutrition: NutritionFacts, ingredients_text: str = "") -> DiabeticRisk:
    ingredients_lower = (ingredients_text or "").lower()
    keyword_hits = sum(1 for kw in REFINED_CARB_KEYWORDS if kw in ingredients_lower)
    sugar = nutrition.sugar_g

    if (sugar is not None and sugar > DIABETIC_SUGAR_AVOID_G) or keyword_hits >= 2:
        return DiabeticRisk.AVOID
    if (sugar is not None and sugar > DIABETIC_SUGAR_MODERATE_G) or keyword_hits >= 1:
        return DiabeticRisk.MODERATE
    return DiabeticRisk.SAFE


SUGAR_LEADING_POSITIONS = 3
_SUGAR_FREE_MARKERS = ("sugar free", "sugar-free", "no sugar", "sugarfree", "without sugar")


def sugar_leads_ingredients(ingredients_text: str) -> bool:
    """True when a sugar-type ingredient is among the first few listed. Labels list
    ingredients by weight, so this means sugar is a major component -- the best
    available hint about sugar when the nutrition table couldn't be read."""
    text = (ingredients_text or "").lower()
    if any(marker in text for marker in _SUGAR_FREE_MARKERS):
        return False
    items, current, depth = [], [], 0
    for char in text:  # split on top-level commas only, so "flour (wheat, sugar)" is one item
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        if char in ",;" and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    items.append("".join(current))
    return any(any(kw in item for kw in REFINED_CARB_KEYWORDS) for item in items[:SUGAR_LEADING_POSITIONS])


def compute_health_score(nutrition: NutritionFacts, ingredients_text: str = "") -> HealthScoreResult:
    flags = []
    penalty = 0
    missing = []

    sugar_penalty, sugar_tier = _tier(nutrition.sugar_g, SUGAR_MODERATE_G, SUGAR_HIGH_G)
    if nutrition.sugar_g is None:
        missing.append("sugar")
    elif sugar_tier != "low":
        flags.append(f"{sugar_tier}_sugar")
    penalty += sugar_penalty

    fat_penalty, fat_tier = _tier(nutrition.saturated_fat_g, SATURATED_FAT_MODERATE_G, SATURATED_FAT_HIGH_G)
    if nutrition.saturated_fat_g is None:
        missing.append("saturated_fat")
    elif fat_tier != "low":
        flags.append(f"{fat_tier}_saturated_fat")
    penalty += fat_penalty

    sodium_penalty, sodium_tier = _tier(nutrition.sodium_mg, SODIUM_MODERATE_MG, SODIUM_HIGH_MG)
    if nutrition.sodium_mg is None:
        missing.append("sodium")
    elif sodium_tier != "low":
        flags.append(f"{sodium_tier}_sodium")
    penalty += sodium_penalty

    score = max(1, min(10, 10 - penalty))

    # A "high" tier on any single nutrient (WHO red: sugar, saturated fat or sodium) must
    # not be averaged away by clean values elsewhere. Without this, a product that is
    # 72% sugar but low in fat and salt scored 7/10 -- "Good". One high flag caps the
    # product at Moderate, and the number is capped at 6 so score and label agree.
    if "high" in (sugar_tier, fat_tier, sodium_tier):
        score = min(score, HIGH_FLAG_SCORE_CAP)

    if score >= 7:
        label = HealthLabel.GOOD
    elif score >= 4:
        label = HealthLabel.MODERATE
    else:
        label = HealthLabel.AVOID

    # A missing nutrient earns no penalty, so unknown data would otherwise look
    # perfect. Missing data can only make a verdict worse, never better, so a
    # product that would score Good is never certified without the full picture --
    # it is "Incomplete" with no number. A Moderate/Avoid verdict stands: the
    # unknowns could only worsen it.
    if "sugar" in missing and sugar_leads_ingredients(ingredients_text):
        flags.append("likely_high_sugar")
    if missing and label == HealthLabel.GOOD:
        return HealthScoreResult(
            score=None,
            label=HealthLabel.INCOMPLETE,
            diabetic_risk=compute_diabetic_risk(nutrition, ingredients_text),
            flags=flags,
            insufficient_data=True,
            missing=missing,
        )

    return HealthScoreResult(
        score=score,
        label=label,
        diabetic_risk=compute_diabetic_risk(nutrition, ingredients_text),
        flags=flags,
        insufficient_data=bool(missing),
        missing=missing,
    )

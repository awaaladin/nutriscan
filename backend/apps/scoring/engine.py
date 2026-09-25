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
    score: int
    label: HealthLabel
    diabetic_risk: DiabeticRisk
    flags: list = field(default_factory=list)
    insufficient_data: bool = False


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
    if score >= 7:
        label = HealthLabel.GOOD
    elif score >= 4:
        label = HealthLabel.MODERATE
    else:
        label = HealthLabel.AVOID

    return HealthScoreResult(
        score=score,
        label=label,
        diabetic_risk=compute_diabetic_risk(nutrition, ingredients_text),
        flags=flags,
        insufficient_data=bool(missing),
    )

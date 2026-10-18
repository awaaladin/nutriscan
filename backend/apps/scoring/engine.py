"""Deterministic WHO-threshold health scoring and diabetic risk tiering.

This module has no Django or network dependencies on purpose: it is the
single source of truth for health claims made by NutriScan, and must stay
pure/unit-testable. LLM output is explanation-only and must never override
these results (see apps.integrations.llm_explanations).

Personal verdicts (diabetes, blood pressure, weight, allergies) live in
apps.scoring.personal and are built on top of what is computed here.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


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
    # Sugar and carbohydrate are both unknown: we can't call it safe, or unsafe.
    UNKNOWN = "Unknown"


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

# "Sugar free", "no added sugar" etc. contain the word "sugar" but mean the opposite;
# counting them made the very products diabetics should choose look worse.
_SUGAR_FREE_PHRASES = re.compile(
    r"sugar[\s-]?free|no added sugars?|no sugars?|without (?:added )?sugars?|zero sugars?|unsweetened"
)
_SUGAR_ALCOHOLS = ("sorbitol", "maltitol", "xylitol", "erythritol", "isomalt", "mannitol", "lactitol")

# WHO/FSA-style per-100g thresholds. Values at or below `moderate` are "low";
# above `moderate` but at or below `high` are "moderate"; above `high` is "high".
SUGAR_MODERATE_G, SUGAR_HIGH_G = 5.0, 10.0
# Drinks are judged per 100 ml and a glass is far more than a bite: a cola at ~10 g/100 ml
# is ~35 g of sugar in a can. Their sugar limits are half those for solid food.
BEVERAGE_SUGAR_MODERATE_G, BEVERAGE_SUGAR_HIGH_G = 2.5, 5.0
SATURATED_FAT_MODERATE_G, SATURATED_FAT_HIGH_G = 1.5, 5.0
SODIUM_MODERATE_MG, SODIUM_HIGH_MG = 120.0, 400.0

# Highest score a product with any "high" nutrient can have (the top of Moderate).
HIGH_FLAG_SCORE_CAP = 6

DIABETIC_SUGAR_AVOID_G = 22.5
DIABETIC_SUGAR_MODERATE_G = 10.0
DIABETIC_BEVERAGE_SUGAR_AVOID_G = 5.0
DIABETIC_BEVERAGE_SUGAR_MODERATE_G = 2.5
# Carbohydrate matters most for blood sugar (carb counting), not only "sugar". Net carbs
# (carbohydrate minus fibre) at or above this need portion care. Never Avoid on its own:
# dry staples (gari, pasta, flour) are high-carb per 100 g but eaten as cooked portions.
DIABETIC_NET_CARB_CAUTION_G = 45.0
HIGH_FIBRE_G = 5.0

_BEVERAGE_NAME = re.compile(
    r"\b(juice|drink|drinks|soda|cola|squash|nectar|smoothie|beverage|lemonade|malta)\b"
)
_NOT_A_BEVERAGE = re.compile(r"\b(powder|mix|sachet|cereal|cube|concentrate|tablet|capsule)\b")
_CARBONATED_WATER = re.compile(r"^(carbonated|sparkling) water")


def is_beverage(name: str, ingredients_text: str = "") -> bool:
    """Best guess that a product is a drink (judged per 100 ml with stricter sugar limits).
    A soft drink lists "carbonated water" first; juices and malt drinks say so in the name.
    Powders and mixes are excluded: they are sold per 100 g of powder."""
    name = (name or "").lower()
    if _NOT_A_BEVERAGE.search(name):
        return False
    if _BEVERAGE_NAME.search(name):
        return True
    return bool(_CARBONATED_WATER.match((ingredients_text or "").lower().strip()))


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
    # Plain-language reasons behind the label and the diabetic risk, for the app to show.
    reasons: list = field(default_factory=list)
    diabetic_reasons: list = field(default_factory=list)
    # True when judged as a drink (per 100 ml, stricter sugar limits).
    beverage: bool = False


def _tier(value: Optional[float], moderate: float, high: float):
    """Return (penalty_points, tier_name_or_None). tier is None if value missing."""
    if value is None:
        return 0, None
    if value > high:
        return 3, "high"
    if value > moderate:
        return 1, "moderate"
    return 0, "low"


def _top_level_items(text: str) -> List[str]:
    """Ingredients split on top-level commas only, so "flour (wheat, sugar)" is one item."""
    items, current, depth = [], [], 0
    for char in text:
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
    return [item.strip() for item in items if item.strip()]


def diabetic_assessment(
    nutrition: NutritionFacts, ingredients_text: str = "", beverage: bool = False
) -> Tuple[DiabeticRisk, List[str]]:
    """Blood-sugar risk of a product and the reasons for it.

    Looks at sugar (stricter for drinks), refined-carbohydrate ingredients (ignoring
    "sugar free" claims), and net carbohydrate (carbs minus fibre). When sugar and
    carbohydrate are both unknown it says Unknown rather than Safe."""
    text = _SUGAR_FREE_PHRASES.sub(" ", (ingredients_text or "").lower())
    hits = [kw for kw in REFINED_CARB_KEYWORDS if kw in text]
    sugar, carbs, fibre = nutrition.sugar_g, nutrition.carbohydrates_g, nutrition.fiber_g
    unit = "ml" if beverage else "g"
    avoid_at = DIABETIC_BEVERAGE_SUGAR_AVOID_G if beverage else DIABETIC_SUGAR_AVOID_G
    moderate_at = DIABETIC_BEVERAGE_SUGAR_MODERATE_G if beverage else DIABETIC_SUGAR_MODERATE_G

    risk, reasons = DiabeticRisk.SAFE, []

    def raise_to(level: DiabeticRisk):
        nonlocal risk
        order = [DiabeticRisk.SAFE, DiabeticRisk.MODERATE, DiabeticRisk.AVOID]
        if order.index(level) > order.index(risk):
            risk = level

    if sugar is not None:
        if sugar > avoid_at:
            raise_to(DiabeticRisk.AVOID)
            reasons.append(f"Sugar is {sugar:g} g per 100 {unit}, very high for blood-sugar control.")
        elif sugar > moderate_at:
            raise_to(DiabeticRisk.MODERATE)
            reasons.append(f"Sugar is {sugar:g} g per 100 {unit}, enough to raise blood sugar.")

    distinct = [kw for kw in hits if not any(kw != other and kw in other for other in hits)]
    if len(hits) >= 2:
        raise_to(DiabeticRisk.AVOID)
        reasons.append(f"Several sugar or refined-carbohydrate ingredients: {', '.join(distinct[:3])}.")
    elif len(hits) == 1:
        raise_to(DiabeticRisk.MODERATE)
        reasons.append(f"Contains {hits[0]}.")

    # Sugar-free sweets and gum list a large "carbohydrate" figure that is mostly sugar
    # alcohols, which raise blood sugar far less than sugar. With sugar itself low, that
    # total is not a reason for caution (the sugar-alcohol note below still applies).
    mostly_polyols = any(alcohol in text for alcohol in _SUGAR_ALCOHOLS) and sugar is not None and sugar <= 5
    if not beverage and carbs is not None and not mostly_polyols:
        net = carbs - (fibre or 0)
        if net >= DIABETIC_NET_CARB_CAUTION_G:
            detail = f"Carbohydrate is {carbs:g} g per 100 g" + (f" ({net:g} g after fibre)" if fibre else "")
            if fibre is not None and fibre >= HIGH_FIBRE_G:
                # Whole grains (oats, whole wheat) are carbohydrate-rich but high in fibre, which
                # slows absorption: worth counting in a portion, not a reason to caution.
                reasons.append(f"{detail}, but high in fibre: count it in your portion.")
            else:
                raise_to(DiabeticRisk.MODERATE)
                reasons.append(f"{detail}: count it in your portion.")
    if fibre is not None and fibre >= HIGH_FIBRE_G and not beverage:
        reasons.append("High in fibre, which slows how fast sugar is absorbed.")
    if any(alcohol in text for alcohol in _SUGAR_ALCOHOLS):
        reasons.append(
            "Contains sugar alcohols: they raise blood sugar less than sugar, but not zero, and can upset the stomach."
        )

    if sugar is None and carbs is None and not hits:
        return DiabeticRisk.UNKNOWN, [
            "Sugar and carbohydrate values are missing, so we can't say whether this suits blood-sugar control."
        ]
    if risk == DiabeticRisk.SAFE and sugar is not None:
        reasons.insert(0, f"Sugar is low ({sugar:g} g per 100 {unit}).")
    return risk, reasons


def compute_diabetic_risk(nutrition: NutritionFacts, ingredients_text: str = "", beverage: bool = False) -> DiabeticRisk:
    return diabetic_assessment(nutrition, ingredients_text, beverage)[0]


SUGAR_LEADING_POSITIONS = 3
_SUGAR_FREE_MARKERS = ("sugar free", "sugar-free", "no sugar", "sugarfree", "without sugar")


def sugar_leads_ingredients(ingredients_text: str) -> bool:
    """True when a sugar-type ingredient is among the first few listed. Labels list
    ingredients by weight, so this means sugar is a major component -- the best
    available hint about sugar when the nutrition table couldn't be read."""
    text = (ingredients_text or "").lower()
    if any(marker in text for marker in _SUGAR_FREE_MARKERS):
        return False
    items = _top_level_items(text)
    return any(any(kw in item for kw in REFINED_CARB_KEYWORDS) for item in items[:SUGAR_LEADING_POSITIONS])


_MISSING_NAMES = {"sugar": "sugar", "saturated_fat": "saturated fat", "sodium": "sodium"}


def compute_health_score(
    nutrition: NutritionFacts, ingredients_text: str = "", beverage: bool = False
) -> HealthScoreResult:
    flags = []
    penalty = 0
    missing = []
    reasons = []
    unit = "ml" if beverage else "g"

    sugar_moderate, sugar_high = (
        (BEVERAGE_SUGAR_MODERATE_G, BEVERAGE_SUGAR_HIGH_G) if beverage else (SUGAR_MODERATE_G, SUGAR_HIGH_G)
    )
    sugar_penalty, sugar_tier = _tier(nutrition.sugar_g, sugar_moderate, sugar_high)
    if nutrition.sugar_g is None:
        missing.append("sugar")
    elif sugar_tier != "low":
        flags.append(f"{sugar_tier}_sugar")
        reasons.append(
            f"Sugar: {nutrition.sugar_g:g} g per 100 {unit} is {sugar_tier} (high is over {sugar_high:g} g)."
        )
    penalty += sugar_penalty

    fat_penalty, fat_tier = _tier(nutrition.saturated_fat_g, SATURATED_FAT_MODERATE_G, SATURATED_FAT_HIGH_G)
    if nutrition.saturated_fat_g is None:
        missing.append("saturated_fat")
    elif fat_tier != "low":
        flags.append(f"{fat_tier}_saturated_fat")
        reasons.append(
            f"Saturated fat: {nutrition.saturated_fat_g:g} g per 100 {unit} is {fat_tier} "
            f"(high is over {SATURATED_FAT_HIGH_G:g} g)."
        )
    penalty += fat_penalty

    sodium_penalty, sodium_tier = _tier(nutrition.sodium_mg, SODIUM_MODERATE_MG, SODIUM_HIGH_MG)
    if nutrition.sodium_mg is None:
        missing.append("sodium")
    elif sodium_tier != "low":
        flags.append(f"{sodium_tier}_sodium")
        reasons.append(
            f"Sodium: {nutrition.sodium_mg:g} mg per 100 {unit} is {sodium_tier} (high is over {SODIUM_HIGH_MG:g} mg)."
        )
    penalty += sodium_penalty

    score = max(1, min(10, 10 - penalty))

    # A "high" tier on any single nutrient (WHO red: sugar, saturated fat or sodium) must
    # not be averaged away by clean values elsewhere. Without this, a product that is
    # 72% sugar but low in fat and salt scored 7/10 -- "Good". One high flag caps the
    # product at Moderate, and the number is capped at 6 so score and label agree.
    highs = [
        name for name, tier in (("sugar", sugar_tier), ("saturated fat", fat_tier), ("sodium", sodium_tier)) if tier == "high"
    ]
    if highs:
        if score > HIGH_FLAG_SCORE_CAP:
            reasons.append(f"High {' and '.join(highs)} caps this product at Moderate, whatever else is good about it.")
        score = min(score, HIGH_FLAG_SCORE_CAP)

    if score >= 7:
        label = HealthLabel.GOOD
    elif score >= 4:
        label = HealthLabel.MODERATE
    else:
        label = HealthLabel.AVOID

    if not missing and not reasons:
        reasons.append("Low in sugar, saturated fat and sodium.")

    # A missing nutrient earns no penalty, so unknown data would otherwise look
    # perfect. Missing data can only make a verdict worse, never better, so a
    # product that would score Good is never certified without the full picture --
    # it is "Incomplete" with no number. A Moderate/Avoid verdict stands: the
    # unknowns could only worsen it.
    if "sugar" in missing and sugar_leads_ingredients(ingredients_text):
        flags.append("likely_high_sugar")
        reasons.append("Sugar is one of the first ingredients, so it is probably high in sugar.")
    if missing:
        names = ", ".join(_MISSING_NAMES[m] for m in missing)
        reasons.append(f"No {names} value on file, so this verdict can only be a minimum.")

    diabetic_risk, diabetic_reasons = diabetic_assessment(nutrition, ingredients_text, beverage)
    if missing and label == HealthLabel.GOOD:
        return HealthScoreResult(
            score=None,
            label=HealthLabel.INCOMPLETE,
            diabetic_risk=diabetic_risk,
            flags=flags,
            insufficient_data=True,
            missing=missing,
            reasons=reasons,
            diabetic_reasons=diabetic_reasons,
            beverage=beverage,
        )

    return HealthScoreResult(
        score=score,
        label=label,
        diabetic_risk=diabetic_risk,
        flags=flags,
        insufficient_data=bool(missing),
        missing=missing,
        reasons=reasons,
        diabetic_reasons=diabetic_reasons,
        beverage=beverage,
    )

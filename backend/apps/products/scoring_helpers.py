"""One way to score a stored product and personalise the result, used by every
endpoint (scan, photo research, history, ask) so they can never disagree."""
from typing import Optional

from apps.scoring.engine import HealthScoreResult, NutritionFacts, compute_health_score, is_beverage
from apps.scoring.personal import Profile, assess_for_profile, parse_allergens

from .models import Product

MISSING_NAMES = {"sugar": "sugar", "saturated_fat": "saturated fat", "sodium": "sodium"}


def facts(product: Product) -> NutritionFacts:
    return NutritionFacts(
        calories_kcal=product.calories_kcal,
        sugar_g=product.sugar_g,
        saturated_fat_g=product.saturated_fat_g,
        sodium_mg=product.sodium_mg,
        carbohydrates_g=product.carbohydrates_g,
        fiber_g=product.fiber_g,
        protein_g=product.protein_g,
    )


def score_product(product: Product) -> HealthScoreResult:
    """The universal health score for a product, judged as a drink when it is one."""
    return compute_health_score(
        facts(product), product.ingredients_text, beverage=is_beverage(product.name, product.ingredients_text)
    )


def profile_for(user) -> Profile:
    """What the user has told us about themselves. A health goal of diabetes, blood
    pressure or weight loss counts even if they didn't tick the matching condition."""
    goal = getattr(user, "primary_goal", "")
    return Profile(
        diabetic=bool(user.is_diabetic) or goal == "diabetes",
        hypertension=bool(user.has_hypertension) or goal == "hypertension",
        weight_loss=goal == "weight_loss",
        allergens=parse_allergens(user.health_notes),
    )


def for_you(user, product: Product, result: HealthScoreResult) -> Optional[dict]:
    """The personal verdict for this user, or None when they haven't told us anything
    that changes how a product should be judged for them."""
    verdict = assess_for_profile(facts(product), product.ingredients_text, profile_for(user), result)
    return verdict.as_dict() if verdict else None


def score_fields(user, product: Product, result: HealthScoreResult) -> dict:
    """The score-related fields every scored response carries."""
    return {
        "score": result.score,
        "label": result.label.value,
        "diabetic_risk": result.diabetic_risk.value,
        "flags": result.flags,
        "insufficient_data": result.insufficient_data,
        "missing_nutrients": [MISSING_NAMES[k] for k in result.missing if k in MISSING_NAMES],
        "reasons": result.reasons,
        "diabetic_reasons": result.diabetic_reasons,
        "beverage": result.beverage,
        "for_you": for_you(user, product, result),
    }

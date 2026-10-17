"""Validating nutrition values that come from a user or from AI reading a label.

Both are untrusted: a typo, a per-serving number entered as per-100g, or a
misread digit would otherwise change the health score everyone sees. So values
are range-checked, converted to per 100g/100ml, cross-checked, and only ever
used to fill blanks -- never to overwrite what we already hold.
"""
from typing import Dict, Optional

# Field -> (min, max) per 100g/100ml. Generous but physically possible: 100 g of
# anything contains at most 100 g of a nutrient, ~900 kcal (pure fat), and salt
# is ~39% sodium so 100 g of salt is ~39,000 mg.
LIMITS = {
    "calories_kcal": (0, 900),
    "sugar_g": (0, 100),
    "saturated_fat_g": (0, 100),
    "sodium_mg": (0, 40000),
    "carbohydrates_g": (0, 100),
    "fiber_g": (0, 100),
    "protein_g": (0, 100),
}


class NutritionInputError(ValueError):
    pass


def per_100g(values: Dict[str, Optional[float]], serving_size_g: Optional[float]) -> Dict[str, float]:
    """Converts per-serving values to per 100g/100ml (a serving of `serving_size_g`)."""
    if not serving_size_g or serving_size_g <= 0 or serving_size_g > 5000:
        raise NutritionInputError("Enter the serving size in grams (or ml) to convert per-serving values.")
    factor = 100.0 / serving_size_g
    return {k: v * factor for k, v in values.items() if v is not None}


def clean_nutrition(values: Dict[str, Optional[float]], strict: bool = True) -> Dict[str, float]:
    """Keeps only known fields with values in range. With `strict` (typed by a
    user) an impossible value raises so they can fix it; otherwise (read by AI) it
    is silently dropped -- a misread should leave a blank, not a wrong number."""
    cleaned = {}
    for field, (low, high) in LIMITS.items():
        value = values.get(field)
        if value is None:
            continue
        if not (low <= value <= high):
            if strict:
                raise NutritionInputError(f"{field.replace('_', ' ')} of {value:g} isn't possible per 100g.")
            continue
        cleaned[field] = round(float(value), 2)

    sugar, carbs = cleaned.get("sugar_g"), cleaned.get("carbohydrates_g")
    if sugar is not None and carbs is not None and sugar > carbs + 0.5:
        if strict:
            raise NutritionInputError("Sugar can't be more than total carbohydrates. Check the two values.")
        cleaned.pop("sugar_g")
        cleaned.pop("carbohydrates_g")
    return cleaned

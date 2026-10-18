"""Personal verdicts: what a product means for THIS user.

The headline health score stays universal so products are comparable. On top of it
this builds a "for you" verdict from the user's own situation -- diabetes, high
blood pressure, a weight-loss goal, and food allergies they noted -- using the same
deterministic rules and facts as the score. Pure logic, no Django.

Two safety rules:
- It only ever *adds* warnings. A product with no allergen found is never described
  as "safe for your allergy": the ingredient list may be incomplete or missing, and
  "may contain traces" labels can't be read.
- Allergies come from free text the user wrote, so parsing is conservative about
  negations ("not allergic to peanuts") and clearly says what it matched.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .engine import (
    BEVERAGE_SUGAR_HIGH_G,
    DiabeticRisk,
    HealthScoreResult,
    NutritionFacts,
    SATURATED_FAT_HIGH_G,
    SODIUM_HIGH_MG,
    SODIUM_MODERATE_MG,
    SUGAR_HIGH_G,
    diabetic_assessment,
)

SUITABLE, CAUTION, AVOID, UNKNOWN = "Suitable", "Caution", "Avoid", "Unknown"
_SEVERITY = {SUITABLE: 0, UNKNOWN: 1, CAUTION: 2, AVOID: 3}

# Energy density worth flagging for someone trying to lose weight (kcal per 100 g/ml).
HIGH_CALORIE_KCAL = 400.0

HEADLINES = {
    AVOID: "Not suitable for you",
    CAUTION: "Be careful with this one",
    UNKNOWN: "We can't tell yet",
    SUITABLE: "No concerns for what you've told us",
}

# group name -> words that mean it in an ingredient list
ALLERGEN_GROUPS: Dict[str, List[str]] = {
    "peanut": ["peanut", "peanuts", "groundnut", "groundnuts", "arachis"],
    "tree nut": ["almond", "cashew", "walnut", "hazelnut", "pistachio", "pecan", "macadamia", "brazil nut", "tree nut"],
    "milk": ["milk", "lactose", "whey", "casein", "caseinate", "cream", "butter", "cheese", "yoghurt", "yogurt", "ghee"],
    "egg": ["egg", "eggs", "albumen", "ovalbumin"],
    "soy": ["soy", "soya", "soybean", "soybeans", "soja"],
    "wheat / gluten": ["wheat", "gluten", "barley", "rye", "semolina", "durum"],
    "fish": ["fish", "anchovy", "anchovies", "tuna", "salmon", "sardine", "cod"],
    "shellfish": ["shellfish", "prawn", "prawns", "shrimp", "crayfish", "crab", "lobster"],
    "sesame": ["sesame", "tahini"],
}
# Words a person writes that map to a group (adds the plain names above).
_ALLERGEN_ALIASES = {"lactose": "milk", "dairy": "milk", "gluten": "wheat / gluten", "nuts": "tree nut", "nut": "tree nut"}
# Phrases that contain an allergen word but aren't that allergen.
_NOT_ALLERGENS = re.compile(r"cocoa butter|shea butter|coconut milk|coconut cream|nutmeg|butternut")
_NEGATION = re.compile(r"\b(?:not|no|never|without|isn't|aren't|don't|doesn't|neither)\b")


@dataclass
class Profile:
    diabetic: bool = False
    hypertension: bool = False
    weight_loss: bool = False
    allergens: List[str] = field(default_factory=list)

    def has_conditions(self) -> bool:
        return self.diabetic or self.hypertension or self.weight_loss or bool(self.allergens)


def _words_to_groups() -> Dict[str, str]:
    mapping = {}
    for group, words in ALLERGEN_GROUPS.items():
        for word in words:
            mapping[word] = group
    mapping.update(_ALLERGEN_ALIASES)
    return mapping


_WORD_TO_GROUP = _words_to_groups()


def parse_allergens(notes: str) -> List[str]:
    """Allergen groups the user says they react to, from free text like
    "Allergic to peanuts and milk. Takes metformin." or "lactose intolerant".
    Looks around each "allerg…"/"intoleran…" for allergen words, within the same
    sentence, and skips statements that negate it ("not allergic to peanuts")."""
    text = (notes or "").lower()
    found: List[str] = []
    for match in re.finditer(r"allerg\w*|intoleran\w*", text):
        start, end = match.start(), match.end()
        sentence_start = max(text.rfind(".", 0, start), text.rfind(";", 0, start), text.rfind("\n", 0, start)) + 1
        before = text[sentence_start:start]
        if _NEGATION.search(before[-35:]):
            continue
        after_match = re.search(r"[.;\n]", text[end:])
        after = text[end : end + (after_match.start() if after_match else len(text))]
        window = before[-40:] + " " + after
        for word in re.findall(r"[a-z]+", window):
            group = _WORD_TO_GROUP.get(word)
            if group and group not in found:
                found.append(group)
    return found


def allergens_in(ingredients_text: str, groups: List[str]) -> Dict[str, List[str]]:
    """For each requested group, the ingredient words found in the list."""
    text = _NOT_ALLERGENS.sub(" ", (ingredients_text or "").lower())
    hits: Dict[str, List[str]] = {}
    for group in groups:
        words = [w for w in ALLERGEN_GROUPS.get(group, []) if re.search(rf"\b{re.escape(w)}\b", text)]
        if words:
            hits[group] = words[:3]
    return hits


@dataclass
class ForYou:
    verdict: str
    headline: str
    reasons: List[str]
    conditions: List[str]

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "headline": self.headline, "reasons": self.reasons, "conditions": self.conditions}


def assess_for_profile(
    nutrition: NutritionFacts,
    ingredients_text: str,
    profile: Profile,
    result: HealthScoreResult,
) -> Optional[ForYou]:
    """The personal verdict, or None when the user has told us nothing that changes
    how a product should be judged for them."""
    if not profile.has_conditions():
        return None

    verdict, reasons, conditions = SUITABLE, [], []

    def note(level: str, reason: Optional[str] = None):
        nonlocal verdict
        if _SEVERITY[level] > _SEVERITY[verdict]:
            verdict = level
        if reason and reason not in reasons:
            reasons.append(reason)

    unit = "ml" if result.beverage else "g"

    if profile.diabetic:
        conditions.append("diabetes")
        risk, risk_reasons = diabetic_assessment(nutrition, ingredients_text, result.beverage)
        level = {
            DiabeticRisk.AVOID: AVOID,
            DiabeticRisk.MODERATE: CAUTION,
            DiabeticRisk.UNKNOWN: UNKNOWN,
            DiabeticRisk.SAFE: SUITABLE,
        }[risk]
        note(level)
        for reason in risk_reasons:
            note(level, f"Diabetes: {reason}")

    if profile.hypertension:
        conditions.append("high blood pressure")
        sodium = nutrition.sodium_mg
        if sodium is None:
            note(UNKNOWN, "High blood pressure: sodium isn't on file, so we can't tell how salty this is.")
        elif sodium > SODIUM_HIGH_MG:
            note(AVOID, f"High blood pressure: sodium is {sodium:g} mg per 100 {unit}, high (salt raises blood pressure).")
        elif sodium > SODIUM_MODERATE_MG:
            note(CAUTION, f"High blood pressure: sodium is {sodium:g} mg per 100 {unit}; keep portions small.")
        else:
            note(SUITABLE, f"High blood pressure: sodium is low ({sodium:g} mg per 100 {unit}).")

    if profile.weight_loss:
        conditions.append("weight loss")
        sugar_high = BEVERAGE_SUGAR_HIGH_G if result.beverage else SUGAR_HIGH_G
        if nutrition.calories_kcal is not None and nutrition.calories_kcal >= HIGH_CALORIE_KCAL:
            note(CAUTION, f"Weight loss: {nutrition.calories_kcal:g} kcal per 100 {unit} is very energy-dense.")
        if nutrition.sugar_g is not None and nutrition.sugar_g > sugar_high:
            note(CAUTION, f"Weight loss: high in sugar ({nutrition.sugar_g:g} g per 100 {unit}) adds calories without filling you up.")
        if nutrition.saturated_fat_g is not None and nutrition.saturated_fat_g > SATURATED_FAT_HIGH_G:
            note(CAUTION, f"Weight loss: high in saturated fat ({nutrition.saturated_fat_g:g} g per 100 {unit}).")

    if profile.allergens:
        for group in profile.allergens:
            conditions.append(f"{group} allergy")
        if not (ingredients_text or "").strip():
            note(CAUTION, "Allergies: there's no ingredient list on file, so we can't check this against your allergies.")
        else:
            for group, words in allergens_in(ingredients_text, profile.allergens).items():
                note(AVOID, f"Allergy: contains {', '.join(words)} (you noted a {group} allergy). Check the pack too.")

    if verdict == SUITABLE and not reasons:
        reasons.append("Nothing in this product conflicts with what you've told us.")
    return ForYou(verdict=verdict, headline=HEADLINES[verdict], reasons=reasons, conditions=conditions)

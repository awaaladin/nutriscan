import unittest

from apps.scoring.engine import (
    DiabeticRisk,
    HealthLabel,
    NutritionFacts,
    compute_health_score,
    diabetic_assessment,
    is_beverage,
)
from apps.scoring.personal import (
    AVOID,
    CAUTION,
    SUITABLE,
    UNKNOWN,
    Profile,
    allergens_in,
    assess_for_profile,
    parse_allergens,
)

GUM = NutritionFacts(sugar_g=72.1, saturated_fat_g=0.0, sodium_mg=9.0, calories_kcal=380.0, carbohydrates_g=97.0)
OATS = NutritionFacts(sugar_g=1.0, saturated_fat_g=1.2, sodium_mg=5.0, calories_kcal=370.0, carbohydrates_g=60.0, fiber_g=10.0)


def verdict(nutrition, ingredients, profile, beverage=False):
    result = compute_health_score(nutrition, ingredients, beverage=beverage)
    return assess_for_profile(nutrition, ingredients, profile, result)


class DiabeticAssessmentTests(unittest.TestCase):
    def test_sugar_free_claims_are_not_counted_as_sugar(self):
        for ingredients in ("Sorbitol, gum base, sugar free flavours", "Water, no added sugar, orange", "Sugar-free cocoa"):
            risk, _ = diabetic_assessment(NutritionFacts(sugar_g=0.5), ingredients)
            self.assertEqual(risk, DiabeticRisk.SAFE, ingredients)

    def test_real_sugar_ingredients_still_count(self):
        risk, reasons = diabetic_assessment(NutritionFacts(sugar_g=3), "Wheat flour, sugar, glucose syrup")
        self.assertEqual(risk, DiabeticRisk.AVOID)
        self.assertTrue(any("sugar" in r.lower() for r in reasons))

    def test_drinks_are_judged_against_stricter_sugar_limits(self):
        self.assertEqual(diabetic_assessment(NutritionFacts(sugar_g=6), "", beverage=True)[0], DiabeticRisk.AVOID)
        self.assertEqual(diabetic_assessment(NutritionFacts(sugar_g=6), "", beverage=False)[0], DiabeticRisk.SAFE)

    def test_cola_scores_as_high_sugar_because_it_is_a_drink(self):
        cola = compute_health_score(NutritionFacts(sugar_g=10.6, saturated_fat_g=0, sodium_mg=10), "", beverage=True)
        self.assertIn("high_sugar", cola.flags)
        self.assertEqual(cola.label, HealthLabel.MODERATE)

    def test_a_drink_at_six_grams_is_high_but_the_same_number_in_food_is_only_moderate(self):
        drink = compute_health_score(NutritionFacts(sugar_g=6, saturated_fat_g=0, sodium_mg=10), "", beverage=True)
        food = compute_health_score(NutritionFacts(sugar_g=6, saturated_fat_g=0, sodium_mg=10), "", beverage=False)
        self.assertIn("high_sugar", drink.flags)
        self.assertIn("moderate_sugar", food.flags)

    def test_high_net_carbohydrate_needs_portion_care_but_is_never_avoid_alone(self):
        bread = NutritionFacts(sugar_g=3, carbohydrates_g=50, fiber_g=2)
        risk, reasons = diabetic_assessment(bread, "Wheat flour, water, yeast")
        self.assertEqual(risk, DiabeticRisk.MODERATE)
        self.assertTrue(any("portion" in r for r in reasons))
        staple = NutritionFacts(sugar_g=1, carbohydrates_g=85, fiber_g=3)
        self.assertEqual(diabetic_assessment(staple, "Cassava")[0], DiabeticRisk.MODERATE)

    def test_fibre_offsets_carbohydrate_and_is_noted(self):
        risk, reasons = diabetic_assessment(NutritionFacts(sugar_g=1, carbohydrates_g=50, fiber_g=10), "Oats")
        self.assertEqual(risk, DiabeticRisk.SAFE)
        self.assertTrue(any("fibre" in r for r in reasons))

    def test_unknown_sugar_and_carbs_is_unknown_not_safe(self):
        risk, reasons = diabetic_assessment(NutritionFacts(), "Water, flavour")
        self.assertEqual(risk, DiabeticRisk.UNKNOWN)
        self.assertTrue(reasons)

    def test_sugar_free_gum_is_not_penalised_for_its_polyol_carbohydrate(self):
        # ~65 g "carbohydrate" that is almost all sorbitol/maltitol, with 0.5 g sugar
        gum = NutritionFacts(sugar_g=0.5, carbohydrates_g=65, fiber_g=0)
        risk, reasons = diabetic_assessment(gum, "Sorbitol, gum base, maltitol, aspartame, sugar free")
        self.assertEqual(risk, DiabeticRisk.SAFE)
        self.assertTrue(any("sugar alcohols" in r for r in reasons))

    def test_polyols_do_not_excuse_a_product_that_also_has_real_sugar(self):
        sweet = NutritionFacts(sugar_g=40, carbohydrates_g=80)
        self.assertEqual(diabetic_assessment(sweet, "Sugar, sorbitol")[0], DiabeticRisk.AVOID)

    def test_sugar_alcohols_are_called_out(self):
        _, reasons = diabetic_assessment(NutritionFacts(sugar_g=0), "Maltitol, gum base")
        self.assertTrue(any("sugar alcohols" in r for r in reasons))


class BeverageDetectionTests(unittest.TestCase):
    def test_drinks(self):
        for name, ingredients in (
            ("Coca-Cola Classic", ""), ("Fanta Orange", "Carbonated water, sugar"), ("Capri-Sun Juice Drink", ""),
            ("Malta Guinness", ""), ("Chivita Pineapple Juice", ""),
        ):
            self.assertTrue(is_beverage(name, ingredients), name)

    def test_foods_powders_and_sauces_are_not_drinks(self):
        for name, ingredients in (
            ("Milo chocolate malt drink powder", ""), ("Tomato paste", "Water, tomatoes"), ("Energy bar", "Oats, honey"),
            ("Indomie noodles", "Wheat flour"), ("Drink mix sachet", ""),
        ):
            self.assertFalse(is_beverage(name, ingredients), name)


class ReasonsTests(unittest.TestCase):
    def test_the_gum_explains_itself(self):
        result = compute_health_score(GUM, "Sugar, gum base, glucose syrup")
        text = " ".join(result.reasons)
        self.assertIn("Sugar: 72.1 g per 100 g is high", text)
        self.assertIn("caps this product at Moderate", text)
        self.assertTrue(result.diabetic_reasons)

    def test_a_clean_product_says_so(self):
        result = compute_health_score(NutritionFacts(sugar_g=1, saturated_fat_g=0.1, sodium_mg=10), "Water")
        self.assertEqual(result.reasons, ["Low in sugar, saturated fat and sodium."])

    def test_missing_data_is_explained(self):
        result = compute_health_score(NutritionFacts(sugar_g=1), "Water")
        self.assertTrue(any("No saturated fat, sodium value" in r for r in result.reasons))


class ParseAllergensTests(unittest.TestCase):
    def test_common_phrasings(self):
        self.assertEqual(parse_allergens("Allergic to peanuts and milk. Takes metformin."), ["peanut", "milk"])
        self.assertEqual(parse_allergens("I have a peanut allergy"), ["peanut"])
        self.assertEqual(parse_allergens("lactose intolerant"), ["milk"])
        self.assertEqual(parse_allergens("Gluten intolerance; takes aspirin"), ["wheat / gluten"])
        self.assertEqual(parse_allergens("allergic to shellfish"), ["shellfish"])

    def test_negations_and_unrelated_notes_find_nothing(self):
        for notes in ("I am not allergic to peanuts", "no allergies", "Takes metformin and amlodipine", "", None):
            self.assertEqual(parse_allergens(notes), [], notes)

    def test_other_sentences_are_not_pulled_in(self):
        # the peanut word is in a different sentence from the allergy
        self.assertEqual(parse_allergens("Allergic to eggs. I like peanuts."), ["egg"])

    def test_ingredient_matching_is_by_whole_word_and_skips_lookalikes(self):
        self.assertIn("peanut", allergens_in("Sugar, peanut oil, salt", ["peanut", "milk"]))
        self.assertEqual(allergens_in("Cocoa butter, sugar, shea butter", ["milk"]), {})
        self.assertEqual(allergens_in("Coconut milk, rice", ["milk"]), {})
        self.assertEqual(allergens_in("Peanutty flavour", ["peanut"]), {})  # not the word "peanut"


class ForYouTests(unittest.TestCase):
    def test_no_conditions_means_no_personal_verdict(self):
        self.assertIsNone(verdict(GUM, "Sugar", Profile()))

    def test_diabetic_and_a_sugary_gum_is_avoid_with_reasons(self):
        fy = verdict(GUM, "Sugar, gum base, glucose syrup", Profile(diabetic=True))
        self.assertEqual(fy.verdict, AVOID)
        self.assertEqual(fy.headline, "Not suitable for you")
        self.assertEqual(fy.conditions, ["diabetes"])
        self.assertTrue(all(r.startswith("Diabetes:") for r in fy.reasons))

    def test_diabetic_and_low_sugar_oats_is_suitable(self):
        self.assertEqual(verdict(OATS, "Whole oats", Profile(diabetic=True)).verdict, SUITABLE)

    def test_diabetic_with_nothing_known_is_unknown(self):
        self.assertEqual(verdict(NutritionFacts(), "Water", Profile(diabetic=True)).verdict, UNKNOWN)

    def test_high_blood_pressure_follows_sodium(self):
        cases = ((900, AVOID), (200, CAUTION), (50, SUITABLE), (None, UNKNOWN))
        for sodium, expected in cases:
            nutrition = NutritionFacts(sugar_g=1, saturated_fat_g=0.5, sodium_mg=sodium)
            self.assertEqual(verdict(nutrition, "x", Profile(hypertension=True)).verdict, expected, sodium)

    def test_weight_loss_flags_energy_dense_and_sugary_food_as_caution(self):
        fy = verdict(NutritionFacts(sugar_g=2, saturated_fat_g=1, sodium_mg=10, calories_kcal=520), "Nuts", Profile(weight_loss=True))
        self.assertEqual(fy.verdict, CAUTION)
        self.assertEqual(verdict(OATS, "Oats", Profile(weight_loss=True)).verdict, SUITABLE)

    def test_an_allergen_in_the_ingredients_is_avoid(self):
        fy = verdict(OATS, "Oats, peanut oil, salt", Profile(allergens=["peanut"]))
        self.assertEqual(fy.verdict, AVOID)
        self.assertIn("peanut", fy.reasons[0])
        self.assertEqual(fy.conditions, ["peanut allergy"])

    def test_without_an_ingredient_list_allergies_cannot_be_checked(self):
        fy = verdict(OATS, "", Profile(allergens=["peanut"]))
        self.assertEqual(fy.verdict, CAUTION)
        self.assertIn("can't check", fy.reasons[0])

    def test_no_allergen_found_never_claims_the_product_is_safe_for_the_allergy(self):
        fy = verdict(OATS, "Whole oats", Profile(allergens=["peanut"]))
        self.assertEqual(fy.verdict, SUITABLE)
        for reason in fy.reasons:
            self.assertNotIn("safe", reason.lower())
            self.assertNotIn("allergen-free", reason.lower())

    def test_the_worst_condition_wins_and_all_are_listed(self):
        fy = verdict(GUM, "Sugar, peanut", Profile(diabetic=True, hypertension=True, allergens=["peanut"]))
        self.assertEqual(fy.verdict, AVOID)
        self.assertEqual(fy.conditions, ["diabetes", "high blood pressure", "peanut allergy"])
        self.assertTrue(any(r.startswith("Allergy:") for r in fy.reasons))
        self.assertTrue(any(r.startswith("Diabetes:") for r in fy.reasons))


if __name__ == "__main__":
    unittest.main()

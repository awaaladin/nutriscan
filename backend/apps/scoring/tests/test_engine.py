import unittest

from apps.scoring.engine import (
    DiabeticRisk,
    HealthLabel,
    NutritionFacts,
    compute_diabetic_risk,
    compute_health_score,
    sugar_leads_ingredients,
)


class ComputeHealthScoreTests(unittest.TestCase):
    def test_low_sugar_low_sodium_is_good(self):
        nutrition = NutritionFacts(sugar_g=2, saturated_fat_g=0.5, sodium_mg=50)
        result = compute_health_score(nutrition)
        self.assertEqual(result.label, HealthLabel.GOOD)
        self.assertEqual(result.score, 10)
        self.assertFalse(result.insufficient_data)

    def test_high_sugar_and_sodium_is_avoid(self):
        nutrition = NutritionFacts(sugar_g=25, saturated_fat_g=8, sodium_mg=600)
        result = compute_health_score(nutrition)
        self.assertEqual(result.label, HealthLabel.AVOID)
        self.assertIn("high_sugar", result.flags)
        self.assertIn("high_sodium", result.flags)
        self.assertIn("high_saturated_fat", result.flags)

    def test_moderate_tier(self):
        # high sugar (-3) + moderate saturated fat (-1) = score 6 -> Moderate
        nutrition = NutritionFacts(sugar_g=12, saturated_fat_g=2, sodium_mg=50)
        result = compute_health_score(nutrition)
        self.assertEqual(result.label, HealthLabel.MODERATE)

    def test_missing_data_is_never_certified_good(self):
        # What looks perfect on the data we have can't be called Good while sugar is unknown.
        nutrition = NutritionFacts(sugar_g=None, saturated_fat_g=1, sodium_mg=100)
        result = compute_health_score(nutrition)
        self.assertTrue(result.insufficient_data)
        self.assertEqual(result.label, HealthLabel.INCOMPLETE)
        self.assertIsNone(result.score)
        self.assertEqual(result.missing, ["sugar"])

    def test_no_nutrition_data_at_all_is_incomplete_not_ten_out_of_ten(self):
        result = compute_health_score(NutritionFacts(), "sugar, gum base, glucose syrup")
        self.assertEqual(result.label, HealthLabel.INCOMPLETE)
        self.assertIsNone(result.score)
        self.assertEqual(result.missing, ["sugar", "saturated_fat", "sodium"])

    def test_known_bad_stays_bad_even_with_other_data_missing(self):
        # Unknown sodium could only make this worse, so the verdict stands, marked partial.
        nutrition = NutritionFacts(sugar_g=30, saturated_fat_g=8, sodium_mg=None)
        result = compute_health_score(nutrition)
        self.assertEqual(result.label, HealthLabel.MODERATE)  # 10 - 3 (sugar) - 3 (sat fat) = 4
        self.assertEqual(result.score, 4)
        self.assertTrue(result.insufficient_data)
        self.assertEqual(result.missing, ["sodium"])

    def test_complete_data_is_unchanged(self):
        result = compute_health_score(NutritionFacts(sugar_g=2, saturated_fat_g=0.5, sodium_mg=50))
        self.assertEqual((result.label, result.score, result.missing), (HealthLabel.GOOD, 10, []))

    def test_sugar_leading_the_ingredients_is_flagged_when_sugar_is_unknown(self):
        result = compute_health_score(NutritionFacts(), "Sugar, gum base, glucose syrup, menthol")
        self.assertIn("likely_high_sugar", result.flags)

    def test_sugar_late_in_the_list_or_sugar_free_is_not_flagged(self):
        late = compute_health_score(NutritionFacts(), "Water, flour, salt, yeast, sugar")
        self.assertNotIn("likely_high_sugar", late.flags)
        free = compute_health_score(NutritionFacts(), "Sugar free: sorbitol, gum base, aspartame")
        self.assertNotIn("likely_high_sugar", free.flags)

    def test_sugar_hint_is_not_added_when_sugar_is_known(self):
        result = compute_health_score(NutritionFacts(sugar_g=1, saturated_fat_g=0, sodium_mg=0), "Sugar, water")
        self.assertNotIn("likely_high_sugar", result.flags)

    def test_brackets_do_not_split_an_ingredient(self):
        # "wheat flour (wheat, sugar)" is a single leading ingredient, and sugar is inside it
        self.assertTrue(sugar_leads_ingredients("Wheat flour (wheat, sugar), water, salt"))
        self.assertFalse(sugar_leads_ingredients("Water, salt, oil, yeast, flour (wheat, sugar)"))

    def test_score_never_drops_below_one(self):
        nutrition = NutritionFacts(sugar_g=100, saturated_fat_g=100, sodium_mg=5000)
        result = compute_health_score(nutrition)
        self.assertEqual(result.score, 1)


class DiabeticRiskTests(unittest.TestCase):
    def test_safe_low_sugar_no_keywords(self):
        nutrition = NutritionFacts(sugar_g=2)
        self.assertEqual(compute_diabetic_risk(nutrition, "water, salt"), DiabeticRisk.SAFE)

    def test_avoid_high_sugar(self):
        nutrition = NutritionFacts(sugar_g=30)
        self.assertEqual(compute_diabetic_risk(nutrition, ""), DiabeticRisk.AVOID)

    def test_avoid_multiple_refined_carb_keywords(self):
        nutrition = NutritionFacts(sugar_g=3)
        ingredients = "wheat flour, sugar, glucose syrup, salt"
        self.assertEqual(compute_diabetic_risk(nutrition, ingredients), DiabeticRisk.AVOID)

    def test_moderate_single_keyword(self):
        nutrition = NutritionFacts(sugar_g=3)
        ingredients = "wheat flour, maltodextrin, salt"
        self.assertEqual(compute_diabetic_risk(nutrition, ingredients), DiabeticRisk.MODERATE)

    def test_moderate_sugar_without_keywords(self):
        nutrition = NutritionFacts(sugar_g=15)
        self.assertEqual(compute_diabetic_risk(nutrition, "water, salt"), DiabeticRisk.MODERATE)


if __name__ == "__main__":
    unittest.main()

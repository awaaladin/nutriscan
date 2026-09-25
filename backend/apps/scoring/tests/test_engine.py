import unittest

from apps.scoring.engine import (
    DiabeticRisk,
    HealthLabel,
    NutritionFacts,
    compute_diabetic_risk,
    compute_health_score,
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

    def test_missing_data_is_flagged_but_still_scored(self):
        nutrition = NutritionFacts(sugar_g=None, saturated_fat_g=1, sodium_mg=100)
        result = compute_health_score(nutrition)
        self.assertTrue(result.insufficient_data)
        self.assertEqual(result.score, 10)

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

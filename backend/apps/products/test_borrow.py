from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.scans.models import Scan

from .identify_helpers import borrow_nutrition, similar_products_with_nutrition
from .models import Product

User = get_user_model()

COMPLETE = {"sugar_g": 72.1, "saturated_fat_g": 0.0, "sodium_mg": 9.0, "calories_kcal": 380.0}


def gum(barcode, name="Fresh Action Chewing Gum Menthol-Eucalyptus Flavour", **extra):
    fields = {"name": name, "brand": "Mentos", "source": "ai_vision", "is_estimated": True,
              "nafdac_number": "A8-109873", "ingredients_text": "Sugar, gum base, glucose syrup"}
    fields.update(extra)
    return Product.objects.create(barcode=barcode, **fields)


class BorrowNutritionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)

    def test_empty_copy_borrows_from_a_copy_with_the_same_nafdac_number(self):
        gum("6154000254667", name="Fresh Action Menthol Eucalyptus Chewing Gum", **COMPLETE)
        empty = gum("6154000256692")
        self.assertTrue(borrow_nutrition(empty))
        empty.refresh_from_db()
        self.assertEqual((empty.sugar_g, empty.sodium_mg, empty.calories_kcal), (72.1, 9.0, 380.0))
        self.assertTrue(empty.is_estimated)

    def test_scanning_the_empty_copy_now_gives_it_a_real_score_with_no_user_action(self):
        gum("6154000254667", name="Fresh Action Menthol Eucalyptus Chewing Gum", **COMPLETE)
        gum("6154000256692")
        resp = self.client.post(reverse("scan"), {"barcode": "6154000256692"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotEqual(resp.data["label"], "Incomplete")
        self.assertIsNotNone(resp.data["score"])
        self.assertIn("high_sugar", resp.data["flags"])
        self.assertEqual(resp.data["missing_nutrients"], [])

    def test_matches_by_similar_name_and_brand_when_there_is_no_nafdac_number(self):
        gum("111", name="Fresh Action Menthol Eucalyptus Chewing Gum", nafdac_number="", **COMPLETE)
        empty = gum("222", nafdac_number="")
        self.assertEqual([p.barcode for p in similar_products_with_nutrition(empty)], ["111"])

    def test_different_products_are_never_mixed_up(self):
        gum("111", name="Orbit Spearmint Gum", nafdac_number="B1-2222", **COMPLETE)
        empty = gum("222")
        self.assertFalse(borrow_nutrition(empty))  # different NAFDAC number, different name
        empty.refresh_from_db()
        self.assertIsNone(empty.sugar_g)

    def test_same_name_under_a_different_brand_is_not_a_match(self):
        gum("111", brand="Orbit", nafdac_number="", **COMPLETE)
        empty = gum("222", nafdac_number="")
        self.assertFalse(borrow_nutrition(empty))

    def test_a_twin_with_barely_any_data_is_not_worth_borrowing_from(self):
        gum("111", sugar_g=50.0)  # only one of the three key nutrients
        self.assertFalse(borrow_nutrition(gum("222")))

    def test_existing_values_are_never_overwritten(self):
        gum("111", **COMPLETE)
        mine = gum("222", sugar_g=2.0)
        borrow_nutrition(mine)
        mine.refresh_from_db()
        self.assertEqual(mine.sugar_g, 2.0)  # kept
        self.assertEqual(mine.sodium_mg, 9.0)  # blank, so filled

    def test_complete_products_are_left_alone(self):
        gum("111", **COMPLETE)
        full = gum("222", sugar_g=1, saturated_fat_g=1, sodium_mg=1)
        self.assertFalse(borrow_nutrition(full))

    def test_medicine_is_never_filled_from_food(self):
        gum("111", **COMPLETE)
        med = gum("222", product_type="medicine")
        self.assertFalse(borrow_nutrition(med))

    def test_verified_data_is_preferred_over_estimated(self):
        gum("111", is_estimated=True, **{**COMPLETE, "sugar_g": 99.0})
        gum("222", is_estimated=False, source="off", **COMPLETE)
        empty = gum("333")
        borrow_nutrition(empty)
        empty.refresh_from_db()
        self.assertEqual(empty.sugar_g, 72.1)  # from the verified copy


class HistoryShowsCurrentVerdictTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)

    def test_an_old_good_ten_out_of_ten_is_corrected_to_incomplete(self):
        empty = gum("6154000256692")
        # saved back when missing data scored as a perfect 10
        Scan.objects.create(user=self.user, product=empty, score=10, label="Good", diabetic_risk="Safe", flags=[])
        row = self.client.get(reverse("history")).data[0]
        self.assertEqual(row["label"], "Incomplete")
        self.assertIsNone(row["score"])
        self.assertEqual(row["diabetic_risk"], "Avoid")

    def test_history_reflects_nutrition_added_later(self):
        product = gum("6154000256692")
        Scan.objects.create(user=self.user, product=product, score=0, label="Incomplete", diabetic_risk="Avoid", flags=[])
        for field, value in COMPLETE.items():
            setattr(product, field, value)
        product.save()
        row = self.client.get(reverse("history")).data[0]
        self.assertNotEqual(row["label"], "Incomplete")
        self.assertIsNotNone(row["score"])

    def test_medicine_rows_are_left_as_they_are(self):
        med = gum("999", product_type="medicine")
        Scan.objects.create(user=self.user, product=med, score=5, label="Moderate", diabetic_risk="Safe", flags=[])
        self.assertEqual(self.client.get(reverse("history")).data[0]["label"], "Moderate")

import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.integrations.vision_identify import IdentifyError
from apps.scans.models import Scan

from .models import Product
from .nutrition_input import NutritionInputError, clean_nutrition, per_100g

User = get_user_model()
EXTRACT = "apps.products.complete_view.extract_nutrition_from_images"
BARCODE = "6154000256692"


def _png(name="n.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class NutritionInputTests(SimpleTestCase):
    def test_per_serving_is_converted_to_per_100g(self):
        # 15 g serving with 3 g sugar -> 20 g per 100 g
        self.assertEqual(per_100g({"sugar_g": 3.0}, 15)["sugar_g"], 20.0)

    def test_per_serving_needs_a_serving_size(self):
        for size in (None, 0, -5):
            with self.assertRaises(NutritionInputError):
                per_100g({"sugar_g": 3.0}, size)

    def test_impossible_values_rejected_when_typed(self):
        for bad in ({"sugar_g": 120}, {"calories_kcal": 5000}, {"sodium_mg": -1}, {"protein_g": 101}):
            with self.assertRaises(NutritionInputError):
                clean_nutrition(bad, strict=True)

    def test_impossible_values_dropped_when_read_by_ai(self):
        self.assertEqual(clean_nutrition({"sugar_g": 120, "protein_g": 5}, strict=False), {"protein_g": 5})

    def test_sugar_cannot_exceed_carbohydrates(self):
        with self.assertRaises(NutritionInputError):
            clean_nutrition({"sugar_g": 30, "carbohydrates_g": 10}, strict=True)
        self.assertEqual(clean_nutrition({"sugar_g": 30, "carbohydrates_g": 10}, strict=False), {})

    def test_unknown_fields_and_nones_are_ignored(self):
        self.assertEqual(clean_nutrition({"sugar_g": None, "bogus": 5}), {})


class IncompleteScoreTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(
            barcode=BARCODE, name="Gum", source="ai_vision", is_estimated=True,
            ingredients_text="Sugar, gum base, glucose syrup, menthol",
        )

    def test_a_product_with_no_nutrition_is_incomplete_not_ten_out_of_ten(self):
        resp = self.client.post(reverse("scan"), {"barcode": BARCODE}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["label"], "Incomplete")
        self.assertIsNone(resp.data["score"])
        self.assertTrue(resp.data["insufficient_data"])
        self.assertEqual(resp.data["missing_nutrients"], ["sugar", "saturated fat", "sodium"])
        self.assertIn("likely_high_sugar", resp.data["flags"])
        self.assertEqual(resp.data["diabetic_risk"], "Avoid")  # still from the ingredients

    def test_the_scan_is_recorded_and_history_shows_no_score(self):
        self.client.post(reverse("scan"), {"barcode": BARCODE}, format="json")
        self.assertEqual(Scan.objects.get().score, 0)  # stored as 0 = no score
        history = self.client.get(reverse("history")).data
        self.assertEqual(history[0]["label"], "Incomplete")
        self.assertIsNone(history[0]["score"])

    def test_no_ai_call_is_spent_explaining_a_score_that_does_not_exist(self):
        with patch("apps.products.views.get_explanation_provider") as provider:
            resp = self.client.post(reverse("scan"), {"barcode": BARCODE}, format="json")
        provider.assert_not_called()
        self.assertIn("can't give", resp.data["explanation"])
        self.assertIn("sugar, saturated fat, sodium", resp.data["explanation"])


class CompleteProductTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(
            barcode=BARCODE, name="Gum", source="ai_vision", is_estimated=True,
            ingredients_text="Sugar, gum base, glucose syrup",
        )
        self.url = reverse("product-complete", args=[BARCODE])

    def _post(self, data, **kwargs):
        return self.client.post(self.url, data, format="json", **kwargs)

    def test_typed_values_complete_the_product_and_give_it_a_real_score(self):
        resp = self._post({"sugar_g": 60, "saturated_fat_g": 0, "sodium_mg": 5, "carbohydrates_g": 90})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["source"], "completed")
        self.assertIsNotNone(resp.data["score"])
        self.assertEqual(resp.data["missing_nutrients"], [])
        self.assertIn("high_sugar", resp.data["flags"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.sugar_g, 60)
        self.assertTrue(self.product.is_estimated)

    def test_existing_values_are_never_overwritten(self):
        self.product.sugar_g = 2.0
        self.product.save()
        self._post({"sugar_g": 99, "sodium_mg": 50})
        self.product.refresh_from_db()
        self.assertEqual(self.product.sugar_g, 2.0)  # kept
        self.assertEqual(self.product.sodium_mg, 50)  # blank, so filled

    def test_existing_ingredients_are_never_overwritten(self):
        self._post({"sugar_g": 1, "ingredients_text": "Something else"})
        self.product.refresh_from_db()
        self.assertEqual(self.product.ingredients_text, "Sugar, gum base, glucose syrup")

    def test_per_serving_values_are_converted(self):
        self._post({"sugar_g": 3, "per_serving": True, "serving_size_g": 15})
        self.product.refresh_from_db()
        self.assertEqual(self.product.sugar_g, 20.0)

    def test_per_serving_without_a_size_is_rejected(self):
        resp = self._post({"sugar_g": 3, "per_serving": True})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["reason"], "bad_values")

    def test_impossible_values_are_rejected_and_nothing_is_saved(self):
        resp = self._post({"sugar_g": 150})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertIsNone(self.product.sugar_g)

    def test_sugar_above_carbohydrates_is_rejected(self):
        resp = self._post({"sugar_g": 40, "carbohydrates_g": 10})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sending_nothing_explains_what_to_do(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["reason"], "nothing_to_add")

    def test_unknown_product(self):
        resp = self.client.post(reverse("product-complete", args=["999"]), {"sugar_g": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_barcode_variants_find_the_product(self):
        resp = self.client.post(reverse("product-complete", args=["0" + BARCODE]), {"sugar_g": 1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_photo_of_the_nutrition_table_is_read_and_applied(self):
        read = {"found": True, "sugar_g": 55.0, "saturated_fat_g": 0.0, "sodium_mg": 8.0, "nafdac_number": "a8-109873"}
        with patch(EXTRACT, return_value=read) as extract:
            resp = self.client.post(self.url, {"images": [_png()]}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(extract.call_count, 1)
        self.product.refresh_from_db()
        self.assertEqual((self.product.sugar_g, self.product.sodium_mg), (55.0, 8.0))
        self.assertEqual(self.product.nafdac_number, "A8-109873")

    def test_misread_values_from_a_photo_are_dropped_not_saved(self):
        read = {"found": True, "sugar_g": 5000.0, "sodium_mg": 8.0}
        with patch(EXTRACT, return_value=read):
            self.client.post(self.url, {"images": [_png()]}, format="multipart")
        self.product.refresh_from_db()
        self.assertIsNone(self.product.sugar_g)
        self.assertEqual(self.product.sodium_mg, 8.0)

    def test_typed_values_win_over_what_the_ai_read(self):
        with patch(EXTRACT, return_value={"found": True, "sugar_g": 10.0, "sodium_mg": 8.0}):
            self.client.post(self.url, {"images": [_png()], "sugar_g": "12"}, format="multipart")
        self.product.refresh_from_db()
        self.assertEqual(self.product.sugar_g, 12.0)
        self.assertEqual(self.product.sodium_mg, 8.0)

    def test_unreadable_photo_asks_for_a_retake_with_a_specific_reason(self):
        error = IdentifyError("no_nutrition_found", "No readable nutrition table.", retake=True)
        with patch(EXTRACT, side_effect=error):
            resp = self.client.post(self.url, {"images": [_png()]}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(resp.data["reason"], "no_nutrition_found")
        self.assertTrue(resp.data["retake"])

    def test_ai_outage_still_completes_from_typed_values(self):
        with patch(EXTRACT, side_effect=IdentifyError("ai_quota_daily", "Daily limit.")):
            resp = self.client.post(self.url, {"images": [_png()], "sugar_g": "9"}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.sugar_g, 9.0)

    def test_ai_outage_with_nothing_typed_reports_the_reason(self):
        with patch(EXTRACT, side_effect=IdentifyError("ai_quota_daily", "Daily limit.")):
            resp = self.client.post(self.url, {"images": [_png()]}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(resp.data["reason"], "ai_quota_daily")

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._post({"sugar_g": 1}).status_code, status.HTTP_401_UNAUTHORIZED)

import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.integrations.vision_identify import IdentifyError

from .models import Product

User = get_user_model()

AI = "apps.products.identify_view.identify_product_from_images"
GOOD_BARCODE = "6001068591206"  # valid GS1 checksum

AI_RESULT = {
    "identified": True,
    "name": "Golden Morn",
    "brand": "Nestle",
    "product_type": "food",
    "confidence": 0.9,
    "barcode": None,
    "nafdac_number": "a4-1234",
    "ingredients_text": "Maize, sugar, soy",
    "calories_kcal": 380.0,
    "sugar_g": 18.0,
    "saturated_fat_g": 1.0,
    "sodium_mg": 150.0,
    "carbohydrates_g": 80.0,
    "fiber_g": 4.0,
    "protein_g": 8.0,
}


def _png(name="p.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class IdentifyFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)
        self.url = reverse("product-identify")

    def _post(self, data=None, photos=3):
        payload = dict(data or {})
        payload["images"] = [_png(f"{i}.png") for i in range(photos)]
        return self.client.post(self.url, payload, format="multipart")

    # --- dataset first: no AI tokens spent -----------------------------------

    def test_barcode_already_on_file_never_calls_the_ai(self):
        Product.objects.create(barcode=GOOD_BARCODE, name="Milk", source="off", sugar_g=4, sodium_mg=50, saturated_fat_g=1)
        with patch(AI) as ai:
            resp = self._post({"barcode": GOOD_BARCODE})
        ai.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["source"], "database")
        self.assertEqual(resp.data["product"]["name"], "Milk")

    def test_barcode_on_file_works_even_with_no_photos(self):
        Product.objects.create(barcode=GOOD_BARCODE, name="Milk", source="off")
        with patch(AI) as ai:
            resp = self.client.post(self.url, {"barcode": GOOD_BARCODE}, format="multipart")
        ai.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_known_nafdac_number_reuses_the_registered_product_without_ai(self):
        Product.objects.create(
            barcode="111", name="Verified Cereal", brand="Acme", nafdac_number="A4-1234",
            nafdac_verified=True, sugar_g=5, sodium_mg=100, saturated_fat_g=1,
        )
        with patch(AI) as ai:
            resp = self._post({"barcode": GOOD_BARCODE, "nafdac_number": "a4-1234"})
        ai.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["source"], "twin")
        saved = Product.objects.get(barcode=GOOD_BARCODE)
        self.assertEqual(saved.name, "Verified Cereal")
        self.assertTrue(saved.nafdac_verified)  # inherits the admin's registry check
        self.assertTrue(saved.is_estimated)  # but the barcode link is still a user claim
        self.assertEqual(resp.data["product"]["integrity"]["tier"], "verified")

    # --- researching from photos ----------------------------------------------

    def test_unknown_product_is_researched_and_saved_under_the_scanned_barcode(self):
        with patch(AI, return_value=dict(AI_RESULT)) as ai:
            resp = self._post({"barcode": GOOD_BARCODE})
        self.assertEqual(ai.call_count, 1)  # all photos in ONE request
        self.assertEqual(len(ai.call_args.args[0]), 3)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["source"], "ai")
        saved = Product.objects.get(barcode=GOOD_BARCODE)
        self.assertEqual(saved.name, "Golden Morn")
        self.assertEqual(saved.nafdac_number, "A4-1234")  # normalized
        self.assertEqual(saved.source, "ai_vision")
        self.assertTrue(saved.is_estimated)

    def test_scanning_it_again_is_answered_from_the_database(self):
        with patch(AI, return_value=dict(AI_RESULT)):
            self._post({"barcode": GOOD_BARCODE})
        with patch(AI) as ai:
            resp = self.client.post(reverse("scan"), {"barcode": GOOD_BARCODE}, format="json")
        ai.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["product"]["nafdac_number"], "A4-1234")
        self.assertTrue(resp.data["is_estimated"])
        self.assertIn("tier", resp.data["product"]["integrity"])

    def test_ai_saved_product_inherits_an_existing_verified_registration(self):
        Product.objects.create(barcode="111", name="Other size", nafdac_number="A4-1234", nafdac_verified=True)
        with patch(AI, return_value=dict(AI_RESULT)):
            resp = self._post({"barcode": GOOD_BARCODE})
        self.assertTrue(Product.objects.get(barcode=GOOD_BARCODE).nafdac_verified)
        self.assertEqual(resp.data["product"]["integrity"]["tier"], "verified")

    def test_existing_product_is_never_overwritten_by_ai(self):
        Product.objects.create(barcode=GOOD_BARCODE, name="Verified Original", source="off", nafdac_verified=True)
        with patch(AI, return_value=dict(AI_RESULT)):
            self._post({"barcode": GOOD_BARCODE})
        self.assertEqual(Product.objects.get(barcode=GOOD_BARCODE).name, "Verified Original")

    def test_barcode_read_from_photos_is_used_only_if_checksum_valid(self):
        with patch(AI, return_value={**AI_RESULT, "barcode": GOOD_BARCODE}):
            self._post()
        self.assertTrue(Product.objects.filter(barcode=GOOD_BARCODE).exists())

        with patch(AI, return_value={**AI_RESULT, "name": "Misread", "barcode": "1234567890123"}):
            self._post()
        misread = Product.objects.get(name="Misread")
        self.assertTrue(misread.barcode.startswith("AI-"))

    def test_medicine_is_identified_but_not_scored(self):
        with patch(AI, return_value={**AI_RESULT, "name": "Panadol", "product_type": "medicine"}):
            resp = self._post({"barcode": GOOD_BARCODE})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["product_type"], "medicine")
        self.assertNotIn("score", resp.data)

    def test_legacy_single_image_field_still_works(self):
        with patch(AI, return_value=dict(AI_RESULT)):
            resp = self.client.post(self.url, {"barcode": GOOD_BARCODE, "image": _png()}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # --- errors say what actually went wrong -----------------------------------

    def test_ai_failure_returns_a_specific_reason_not_a_silent_404(self):
        error = IdentifyError("ai_model_gone", "The AI model this app uses is no longer available.")
        with patch(AI, side_effect=error):
            resp = self._post({"barcode": GOOD_BARCODE})
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(resp.data["reason"], "ai_model_gone")
        self.assertIn("no longer available", resp.data["detail"])
        self.assertFalse(resp.data["retake"])
        self.assertFalse(Product.objects.filter(barcode=GOOD_BARCODE).exists())

    def test_unreadable_photos_ask_for_a_retake(self):
        error = IdentifyError("not_identified", "Retake the photos closer.", retake=True)
        with patch(AI, side_effect=error):
            resp = self._post({"barcode": GOOD_BARCODE})
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertTrue(resp.data["retake"])

    def test_missing_ai_key_is_a_503(self):
        with patch(AI, side_effect=IdentifyError("ai_not_configured", "AI isn't set up.")):
            resp = self._post({"barcode": GOOD_BARCODE})
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_no_photos_for_an_unknown_product_explains_what_to_do(self):
        resp = self.client.post(self.url, {"barcode": GOOD_BARCODE}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["reason"], "no_photos")
        self.assertIn("at least 3", resp.data["detail"])

    def test_non_image_upload_names_the_bad_photo(self):
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        resp = self.client.post(self.url, {"barcode": GOOD_BARCODE, "images": [_png(), bad]}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Photo 2", resp.data["detail"])

    def test_too_many_photos_rejected(self):
        resp = self._post({"barcode": GOOD_BARCODE}, photos=7)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_junk_nafdac_number_rejected_before_any_work(self):
        with patch(AI) as ai:
            resp = self._post({"barcode": GOOD_BARCODE, "nafdac_number": "nonsense"})
        ai.assert_not_called()
        self.assertEqual(resp.data["reason"], "bad_nafdac_number")

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .barcodes import barcode_variants, find_product_by_barcode
from .models import Product

User = get_user_model()


class BarcodeVariantTests(SimpleTestCase):
    def test_raw_form_comes_first(self):
        self.assertEqual(barcode_variants("6154000256692")[0], "6154000256692")

    def test_upc_a_matches_its_ean13_and_gtin14_forms(self):
        variants = barcode_variants("012345678905")
        self.assertIn("0012345678905", variants)
        self.assertIn("00012345678905", variants)

    def test_ean13_with_leading_zero_matches_upc_a(self):
        self.assertIn("012345678905", barcode_variants("0012345678905"))

    def test_non_numeric_codes_are_left_alone(self):
        self.assertEqual(barcode_variants("AI-abc123"), ["AI-abc123"])
        self.assertEqual(barcode_variants("  "), [])

    def test_different_numbers_do_not_collide(self):
        self.assertNotIn("6154000256693", barcode_variants("6154000256692"))


class BarcodeLookupTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)

    def test_scan_finds_a_product_stored_under_a_padded_form(self):
        Product.objects.create(
            barcode="0012345678905", name="Padded", sugar_g=1, sodium_mg=10, saturated_fat_g=0.5
        )
        resp = self.client.post(reverse("scan"), {"barcode": "012345678905"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["product"]["name"], "Padded")

    def test_exact_match_wins_over_an_equivalent_form(self):
        Product.objects.create(barcode="0012345678905", name="Padded")
        Product.objects.create(barcode="012345678905", name="Exact")
        self.assertEqual(find_product_by_barcode("012345678905").name, "Exact")

    def test_unknown_barcode_is_still_a_404(self):
        resp = self.client.post(reverse("scan"), {"barcode": "6154000256693"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_product_detail_and_reports_use_the_same_matching(self):
        Product.objects.create(barcode="0012345678905", name="Padded")
        self.assertEqual(self.client.get(reverse("product-detail", args=["012345678905"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("product-reports", args=["012345678905"])).status_code, 200)

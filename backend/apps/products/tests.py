from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Product

User = get_user_model()


class ScanFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="chinedu", password="strongpassword123")
        self.client.force_authenticate(self.user)

    def test_scan_existing_product_returns_score_and_explanation(self):
        Product.objects.create(
            barcode="6009000000000",
            name="Test Cornflakes",
            brand="TestBrand",
            sugar_g=25,
            saturated_fat_g=8,
            sodium_mg=500,
            ingredients_text="corn, sugar, glucose syrup, salt",
        )
        resp = self.client.post(reverse("scan"), {"barcode": "6009000000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["label"], "Avoid")
        self.assertEqual(resp.data["diabetic_risk"], "Avoid")
        self.assertIn("explanation", resp.data)

    @patch("apps.products.views.OpenFoodFactsClient.fetch_product", return_value=None)
    def test_scan_unknown_product_returns_404_with_submit_action(self, mock_fetch):
        resp = self.client.post(reverse("scan"), {"barcode": "0000000000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["action"], "submit_product")

    def test_analyze_endpoint_scores_raw_payload(self):
        resp = self.client.post(
            reverse("analyze"), {"sugar_g": 2, "saturated_fat_g": 0.5, "sodium_mg": 50}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["label"], "Good")

    def test_submit_product_creates_pending_submission(self):
        resp = self.client.post(
            reverse("product-submit"),
            {
                "barcode": "6009999999999",
                "name": "Local Zobo Drink",
                "brand": "LocalBrand",
                "nutrition_payload": {"sugar_g": 12},
                "ingredients_text": "hibiscus, sugar, water",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "pending")

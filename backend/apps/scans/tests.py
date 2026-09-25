from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.products.models import Product

from .models import Scan

User = get_user_model()


class HistoryTests(APITestCase):
    def test_history_lists_only_current_user_scans(self):
        user = User.objects.create_user(username="tolu", password="strongpassword123")
        other = User.objects.create_user(username="other", password="strongpassword123")
        product = Product.objects.create(barcode="123", name="Snack")
        Scan.objects.create(user=user, product=product, score=5, label="Moderate", diabetic_risk="Safe")
        Scan.objects.create(user=other, product=product, score=5, label="Moderate", diabetic_risk="Safe")

        self.client.force_authenticate(user)
        resp = self.client.get(reverse("history"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

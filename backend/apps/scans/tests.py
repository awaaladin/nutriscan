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


class DeleteHistoryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.other = User.objects.create_user(username="bola", password="strongpassword123")
        self.product = Product.objects.create(barcode="777", name="Biscuit", sugar_g=12)
        self.mine = Scan.objects.create(user=self.user, product=self.product, score=5, label="Moderate", diabetic_risk="Safe")
        self.theirs = Scan.objects.create(user=self.other, product=self.product, score=5, label="Moderate", diabetic_risk="Safe")
        self.client.force_authenticate(self.user)

    def test_deleting_one_scan_keeps_the_product_and_everyone_elses_scans(self):
        resp = self.client.delete(reverse("history-detail", args=[self.mine.pk]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Scan.objects.filter(pk=self.mine.pk).exists())
        self.assertTrue(Scan.objects.filter(pk=self.theirs.pk).exists())
        self.assertEqual(Product.objects.get(barcode="777").sugar_g, 12)

    def test_you_cannot_delete_someone_elses_scan(self):
        resp = self.client.delete(reverse("history-detail", args=[self.theirs.pk]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Scan.objects.filter(pk=self.theirs.pk).exists())

    def test_clearing_history_removes_only_my_scans_and_keeps_the_data_set(self):
        resp = self.client.delete(reverse("history"))
        self.assertEqual(resp.data["deleted"], 1)
        self.assertEqual(Scan.objects.filter(user=self.user).count(), 0)
        self.assertEqual(Scan.objects.filter(user=self.other).count(), 1)
        self.assertTrue(Product.objects.filter(barcode="777").exists())

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.delete(reverse("history")).status_code, status.HTTP_401_UNAUTHORIZED)

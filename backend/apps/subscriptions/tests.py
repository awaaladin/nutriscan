from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class SubscriptionFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)

    def test_verify_then_pro_insights_accessible(self):
        verify_resp = self.client.post(
            reverse("subscription-verify"),
            {"plan": "monthly", "purchase_token": "fake-token", "product_id": "nutriscan_pro_monthly"},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_resp.data["status"], "active")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_pro)

        insights_resp = self.client.get(reverse("pro-insights"))
        self.assertEqual(insights_resp.status_code, status.HTTP_200_OK)

    def test_pro_insights_blocked_for_free_user(self):
        resp = self.client.get(reverse("pro-insights"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class AuthFlowTests(APITestCase):
    def test_register_then_preferences_then_login(self):
        register_resp = self.client.post(
            reverse("register"),
            {
                "username": "amaka",
                "email": "amaka@example.com",
                "password": "strongpassword123",
                "region": "NG",
            },
        )
        self.assertEqual(register_resp.status_code, status.HTTP_201_CREATED)
        access = register_resp.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        prefs_resp = self.client.patch(reverse("preferences"), {"is_diabetic": True}, format="json")
        self.assertEqual(prefs_resp.status_code, status.HTTP_200_OK)
        self.assertTrue(prefs_resp.data["is_diabetic"])

        self.client.credentials()
        login_resp = self.client.post(reverse("login"), {"username": "amaka", "password": "strongpassword123"})
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_resp.data)

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Subscription
from .play_client import PlayNotConfigured, PlaySubscription, PlayVerificationError

User = get_user_model()

VERIFIER = "apps.subscriptions.views.get_verifier"
SERVICE_VERIFIER = "apps.subscriptions.services.get_verifier"
PAYLOAD = {"purchase_token": "tok-1", "product_id": "nutriscan_pro_monthly"}


class FakeVerifier:
    def __init__(self, play=None, error=None):
        self.play, self.error, self.acknowledged = play, error, []

    def get_subscription(self, token):
        if self.error:
            raise self.error
        return self.play

    def acknowledge(self, product_id, token):
        self.acknowledged.append((product_id, token))


def _play(product="nutriscan_pro_monthly", days=30, entitled=True, acknowledged=False):
    return PlaySubscription(
        product_id=product,
        expires_at=timezone.now() + timedelta(days=days),
        entitled=entitled,
        acknowledged=acknowledged,
    )


class VerifySubscriptionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)
        self.url = reverse("subscription-verify")

    def test_valid_purchase_grants_pro_and_acknowledges(self):
        fake = FakeVerifier(play=_play())
        with patch(VERIFIER, return_value=fake):
            resp = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["plan"], "monthly")
        self.assertEqual(resp.data["status"], "active")
        self.assertEqual(fake.acknowledged, [("nutriscan_pro_monthly", "tok-1")])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_pro)
        with patch(SERVICE_VERIFIER, return_value=fake):
            self.assertEqual(self.client.get(reverse("pro-insights")).status_code, status.HTTP_200_OK)

    def test_already_acknowledged_is_not_acknowledged_again(self):
        fake = FakeVerifier(play=_play(acknowledged=True))
        with patch(VERIFIER, return_value=fake):
            self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(fake.acknowledged, [])

    def test_plan_comes_from_google_not_client(self):
        fake = FakeVerifier(play=_play(product="nutriscan_pro_yearly", days=365))
        with patch(VERIFIER, return_value=fake):
            resp = self.client.post(self.url, {**PAYLOAD, "plan": "monthly"}, format="json")
        self.assertEqual(resp.data["plan"], "yearly")

    def test_not_configured_fails_closed(self):
        with patch(VERIFIER, return_value=FakeVerifier(error=PlayNotConfigured())):
            resp = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_pro)

    def test_google_rejection_grants_nothing(self):
        with patch(VERIFIER, return_value=FakeVerifier(error=PlayVerificationError())):
            resp = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_pro)

    def test_unknown_product_rejected(self):
        with patch(VERIFIER, return_value=FakeVerifier(play=_play(product="something_else"))):
            resp = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_pro)

    def test_inactive_subscription_does_not_grant_pro(self):
        with patch(VERIFIER, return_value=FakeVerifier(play=_play(entitled=False))):
            resp = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_pro)

    def test_token_cannot_be_reused_by_another_account(self):
        other = User.objects.create_user(username="bayo", password="strongpassword123")
        Subscription.objects.create(user=other, play_purchase_token="tok-1", status="active")
        with patch(VERIFIER, return_value=FakeVerifier(play=_play())):
            resp = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_pro)


class ProStatusTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123", is_pro=True)
        self.client.force_authenticate(self.user)

    def test_pro_flag_without_a_subscription_is_not_honoured(self):
        # e.g. a user flipped to is_pro by hand in the DB with no purchase behind it
        self.assertEqual(self.client.get(reverse("pro-insights")).status_code, status.HTTP_403_FORBIDDEN)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_pro)

    def test_pro_insights_blocked_for_free_user(self):
        free = User.objects.create_user(username="free", password="strongpassword123")
        self.client.force_authenticate(free)
        self.assertEqual(self.client.get(reverse("pro-insights")).status_code, status.HTTP_403_FORBIDDEN)

    def test_expired_subscription_renews_when_google_says_so(self):
        Subscription.objects.create(
            user=self.user, plan="monthly", status="active", play_purchase_token="tok-1",
            expires_at=timezone.now() - timedelta(days=1),
        )
        with patch(SERVICE_VERIFIER, return_value=FakeVerifier(play=_play())):
            resp = self.client.get(reverse("preferences"))
        self.assertTrue(resp.data["is_pro"])
        self.assertGreater(Subscription.objects.get(user=self.user).expires_at, timezone.now())

    def test_expired_subscription_revokes_pro_when_lapsed(self):
        Subscription.objects.create(
            user=self.user, plan="monthly", status="active", play_purchase_token="tok-1",
            expires_at=timezone.now() - timedelta(days=1),
        )
        lapsed = _play(days=-1, entitled=False)
        with patch(SERVICE_VERIFIER, return_value=FakeVerifier(play=lapsed)):
            resp = self.client.get(reverse("preferences"))
        self.assertFalse(resp.data["is_pro"])

    def test_unconfirmable_expired_subscription_is_not_honoured(self):
        Subscription.objects.create(
            user=self.user, plan="monthly", status="active", play_purchase_token="tok-1",
            expires_at=timezone.now() - timedelta(days=1),
        )
        with patch(SERVICE_VERIFIER, return_value=FakeVerifier(error=PlayNotConfigured())):
            resp = self.client.get(reverse("preferences"))
        self.assertFalse(resp.data["is_pro"])

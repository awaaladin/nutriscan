"""Server-side verification of Google Play subscription purchases.

The Android app only ever sends a purchase token; everything that grants Pro
(which product, whether it is paid, when it expires) is read from Google's
Play Developer API here, never trusted from the client. Without
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON configured, verification fails closed
(PlayNotConfigured) -- there is no fallback that grants Pro.

Setup: create a service account in Google Cloud, enable the Google Play
Android Developer API, and invite the service account's email under
Play Console > Users and permissions with "View financial data" and "Manage
orders and subscriptions". Put its JSON key in GOOGLE_PLAY_SERVICE_ACCOUNT_JSON.
"""
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.utils.dateparse import parse_datetime

API_ROOT = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

# Google states in which the user keeps paid access until expiryTime.
ENTITLED_STATES = {
    "SUBSCRIPTION_STATE_ACTIVE",
    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
    "SUBSCRIPTION_STATE_CANCELED",  # cancelled but paid through expiry
}


class PlayNotConfigured(Exception):
    pass


class PlayVerificationError(Exception):
    """Google rejected the token, or the response couldn't be understood."""


@dataclass
class PlaySubscription:
    product_id: str
    expires_at: datetime
    entitled: bool
    acknowledged: bool


class PlayVerifier:
    def __init__(self, session=None):
        self._session = session

    def _get_session(self):
        if self._session is not None:
            return self._session
        raw = getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise PlayNotConfigured("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is not set.")
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
        self._session = AuthorizedSession(credentials)
        return self._session

    @property
    def _package(self) -> str:
        return settings.GOOGLE_PLAY_PACKAGE_NAME

    def get_subscription(self, purchase_token: str) -> PlaySubscription:
        session = self._get_session()
        response = session.get(
            f"{API_ROOT}/{self._package}/purchases/subscriptionsv2/tokens/{purchase_token}", timeout=15
        )
        if response.status_code != 200:
            raise PlayVerificationError(f"Google Play returned {response.status_code}.")
        data = response.json()
        try:
            line = data["lineItems"][0]
            expires_at = parse_datetime(line["expiryTime"])
            return PlaySubscription(
                product_id=line["productId"],
                expires_at=expires_at,
                entitled=data["subscriptionState"] in ENTITLED_STATES,
                acknowledged=data.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise PlayVerificationError("Unexpected response from Google Play.") from exc

    def acknowledge(self, product_id: str, purchase_token: str) -> None:
        """Play refunds purchases that aren't acknowledged within 3 days."""
        session = self._get_session()
        response = session.post(
            f"{API_ROOT}/{self._package}/purchases/subscriptions/{product_id}/tokens/{purchase_token}:acknowledge",
            json={},
            timeout=15,
        )
        if response.status_code not in (200, 204):
            raise PlayVerificationError(f"Acknowledge failed with {response.status_code}.")


def get_verifier() -> PlayVerifier:
    return PlayVerifier()

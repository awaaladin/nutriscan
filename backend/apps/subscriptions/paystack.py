"""Paystack: prepaid Pro bought on the web (card, bank transfer, USSD), next to Google Play.

One Paystack account serves several apps, so every NutriScan reference starts with the app code
and every transaction carries the same metadata keys. That lets the dashboard, exports and the
webhook router tell NutriScan's payments apart from the other apps':

    NUTRISCAN-PROMONTH-20261023-4F9A2C7B1E0D   one month of Pro
    NUTRISCAN-PROYEAR-20261023-9C1E0D4F9A2C    one year of Pro

The router forwards only NUTRISCAN- references here, byte for byte, so the HMAC signature still
verifies against the shared secret key.
"""
import hashlib
import hmac
import uuid

import requests
from django.conf import settings
from django.utils import timezone

APP_CODE = "NUTRISCAN"
APP_NAME = "NutriScan"
PURPOSES = {"monthly": "PROMONTH", "yearly": "PROYEAR"}


class PaystackError(Exception):
    pass


class PaystackNotConfigured(PaystackError):
    pass


def make_reference(purpose: str, *, length: int = 12) -> str:
    stamp = timezone.now().strftime("%Y%m%d")
    return f"{APP_CODE}-{purpose.upper()}-{stamp}-{uuid.uuid4().hex[:length].upper()}"


def is_ours(reference) -> bool:
    return (reference or "").upper().startswith(f"{APP_CODE}-")


def paystack_metadata(purpose: str, description: str, **extra) -> dict:
    """Metadata sent with every transaction. custom_fields show on the Paystack dashboard."""
    return {
        "app": APP_CODE,
        "app_name": APP_NAME,
        "purpose": purpose.upper(),
        **extra,
        "custom_fields": [
            {"display_name": "App", "variable_name": "app", "value": APP_NAME},
            {"display_name": "Payment for", "variable_name": "purpose", "value": description[:200]},
        ],
    }


def _request(method, path, **kwargs):
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackNotConfigured("PAYSTACK_SECRET_KEY is not set")
    try:
        response = requests.request(
            method,
            f"{settings.PAYSTACK_BASE_URL.rstrip('/')}{path}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=20,
            **kwargs,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaystackError(f"Paystack unreachable: {exc}") from exc
    if not response.ok or not body.get("status"):
        raise PaystackError(body.get("message") or f"Paystack error {response.status_code}")
    return body["data"]


def initialize_transaction(*, email, amount_kobo, reference, callback_url, metadata):
    return _request("POST", "/transaction/initialize", json={
        "email": email, "amount": amount_kobo, "currency": "NGN", "reference": reference,
        "callback_url": callback_url, "metadata": metadata,
    })


def verify_transaction(reference):
    return _request("GET", f"/transaction/verify/{reference}")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    if not settings.PAYSTACK_SECRET_KEY or not signature:
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)

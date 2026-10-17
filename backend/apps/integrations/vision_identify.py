"""Identify a product from photos of its sides when its barcode isn't in any
database yet (Open Food Facts' Nigerian coverage is partial, and there's no
barcode database for Nigerian pharmaceuticals at all -- see
apps.products.medicine_names). Gemini reads the package directly.

All photos go to the model in ONE request -- they're different sides of the
same pack, and combining them is both more accurate (front for the name, back
for nutrition/ingredients/NAFDAC number) and cheaper than a call per photo.
Callers must check their own data first (barcode, NAFDAC number) so this is
only reached when there is genuinely nothing on file.

This is a best-effort estimate, not a verified reading: label photos are often
angled or blurry, so extracted numbers can be wrong. Callers must mark results
from here as estimated (see Product.is_estimated).

Failures raise IdentifyError with a machine-readable `reason` and a message
written for the user, so the app can say what actually went wrong instead of a
generic "couldn't identify".
"""
import base64
import json
import os
import time
from typing import List, Tuple

import requests
from django.conf import settings

# "-latest" alias so a retired dated model (gemini-2.0-flash was retired and
# every call 404'd, silently) can't break photo identification again.
DEFAULT_MODEL = "gemini-flash-latest"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "identified": {"type": "boolean"},
        "name": {"type": "string"},
        "brand": {"type": "string"},
        "product_type": {"type": "string", "enum": ["food", "medicine", "non_food"]},
        "confidence": {"type": "number"},
        "barcode": {"type": "string", "nullable": True},
        "nafdac_number": {"type": "string", "nullable": True},
        "ingredients_text": {"type": "string"},
        "calories_kcal": {"type": "number", "nullable": True},
        "sugar_g": {"type": "number", "nullable": True},
        "saturated_fat_g": {"type": "number", "nullable": True},
        "sodium_mg": {"type": "number", "nullable": True},
        "carbohydrates_g": {"type": "number", "nullable": True},
        "fiber_g": {"type": "number", "nullable": True},
        "protein_g": {"type": "number", "nullable": True},
    },
    "required": ["identified", "name", "brand", "product_type", "confidence"],
}

PROMPT = """You are looking at several photos of the SAME packaged product (food or medicine),
taken from different sides, because a barcode scanner could not recognize it. Combine
everything visible across all the photos to identify it and, if it is a food with a visible
nutrition facts panel, read the per-100g/100ml values exactly as printed.

Rules:
- Set identified=false if you cannot tell what the product is at all.
- product_type is "medicine" for any drug/pharmaceutical, "food" for packaged food/drink,
  "non_food" for anything else (cosmetics, household goods, etc).
- If a barcode (the printed digits under the black bars, usually 8-13 digits) is visible
  in any photo, transcribe those digits exactly into barcode. Read them from the printed
  numbers, not by interpreting the bar pattern. Use null if none is visible or legible.
- If a NAFDAC registration number is printed on the pack (formats like "A4-1234" or
  "04-8861", often labelled "NAFDAC Reg. No."), transcribe it exactly into nafdac_number;
  use null if it isn't visible or legible. Never invent one.
- Only fill in numeric nutrition fields if you can actually read them in the photos --
  use null rather than guessing a plausible-sounding number.
- Nutrition values must be per 100g or 100ml, converting from per-serving if needed.
- sodium_mg must be in milligrams (convert from grams if the label shows salt/sodium in g).
- For medicine or non_food items, leave nutrition fields null.
"""


class IdentifyError(Exception):
    """`reason` is a stable code the client can branch on; `message` is shown
    to the user as-is. `retake` says whether better photos could fix it."""

    def __init__(self, reason: str, message: str, retake: bool = False):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.retake = retake


def identify_product_from_images(images: List[Tuple[bytes, str]]) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise IdentifyError(
            "ai_not_configured",
            "AI photo recognition isn't set up on the server yet (missing API key). "
            "You can still add the product by hand.",
        )

    parts = [{"text": PROMPT}] + [
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}
        for data, mime in images
    ]

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": RESPONSE_SCHEMA},
    }
    response = post_with_model_fallback(api_key, payload)
    if response.status_code != 200:
        raise _http_error(response)

    try:
        candidate = response.json()["candidates"][0]
        result = json.loads(candidate["content"]["parts"][0]["text"])
    except (KeyError, IndexError, ValueError, TypeError):
        # Typically a safety block or an empty candidate, not a bad request.
        raise IdentifyError(
            "ai_bad_response",
            "The AI couldn't read these photos. Retake them in good light, one side per photo.",
            retake=True,
        )

    if not result.get("identified") or not result.get("name"):
        raise IdentifyError(
            "not_identified",
            "The AI couldn't tell what this product is. Retake the photos closer, in good light, "
            "with the front label and the back label each filling the frame.",
            retake=True,
        )
    return result


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3

# The free tier meters requests per model per day, so these are tried in order:
# when one model's daily allowance is spent (429) or it has been retired (404),
# the next still has its own. Override with GEMINI_MODELS / GEMINI_CHAT_MODELS.
#
# Reading a label needs accuracy, so photo research starts with the strongest
# model. Chat (questions, one-sentence explanations) needs speed and volume, so
# it starts with the lite models (~2s vs ~8s).
DEFAULT_MODELS = [
    DEFAULT_MODEL,
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
]
DEFAULT_CHAT_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.7-flash",
    DEFAULT_MODEL,
]


def configured_models(kind: str = "vision") -> List[str]:
    if kind == "chat":
        return list(getattr(settings, "GEMINI_CHAT_MODELS", None) or DEFAULT_CHAT_MODELS)
    return list(getattr(settings, "GEMINI_MODELS", None) or DEFAULT_MODELS)


def is_daily_quota(response) -> bool:
    """True when a 429 means today's allowance is spent (retrying can't help),
    as opposed to a per-minute burst limit that clears in seconds."""
    try:
        details = response.json().get("error", {}).get("details", [])
    except (ValueError, AttributeError):
        return False
    return any("PerDay" in violation.get("quotaId", "") for d in details for violation in d.get("violations", []))


def _post_with_retries(url: str, api_key: str, payload: dict, timeout: int = 30, max_attempts: int = MAX_ATTEMPTS):
    """Google's API briefly returns 429/5xx (overloaded, rate-limited) or drops
    a connection even when nothing is wrong with the request. One of those must
    not fail a scan the user spent time photographing, so these are retried with
    a short backoff; permanent errors (bad key, bad request, retired model) and
    a spent daily quota return immediately. Raises IdentifyError if every attempt
    failed to connect."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
        except requests.Timeout:
            last_error = IdentifyError("ai_timeout", "The AI took too long to respond. Please try again.")
        except requests.RequestException:
            last_error = IdentifyError(
                "ai_unreachable", "The server couldn't reach the AI service. Please try again shortly."
            )
        else:
            if (
                response.status_code not in RETRYABLE_STATUSES
                or attempt == max_attempts
                or (response.status_code == 429 and is_daily_quota(response))
            ):
                return response
            last_error = None
        if attempt < max_attempts:
            time.sleep(1.5 * attempt)
    raise last_error


def post_with_model_fallback(
    api_key: str,
    payload: dict,
    timeout: int = 30,
    max_attempts: int = MAX_ATTEMPTS,
    models: List[str] = None,
    kind: str = "vision",
):
    """POST to the first model that will take the request. A model that is out
    of quota (429) or retired (404) hands over to the next; any other answer,
    success or a permanent error, is final. If every model refuses, the last
    refusal is returned so the caller reports the real reason."""
    response = None
    for model in models or configured_models(kind):
        response = _post_with_retries(API_URL.format(model=model), api_key, payload, timeout, max_attempts)
        if response.status_code not in (404, 429):
            return response
    return response


def _http_error(response) -> IdentifyError:
    status = response.status_code
    if status == 429:
        if is_daily_quota(response):
            return IdentifyError(
                "ai_quota_daily",
                "NutriScan's AI has reached its daily limit, so it can't research new products or answer "
                "questions until it resets (usually within a day). Products already in our database still "
                "work, and you can add this one by hand.",
            )
        return IdentifyError("ai_quota", "The AI service is busy right now. Please try again in a minute.")
    if status in (401, 403):
        return IdentifyError("ai_auth", "The server's AI key was rejected, so the AI features are unavailable. This is a server problem, not your photos.")
    if status == 404:
        return IdentifyError("ai_model_gone", "The AI models this app uses are no longer available. This is a server problem, not your photos.")
    if status == 400:
        return IdentifyError(
            "ai_rejected",
            "The AI couldn't process this request (it may be too large or malformed). "
            "If you were sending photos, retake them and try again.",
            retake=True,
        )
    return IdentifyError("ai_error", f"The AI service returned an error ({status}). Please try again shortly.")

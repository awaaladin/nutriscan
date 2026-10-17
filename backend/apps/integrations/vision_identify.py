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

    model = getattr(settings, "GEMINI_VISION_MODEL", DEFAULT_MODEL)
    parts = [{"text": PROMPT}] + [
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}}
        for data, mime in images
    ]

    try:
        response = requests.post(
            API_URL.format(model=model),
            params={"key": api_key},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": RESPONSE_SCHEMA},
            },
            timeout=45,
        )
    except requests.Timeout:
        raise IdentifyError("ai_timeout", "The AI took too long to read the photos. Please try again.")
    except requests.RequestException:
        raise IdentifyError("ai_unreachable", "The server couldn't reach the AI service. Please try again shortly.")

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


def _http_error(response) -> IdentifyError:
    status = response.status_code
    if status == 429:
        return IdentifyError("ai_quota", "The AI service is busy or over its daily limit. Please try again in a few minutes.")
    if status in (401, 403):
        return IdentifyError("ai_auth", "The server's AI key was rejected, so photo recognition is unavailable. This is a server problem, not your photos.")
    if status == 404:
        return IdentifyError("ai_model_gone", "The AI model this app uses is no longer available. This is a server problem, not your photos.")
    if status == 400:
        return IdentifyError("ai_rejected", "The AI rejected these photos (they may be too large or corrupted). Retake them and try again.", retake=True)
    return IdentifyError("ai_error", f"The AI service returned an error ({status}). Please try again shortly.")

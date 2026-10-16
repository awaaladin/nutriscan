"""Identify a scanned product from a photo when its barcode isn't in any
database yet (Open Food Facts' Nigerian coverage is partial, and there's no
barcode database for Nigerian pharmaceuticals at all -- see
apps.products.medicine_names). Gemini reads the package/label directly from
the photo instead.

This is a best-effort estimate, not a verified reading: label photos are
often angled or blurry, so the nutrition numbers it extracts can be wrong.
Callers must mark results from here as estimated (see Product.is_estimated)
rather than presenting them with the same confidence as a verified source.
"""
import base64
import json
import os
from typing import Optional

import requests

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "identified": {"type": "boolean"},
        "name": {"type": "string"},
        "brand": {"type": "string"},
        "product_type": {"type": "string", "enum": ["food", "medicine", "non_food"]},
        "confidence": {"type": "number"},
        "barcode": {"type": "string", "nullable": True},
        "ingredients_text": {"type": "string"},
        "nafdac_number": {"type": "string", "nullable": True},
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

PROMPT = """You are looking at a photo of a packaged product (food or medicine) that a
barcode scanner could not recognize. Identify it and, if it is a food with a visible
nutrition facts panel, read the per-100g/100ml values exactly as printed.

Rules:
- Set identified=false if you cannot tell what the product is at all.
- product_type is "medicine" for any drug/pharmaceutical, "food" for packaged food/drink,
  "non_food" for anything else (cosmetics, household goods, etc).
- If a barcode (the printed digits under the black bars, usually 8-13 digits) is visible
  anywhere in the photo, transcribe those digits exactly into barcode. This may be the
  only barcode reading available if the camera's live scanner couldn't lock onto it --
  read it directly from the printed numbers, not by interpreting the bar pattern. Use
  null if no barcode is visible or the digits aren't legible.
- If a NAFDAC registration number is printed on the pack (formats like "A4-1234" or
  "04-8861", often labelled "NAFDAC Reg. No."), transcribe it exactly into
  nafdac_number; use null if it isn't visible or legible.
- Only fill in numeric nutrition fields if you can actually read them in the photo --
  use null rather than guessing a plausible-sounding number.
- Nutrition values must be per 100g or 100ml, converting from per-serving if needed.
- sodium_mg must be in milligrams (convert from grams if the label shows salt/sodium in g).
- For medicine or non_food items, leave nutrition fields null.
"""


def identify_product_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[dict]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    encoded = base64.b64encode(image_bytes).decode("ascii")
    try:
        response = requests.post(
            API_URL,
            params={"key": api_key},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": PROMPT},
                            {"inline_data": {"mime_type": mime_type, "data": encoded}},
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": RESPONSE_SCHEMA,
                },
            },
            timeout=20,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None

    if not result.get("identified") or not result.get("name"):
        return None
    return result

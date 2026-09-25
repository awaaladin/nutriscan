from typing import Optional

import requests
from django.conf import settings

OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"


class OpenFoodFactsClient:
    """Thin client for the Open Food Facts read API.

    Nigerian/local products are frequently missing from Open Food Facts;
    callers should fall back to the community ProductSubmission flow when
    this returns None (see apps.products.views.ScanView).
    """

    def fetch_product(self, barcode: str) -> Optional[dict]:
        try:
            response = requests.get(
                OFF_API_URL.format(barcode=barcode),
                timeout=getattr(settings, "OPEN_FOOD_FACTS_TIMEOUT", 5),
            )
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        payload = response.json()
        if payload.get("status") != 1:
            return None

        product = payload["product"]
        nutriments = product.get("nutriments", {})

        return {
            "name": product.get("product_name") or "Unknown product",
            "brand": product.get("brands", ""),
            "calories_kcal": nutriments.get("energy-kcal_100g"),
            "sugar_g": nutriments.get("sugars_100g"),
            "saturated_fat_g": nutriments.get("saturated-fat_100g"),
            "sodium_mg": _sodium_mg(nutriments),
            "carbohydrates_g": nutriments.get("carbohydrates_100g"),
            "fiber_g": nutriments.get("fiber_100g"),
            "protein_g": nutriments.get("proteins_100g"),
            "ingredients_text": product.get("ingredients_text", ""),
            "additives": product.get("additives_tags", []),
            "image_url": product.get("image_url", ""),
        }


def _sodium_mg(nutriments: dict) -> Optional[float]:
    sodium_g = nutriments.get("sodium_100g")
    if sodium_g is None:
        return None
    return sodium_g * 1000

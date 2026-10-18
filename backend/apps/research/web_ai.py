"""AI web research: ask the AI to look the product up online and cite its sources.

Used only when live web search actually ran and returned pages. An answer the AI gave
from memory is never saved as evidence: it can't be checked, and a confident wrong
number would erode exactly the trust this data set exists to build. On Google's free
tier web search is blocked, so this returns None and research uses database sources
only; it switches on by itself if search becomes available.
"""
import json
import re
from typing import Optional

from apps.integrations.gemini_chat import generate
from apps.integrations.vision_identify import IdentifyError
from apps.products.nutrition_input import clean_nutrition

from .matching import barcode_country, match_score

INSTRUCTION = """You are researching ONE packaged food product to find its nutrition facts from web pages.
Search the web for the product (use the brand, name and barcode given). Prefer the manufacturer's own site, a
retailer listing or an established food database, for the SAME country's version of the product.

Reply with ONLY a JSON object, no other text:
{"name": "...", "brand": "...", "country": "country this version is sold in",
 "per_100g": {"calories_kcal": n, "sugar_g": n, "saturated_fat_g": n, "sodium_mg": n,
              "carbohydrates_g": n, "fiber_g": n, "protein_g": n},
 "ingredients_text": "..."}
Use null for any value you did not find on a page. Never estimate or fill from general knowledge.
If you cannot find this exact product, reply {"found": false}."""


def _parse(text: str) -> Optional[dict]:
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("found") is not False else None


def research(product) -> Optional[dict]:
    prompt = f"Product: {product.name}\nBrand: {product.brand or 'unknown'}\nBarcode: {product.barcode}"
    try:
        reply = generate(INSTRUCTION, [], prompt, require_search=True)
    except IdentifyError:
        return None  # search unavailable, quota, or any AI failure: no web evidence
    if not reply["web_research"] or not reply["sources"]:
        return None

    data = _parse(reply["answer"])
    if not data:
        return None
    facts = clean_nutrition(
        {k: v for k, v in (data.get("per_100g") or {}).items() if isinstance(v, (int, float))}, strict=False
    )
    if not facts:
        return None

    country = barcode_country(product.barcode)
    claimed_country = (data.get("country") or "").strip().lower().replace(" ", "-")
    countries = [f"en:{claimed_country}"] if claimed_country else []
    score = match_score(product.name, product.brand, country, str(data.get("name") or ""), data.get("brand") or "", countries)
    source = reply["sources"][0]
    return {
        "url": source["url"],
        "label": source["title"],
        "facts": facts,
        "ingredients": str(data.get("ingredients_text") or "")[:3000],
        "score": score,
    }

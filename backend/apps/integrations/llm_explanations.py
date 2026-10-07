"""Pluggable LLM explanation layer.

The rules engine (apps.scoring.engine) is the sole source of truth for
scores and risk tiers. Implementations here only turn an already-computed
result into a plain-language sentence -- they must never be allowed to
change the score, label, or diabetic risk. Swap get_explanation_provider()
to call a real LLM provider without touching any caller code.
"""
import os
from abc import ABC, abstractmethod
from typing import List

import requests


class LLMExplanationProvider(ABC):
    @abstractmethod
    def explain(
        self,
        product_name: str,
        score: int,
        label: str,
        diabetic_risk: str,
        flags: List[str],
    ) -> str:
        ...


class TemplateExplanationProvider(LLMExplanationProvider):
    """Deterministic, zero-cost stub used until a real LLM provider is wired in."""

    def explain(self, product_name, score, label, diabetic_risk, flags):
        flag_text = ", ".join(f.replace("_", " ") for f in flags) or "no major concerns"
        return (
            f"{product_name} scored {score}/10 ({label}). "
            f"Flagged for: {flag_text}. Diabetic risk: {diabetic_risk}. "
            "This is educational information, not medical advice."
        )


class GeminiExplanationProvider(LLMExplanationProvider):
    """Turns an already-scored result into a plain-language sentence via Gemini.

    Never sends the raw product to the model for scoring -- only the
    already-computed score/label/diabetic_risk/flags, with an explicit
    instruction not to alter them. Falls back to the deterministic
    template on any API error so a flaky network call never breaks the
    product detail response.
    """

    API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.8-flash:generateContent"
    )

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._fallback = TemplateExplanationProvider()

    def explain(self, product_name, score, label, diabetic_risk, flags):
        flag_text = ", ".join(f.replace("_", " ") for f in flags) or "no major concerns"
        prompt = (
            "Write a single short, friendly sentence (max 2 sentences) explaining this "
            "food product's health assessment to a consumer. Do not invent a different "
            "score or label -- only restate and explain the ones given. End with a "
            "reminder that this is educational information, not medical advice.\n\n"
            f"Product: {product_name}\n"
            f"Score: {score}/10\n"
            f"Label: {label}\n"
            f"Diabetic risk: {diabetic_risk}\n"
            f"Flags: {flag_text}"
        )
        try:
            response = requests.post(
                self.API_URL,
                params={"key": self._api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=10,
            )
            response.raise_for_status()
            text = (
                response.json()["candidates"][0]["content"]["parts"][0]["text"]
            ).strip()
            return text or self._fallback.explain(
                product_name, score, label, diabetic_risk, flags
            )
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return self._fallback.explain(product_name, score, label, diabetic_risk, flags)


def get_explanation_provider() -> LLMExplanationProvider:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return GeminiExplanationProvider(api_key)
    return TemplateExplanationProvider()

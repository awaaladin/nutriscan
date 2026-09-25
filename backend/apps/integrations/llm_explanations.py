"""Pluggable LLM explanation layer.

The rules engine (apps.scoring.engine) is the sole source of truth for
scores and risk tiers. Implementations here only turn an already-computed
result into a plain-language sentence -- they must never be allowed to
change the score, label, or diabetic risk. Swap get_explanation_provider()
to call a real LLM provider without touching any caller code.
"""
from abc import ABC, abstractmethod
from typing import List


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


def get_explanation_provider() -> LLMExplanationProvider:
    # TODO: return a real provider (e.g. an Anthropic API-backed one) here
    # once cost/latency budget is decided. Keep responses cached per
    # product+score+label+diabetic_risk (see CachedExplanation) to avoid
    # repeat calls for the same result.
    return TemplateExplanationProvider()

"""Retrieval from NutriScan's reviewed knowledge base.

This is how the cloud AI learns from our users today, with no training run: before it
answers, we look up reviewed question/answer pairs that match the question and put them
in front of it as trusted context. Only entries an admin has approved are ever used.
"""
import re
from typing import List

from .models import KnowledgeEntry

_STOP = {
    "what", "when", "where", "which", "does", "this", "that", "with", "from", "have", "about", "there",
    "should", "would", "could", "your", "mine", "they", "them", "their", "tell", "more", "much", "many",
    "please", "thanks", "thank", "can", "is", "are",
}
MIN_SHARED_WORDS = 2
MIN_OVERLAP = 0.4  # share of the entry's question words that the new question contains


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 4 and w not in _STOP}


def relevant_entries(text: str, limit: int = 3) -> List[KnowledgeEntry]:
    asked = _words(text)
    if len(asked) < MIN_SHARED_WORDS:
        return []
    scored = []
    for entry in KnowledgeEntry.objects.filter(approved=True):
        words = _words(entry.question)
        shared = len(words & asked)
        if words and shared >= MIN_SHARED_WORDS and shared / len(words) >= MIN_OVERLAP:
            scored.append((shared / len(words), shared, entry))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [entry for _, _, entry in scored[:limit]]

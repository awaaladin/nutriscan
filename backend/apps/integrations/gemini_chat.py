"""Shared chat engine: one place for web search, model fallback and image input.

Used by the per-product "ask about this product" screen and by the general
assistant chat, so both behave the same way when Google's free tier refuses web
search or a model runs out of daily quota (see vision_identify for the fallback
and retry rules).
"""
import base64
import os
import time
from typing import Dict, List, Optional, Tuple

from .vision_identify import IdentifyError, _http_error, configured_models, post_with_model_fallback

# Web search ("grounding") has its own, much smaller quota than plain answers and
# is blocked on Google's free tier. Once it has been refused, skip it for a while
# instead of spending a request on every question just to be refused again.
SEARCH_RETRY_AFTER_SECONDS = 600
_search_unavailable_until = 0.0

NO_SEARCH_NOTE = (
    "\n\nNOTE: live web search is unavailable for this answer. Rely on the data above and "
    "general knowledge, and say plainly when something would need checking online."
)


def generate(
    system_instruction: str,
    history: List[Dict[str, str]],
    user_text: str,
    images: Optional[List[Tuple[bytes, str]]] = None,
    max_history: int = 10,
) -> dict:
    """Returns {"answer", "sources", "web_research"}. `history` is earlier turns,
    oldest first, as {"role": "user"|"assistant", "text": ...}; `images` are
    (bytes, mime) attached to the new user turn. Raises IdentifyError (reused for
    its reason/message shape) when the AI can't answer. Tries web search first;
    if that isn't available it answers without it and says so via web_research=False."""
    global _search_unavailable_until
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise IdentifyError("ai_not_configured", "The assistant isn't set up on the server yet (missing API key).")

    contents = []
    for turn in history[-max_history:]:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = (turn.get("text") or "")[:2000]
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    parts = [{"text": user_text[:2000] or "(photo attached)"}]
    for data, mime in images or []:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}})
    contents.append({"role": "user", "parts": parts})

    def payload(with_search: bool) -> dict:
        instruction = system_instruction + ("" if with_search else NO_SEARCH_NOTE)
        body = {"systemInstruction": {"parts": [{"text": instruction}]}, "contents": contents}
        if with_search:
            body["tools"] = [{"google_search": {}}]
        return body

    response, web_research = None, False
    if time.time() >= _search_unavailable_until:
        # One quick attempt on the primary model only: a refusal is expected on
        # the free tier and must not cost a long retry loop.
        response = post_with_model_fallback(
            api_key, payload(True), max_attempts=1, models=configured_models("chat")[:1]
        )
        web_research = response.status_code == 200
        if not web_research:
            _search_unavailable_until = time.time() + SEARCH_RETRY_AFTER_SECONDS
    if not web_research:
        response = post_with_model_fallback(api_key, payload(False), max_attempts=2, kind="chat")
    if response.status_code != 200:
        raise _http_error(response)

    try:
        candidate = response.json()["candidates"][0]
        answer = "".join(part.get("text", "") for part in candidate["content"]["parts"]).strip()
    except (KeyError, IndexError, ValueError, TypeError):
        raise IdentifyError("ai_bad_response", "The assistant couldn't answer that. Try rephrasing the question.")
    if not answer:
        raise IdentifyError("ai_bad_response", "The assistant couldn't answer that. Try rephrasing the question.")

    sources, seen = [], set()
    for chunk in candidate.get("groundingMetadata", {}).get("groundingChunks", []):
        web = chunk.get("web") or {}
        url = web.get("uri")
        if url and url not in seen:
            seen.add(url)
            sources.append({"title": web.get("title") or url, "url": url})
    return {"answer": answer, "sources": sources[:4], "web_research": web_research}

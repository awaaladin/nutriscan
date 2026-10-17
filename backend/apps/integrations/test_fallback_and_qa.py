import json
import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from . import product_qa
from .product_qa import ask_about_product
from .vision_identify import IdentifyError, identify_product_from_images

POST = "apps.integrations.vision_identify.requests.post"
SLEEP = "apps.integrations.vision_identify.time.sleep"
IMAGES = [(b"fake", "image/jpeg")] * 3
GOOD = {"identified": True, "name": "Golden Morn", "brand": "Nestle", "product_type": "food", "confidence": 0.9}
DAILY = {"error": {"details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}
PER_MINUTE = {"error": {"details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel"}]}]}}


class Resp:
    def __init__(self, status=200, body=None, text=None):
        self.status_code = status
        self._body = body
        self._text = text

    def json(self):
        if self._body is not None:
            return self._body
        return {"candidates": [{"content": {"parts": [{"text": self._text or json.dumps(GOOD)}]}}]}


def urls(post):
    return [c.args[0].split("/models/")[1].split(":")[0] for c in post.call_args_list]


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@override_settings(GEMINI_MODELS=["m1", "m2", "m3"])
class ModelFallbackTests(SimpleTestCase):
    def test_spent_daily_quota_moves_to_the_next_model_without_retrying(self):
        with patch(POST, side_effect=[Resp(429, DAILY), Resp()]) as post, patch(SLEEP) as sleep:
            result = identify_product_from_images(IMAGES)
        self.assertEqual(result["name"], "Golden Morn")
        self.assertEqual(urls(post), ["m1", "m2"])
        sleep.assert_not_called()  # retrying a spent daily quota only wastes time

    def test_retired_model_moves_to_the_next(self):
        with patch(POST, side_effect=[Resp(404), Resp()]) as post:
            identify_product_from_images(IMAGES)
        self.assertEqual(urls(post), ["m1", "m2"])

    def test_per_minute_limit_is_retried_on_the_same_model_first(self):
        with patch(POST, side_effect=[Resp(429, PER_MINUTE), Resp()]) as post, patch(SLEEP):
            identify_product_from_images(IMAGES)
        self.assertEqual(urls(post), ["m1", "m1"])

    def test_every_model_out_of_daily_quota_gives_an_honest_message(self):
        with patch(POST, return_value=Resp(429, DAILY)) as post, patch(SLEEP):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(urls(post), ["m1", "m2", "m3"])
        self.assertEqual(ctx.exception.reason, "ai_quota_daily")
        self.assertIn("daily limit", ctx.exception.message)

    def test_permanent_errors_do_not_try_other_models(self):
        for status in (400, 401, 403):
            with patch(POST, return_value=Resp(status)) as post:
                with self.assertRaises(IdentifyError):
                    identify_product_from_images(IMAGES)
            self.assertEqual(len(post.call_args_list), 1, status)


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@override_settings(GEMINI_CHAT_MODELS=["c1", "c2"])
class ProductQaTests(SimpleTestCase):
    def setUp(self):
        product_qa._search_unavailable_until = 0.0

    def tearDown(self):
        product_qa._search_unavailable_until = 0.0

    def _answer(self, text="Because of the sugar."):
        return {
            "candidates": [
                {
                    "content": {"parts": [{"text": text}]},
                    "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://x.test/a", "title": "A"}}]},
                }
            ]
        }

    def test_web_research_used_when_available(self):
        with patch(POST, return_value=Resp(200, self._answer())) as post:
            reply = ask_about_product("CTX", "Is it ok?", [])
        self.assertTrue(reply["web_research"])
        self.assertEqual(reply["sources"], [{"title": "A", "url": "https://x.test/a"}])
        self.assertIn("tools", post.call_args.kwargs["json"])

    def test_falls_back_to_our_own_data_when_search_is_refused(self):
        with patch(POST, side_effect=[Resp(429), Resp(200, self._answer())]) as post, patch(SLEEP):
            reply = ask_about_product("CTX", "Is it ok?", [])
        self.assertFalse(reply["web_research"])
        second = post.call_args_list[1].kwargs["json"]
        self.assertNotIn("tools", second)
        self.assertIn("live web search is unavailable", second["systemInstruction"]["parts"][0]["text"])

    def test_refused_search_is_not_retried_on_every_question(self):
        with patch(POST, side_effect=[Resp(429), Resp(200, self._answer()), Resp(200, self._answer())]) as post, patch(SLEEP):
            ask_about_product("CTX", "one", [])
            ask_about_product("CTX", "two", [])
        # question two went straight to a no-search answer: 3 calls total, not 4
        self.assertEqual(len(post.call_args_list), 3)
        self.assertNotIn("tools", post.call_args_list[2].kwargs["json"])

    def test_history_and_product_context_are_sent(self):
        history = [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}]
        with patch(POST, return_value=Resp(200, self._answer())) as post:
            ask_about_product("PRODUCT DATA here", "Follow-up?", history)
        sent = post.call_args.kwargs["json"]
        self.assertIn("PRODUCT DATA here", sent["systemInstruction"]["parts"][0]["text"])
        self.assertEqual([c["role"] for c in sent["contents"]], ["user", "model", "user"])

    def test_empty_answer_is_an_error_not_a_blank_reply(self):
        with patch(POST, return_value=Resp(200, {"candidates": [{"content": {"parts": [{"text": " "}]}}]})):
            with self.assertRaises(IdentifyError):
                ask_about_product("CTX", "q", [])

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            with self.assertRaises(IdentifyError) as ctx:
                ask_about_product("CTX", "q", [])
        self.assertEqual(ctx.exception.reason, "ai_not_configured")

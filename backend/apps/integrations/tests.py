import json
import os
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from .vision_identify import IdentifyError, identify_product_from_images

POST = "apps.integrations.vision_identify.requests.post"
SLEEP = "apps.integrations.vision_identify.time.sleep"
IMAGES = [(b"fake", "image/jpeg")] * 3

GOOD = {"identified": True, "name": "Golden Morn", "brand": "Nestle", "product_type": "food", "confidence": 0.9}


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if self._body is None:
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(GOOD)}]}}]}
        return self._body


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@override_settings(GEMINI_MODELS=["only-model"])
class VisionIdentifyTests(SimpleTestCase):
    def test_success_sends_all_photos_in_one_request(self):
        with patch(POST, return_value=FakeResponse()) as post:
            result = identify_product_from_images(IMAGES)
        self.assertEqual(result["name"], "Golden Morn")
        self.assertEqual(post.call_count, 1)
        parts = post.call_args.kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(len([p for p in parts if "inline_data" in p]), 3)

    def test_temporary_google_errors_are_retried_then_succeed(self):
        with patch(POST, side_effect=[FakeResponse(503), FakeResponse(429), FakeResponse()]) as post, patch(SLEEP):
            result = identify_product_from_images(IMAGES)
        self.assertEqual(result["name"], "Golden Morn")
        self.assertEqual(post.call_count, 3)

    def test_persistent_overload_gives_a_specific_message_not_a_silent_failure(self):
        with patch(POST, return_value=FakeResponse(503)) as post, patch(SLEEP):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(ctx.exception.reason, "ai_error")
        self.assertIn("503", ctx.exception.message)

    def test_persistent_rate_limit_is_reported_as_quota(self):
        with patch(POST, return_value=FakeResponse(429)), patch(SLEEP):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(ctx.exception.reason, "ai_quota")

    def test_permanent_errors_are_not_retried(self):
        for status, reason in ((401, "ai_auth"), (403, "ai_auth"), (404, "ai_model_gone"), (400, "ai_rejected")):
            with patch(POST, return_value=FakeResponse(status)) as post, patch(SLEEP):
                with self.assertRaises(IdentifyError) as ctx:
                    identify_product_from_images(IMAGES)
            self.assertEqual(post.call_count, 1, status)
            self.assertEqual(ctx.exception.reason, reason)

    def test_timeout_then_success(self):
        with patch(POST, side_effect=[requests.Timeout(), FakeResponse()]), patch(SLEEP):
            self.assertEqual(identify_product_from_images(IMAGES)["name"], "Golden Morn")

    def test_repeated_timeouts_report_a_timeout(self):
        with patch(POST, side_effect=requests.Timeout()), patch(SLEEP):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(ctx.exception.reason, "ai_timeout")

    def test_dropped_connection_reports_unreachable(self):
        with patch(POST, side_effect=requests.ConnectionError()), patch(SLEEP):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(ctx.exception.reason, "ai_unreachable")

    def test_unidentified_product_asks_for_a_retake(self):
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps({**GOOD, "identified": False})}]}}]}
        with patch(POST, return_value=FakeResponse(200, body)):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(ctx.exception.reason, "not_identified")
        self.assertTrue(ctx.exception.retake)

    def test_blocked_or_empty_response_asks_for_a_retake(self):
        with patch(POST, return_value=FakeResponse(200, {"candidates": []})):
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(ctx.exception.reason, "ai_bad_response")
        self.assertTrue(ctx.exception.retake)


@override_settings(GEMINI_MODELS=["only-model"])
class MissingKeyTests(SimpleTestCase):
    def test_missing_key_says_so(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            with self.assertRaises(IdentifyError) as ctx:
                identify_product_from_images(IMAGES)
        self.assertEqual(ctx.exception.reason, "ai_not_configured")

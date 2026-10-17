import io
import json
import os
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.integrations.vision_identify import IdentifyError
from apps.products.models import Product
from apps.scans.models import Scan

from .command_helpers import scrub_for_test
from .context import build_context, emergency_notice, relevant_products
from .models import ChatMessage, ChatThread

User = get_user_model()
GENERATE = "apps.assistant.views.generate"
REPLY = {"answer": "Paracetamol is a pain reliever.", "sources": [], "web_research": False}


def _png(name="p.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def gum(**extra):
    fields = dict(
        barcode="6154000256692", name="Fresh Action Chewing Gum Menthol Eucalyptus", brand="Mentos",
        nafdac_number="A8-109873", sugar_g=72.1, saturated_fat_g=0.0, sodium_mg=9.0,
        ingredients_text="Sugar, gum base, glucose syrup",
    )
    fields.update(extra)
    return Product.objects.create(**fields)


class ChatApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", password="strongpassword123", is_diabetic=True, primary_goal="diabetes"
        )
        self.client.force_authenticate(self.user)
        self.url = reverse("assistant-chat")

    def _chat(self, data=None, photos=0):
        payload = dict(data or {})
        if photos:
            payload["images"] = [_png(f"{i}.png") for i in range(photos)]
        return self.client.post(self.url, payload, format="multipart")

    def test_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._chat({"message": "hi"}).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_first_message_starts_a_thread_and_saves_both_turns(self):
        with patch(GENERATE, return_value=REPLY):
            resp = self._chat({"message": "What is paracetamol?"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["message"]["text"], REPLY["answer"])
        thread = ChatThread.objects.get(pk=resp.data["thread_id"])
        self.assertEqual(thread.title, "What is paracetamol?")
        self.assertEqual([m.role for m in thread.messages.all()], ["user", "assistant"])

    def test_follow_up_continues_the_thread_and_sends_earlier_turns(self):
        with patch(GENERATE, return_value=REPLY):
            first = self._chat({"message": "What is paracetamol?"})
        with patch(GENERATE, return_value=REPLY) as gen:
            second = self._chat({"message": "And the side effects?", "thread_id": first.data["thread_id"]})
        self.assertEqual(second.data["thread_id"], first.data["thread_id"])
        history = gen.call_args.args[1]
        self.assertEqual([h["role"] for h in history], ["user", "assistant"])
        self.assertEqual(ChatThread.objects.count(), 1)

    def test_empty_message_without_a_photo_is_rejected(self):
        resp = self._chat({"message": "  "})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["reason"], "empty_message")

    def test_a_photo_alone_is_a_valid_question(self):
        with patch(GENERATE, return_value=REPLY) as gen:
            resp = self._chat({}, photos=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(gen.call_args.args[3]), 1)  # the photo reached the AI
        user_turn = ChatMessage.objects.get(role="user")
        self.assertEqual(user_turn.image_count, 1)
        self.assertEqual(user_turn.text, "(photo)")

    def test_at_most_three_photos_are_sent_and_none_are_stored(self):
        with patch(GENERATE, return_value=REPLY) as gen:
            self._chat({"message": "what are these?"}, photos=5)
        self.assertEqual(len(gen.call_args.args[3]), 3)
        self.assertEqual(ChatMessage.objects.get(role="user").image_count, 3)
        self.assertFalse(hasattr(ChatMessage, "image"))  # only a count is kept, never the pixels

    def test_non_image_upload_is_rejected_before_any_ai_call(self):
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        with patch(GENERATE) as gen:
            resp = self.client.post(self.url, {"message": "hi", "images": [bad]}, format="multipart")
        gen.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["reason"], "bad_photos")

    def test_ai_failure_returns_a_specific_reason_and_saves_nothing(self):
        for error, expected in (
            (IdentifyError("ai_quota_daily", "Daily limit."), 502),
            (IdentifyError("ai_not_configured", "No key."), 503),
        ):
            with patch(GENERATE, side_effect=error):
                resp = self._chat({"message": "hi"})
            self.assertEqual(resp.status_code, expected)
            self.assertEqual(resp.data["reason"], error.reason)
        self.assertEqual(ChatThread.objects.count(), 0)  # a failed turn leaves no half-saved chat

    def test_emergency_wording_gets_a_fixed_notice_even_when_the_ai_fails(self):
        with patch(GENERATE, return_value=REPLY):
            ok = self._chat({"message": "my child swallowed tablets, possible overdose"})
        self.assertIn("112", ok.data["notice"])
        with patch(GENERATE, side_effect=IdentifyError("ai_error", "down")):
            down = self._chat({"message": "I have chest pain"})
        self.assertIn("112", down.data["notice"])
        with patch(GENERATE, return_value=REPLY):
            calm = self._chat({"message": "is rice healthy?"})
        self.assertIsNone(calm.data["notice"])

    def test_another_users_thread_is_not_accessible(self):
        other = User.objects.create_user(username="bayo", password="strongpassword123")
        theirs = ChatThread.objects.create(user=other, title="private")
        with patch(GENERATE, return_value=REPLY):
            resp = self._chat({"message": "hi", "thread_id": theirs.id})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_messages_are_marked_for_training_only_with_consent(self):
        with patch(GENERATE, return_value=REPLY):
            self._chat({"message": "no consent yet"})
        self.assertFalse(ChatMessage.objects.filter(training_ok=True).exists())
        self.user.allow_training_use = True
        self.user.save()
        with patch(GENERATE, return_value=REPLY):
            self._chat({"message": "now consented"})
        self.assertEqual(ChatMessage.objects.filter(training_ok=True).count(), 2)  # that turn only


class PersonalContextTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", password="strongpassword123", is_diabetic=True, has_hypertension=True,
            primary_goal="diabetes", health_notes="Allergic to peanuts. Takes metformin.",
        )
        self.client.force_authenticate(self.user)

    def test_context_carries_the_users_profile_and_notes(self):
        context = build_context(self.user, "what should I eat?")
        self.assertIn("diabetic: yes", context)
        self.assertIn("high blood pressure: yes", context)
        self.assertIn("Allergic to peanuts", context)
        self.assertIn("untrusted", context)

    def test_recent_scans_use_the_current_verdict_not_a_stale_one(self):
        product = gum()
        Scan.objects.create(user=self.user, product=product, score=10, label="Good", diabetic_risk="Safe", flags=[])
        context = build_context(self.user, "hello")
        self.assertIn("Fresh Action", context)
        self.assertIn("high_sugar", context)  # recomputed now, not the saved "Good 10/10"

    def test_other_users_scans_never_appear(self):
        other = User.objects.create_user(username="bayo", password="strongpassword123")
        Scan.objects.create(user=other, product=gum(), score=7, label="Good", diabetic_risk="Avoid", flags=[])
        self.assertNotIn("Fresh Action", build_context(self.user, "hello"))

    def test_a_mentioned_product_is_pulled_from_our_database(self):
        gum()
        context = build_context(self.user, "Is Fresh Action chewing gum bad for me?")
        self.assertIn("barcode 6154000256692", context)
        self.assertIn("A8-109873", context)

    def test_products_are_found_by_barcode_and_by_nafdac_number(self):
        gum()
        self.assertEqual(len(relevant_products("scan 6154000256692 please")), 1)
        self.assertEqual(len(relevant_products("is NAFDAC a8-109873 real?")), 1)
        self.assertEqual(len(relevant_products("tell me about rice")), 0)

    def test_a_loose_word_overlap_does_not_pull_in_the_wrong_product(self):
        gum()
        self.assertEqual(relevant_products("is chewing healthy?"), [])  # one shared word is not a match

    def test_the_prompt_in_the_chat_call_includes_that_context(self):
        gum()
        with patch(GENERATE, return_value=REPLY) as gen:
            self.client.post(
                reverse("assistant-chat"), {"message": "Is Fresh Action chewing gum okay?"}, format="multipart"
            )
        instruction = gen.call_args.args[0]
        self.assertIn("OUR DATA", instruction)
        self.assertIn("never identify a pill".lower(), instruction.lower().replace("never identify a pill, capsule or tablet", "never identify a pill"))
        self.assertIn("Fresh Action", instruction)

    def test_emergency_detection(self):
        self.assertIsNotNone(emergency_notice("he may have taken an overdose"))
        self.assertIsNotNone(emergency_notice("I can't breathe properly"))
        self.assertIsNone(emergency_notice("which foods are high in fibre?"))


class ThreadsFeedbackSettingsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.other = User.objects.create_user(username="bayo", password="strongpassword123")
        self.client.force_authenticate(self.user)
        self.thread = ChatThread.objects.create(user=self.user, title="Diabetes diet")
        self.q = ChatMessage.objects.create(thread=self.thread, role="user", text="what can I eat?")
        self.a = ChatMessage.objects.create(thread=self.thread, role="assistant", text="Vegetables.")
        self.theirs = ChatThread.objects.create(user=self.other, title="private")
        self.their_answer = ChatMessage.objects.create(thread=self.theirs, role="assistant", text="secret")

    def test_thread_list_shows_only_my_threads(self):
        titles = [t["title"] for t in self.client.get(reverse("assistant-threads")).data]
        self.assertEqual(titles, ["Diabetes diet"])

    def test_thread_detail_returns_messages_and_hides_other_users_threads(self):
        resp = self.client.get(reverse("assistant-thread", args=[self.thread.id]))
        self.assertEqual([m["role"] for m in resp.data["messages"]], ["user", "assistant"])
        self.assertEqual(self.client.get(reverse("assistant-thread", args=[self.theirs.id])).status_code, 404)

    def test_delete_one_thread(self):
        self.assertEqual(self.client.delete(reverse("assistant-thread", args=[self.thread.id])).status_code, 204)
        self.assertFalse(ChatThread.objects.filter(pk=self.thread.id).exists())
        self.assertEqual(self.client.delete(reverse("assistant-thread", args=[self.theirs.id])).status_code, 404)
        self.assertTrue(ChatThread.objects.filter(pk=self.theirs.id).exists())

    def test_delete_all_my_chats_leaves_other_users_alone(self):
        ChatThread.objects.create(user=self.user, title="another")
        self.client.delete(reverse("assistant-threads"))
        self.assertFalse(ChatThread.objects.filter(user=self.user).exists())
        self.assertTrue(ChatThread.objects.filter(user=self.other).exists())

    def test_feedback_can_be_set_changed_and_cleared(self):
        url = reverse("assistant-feedback", args=[self.a.id])
        self.assertEqual(self.client.post(url, {"value": 1}, format="json").data["feedback"], 1)
        self.client.post(url, {"value": -1, "note": "too vague"}, format="json")
        self.a.refresh_from_db()
        self.assertEqual((self.a.feedback, self.a.feedback_note), (-1, "too vague"))
        self.client.post(url, {"value": 0}, format="json")
        self.a.refresh_from_db()
        self.assertEqual((self.a.feedback, self.a.feedback_note), (None, ""))

    def test_feedback_rules(self):
        self.assertEqual(self.client.post(reverse("assistant-feedback", args=[self.a.id]), {"value": 5}, format="json").status_code, 400)
        # not on my own question, and not on someone else's answer
        self.assertEqual(self.client.post(reverse("assistant-feedback", args=[self.q.id]), {"value": 1}, format="json").status_code, 404)
        self.assertEqual(self.client.post(reverse("assistant-feedback", args=[self.their_answer.id]), {"value": 1}, format="json").status_code, 404)

    def test_settings_default_to_no_training_use(self):
        data = self.client.get(reverse("assistant-settings")).data
        self.assertEqual(data, {"health_notes": "", "allow_training_use": False})

    def test_health_notes_are_saved_and_limited(self):
        url = reverse("assistant-settings")
        self.assertEqual(self.client.patch(url, {"health_notes": "On metformin"}, format="json").data["health_notes"], "On metformin")
        self.assertEqual(self.client.patch(url, {"health_notes": "x" * 501}, format="json").status_code, 400)

    def test_withdrawing_consent_clears_training_eligibility_of_all_my_messages(self):
        ChatMessage.objects.filter(thread=self.thread).update(training_ok=True)
        url = reverse("assistant-settings")
        self.client.patch(url, {"allow_training_use": True}, format="json")
        self.assertTrue(ChatMessage.objects.filter(thread=self.thread, training_ok=True).exists())
        self.client.patch(url, {"allow_training_use": False}, format="json")
        self.assertFalse(ChatMessage.objects.filter(thread=self.thread, training_ok=True).exists())

    def test_settings_are_per_user(self):
        self.client.patch(reverse("assistant-settings"), {"health_notes": "mine"}, format="json")
        self.other.refresh_from_db()
        self.assertEqual(self.other.health_notes, "")


class TrainingExportTests(APITestCase):
    def _chat(self, user, q, a, *, consent, feedback=None, note=""):
        thread = ChatThread.objects.create(user=user, title=q[:20])
        ChatMessage.objects.create(thread=thread, role="user", text=q, training_ok=consent)
        ChatMessage.objects.create(thread=thread, role="assistant", text=a, training_ok=consent, feedback=feedback, feedback_note=note)

    def _export(self):
        with tempfile.TemporaryDirectory() as out:
            call_command("export_training_data", out=out, stdout=io.StringIO())
            def read(name):
                with open(os.path.join(out, name), encoding="utf-8") as handle:
                    return [json.loads(line) for line in handle if line.strip()]
            return read("good.jsonl"), read("review.jsonl")

    def test_only_consented_and_rated_conversations_are_exported(self):
        user = User.objects.create_user(username="ada", password="strongpassword123")
        self._chat(user, "consented and liked", "answer one", consent=True, feedback=1)
        self._chat(user, "consented but unrated", "answer two", consent=True)
        self._chat(user, "liked but NOT consented", "answer three", consent=False, feedback=1)
        good, review = self._export()
        self.assertEqual([t["messages"][0]["content"] for t in good], ["consented and liked"])
        self.assertEqual(review, [])

    def test_thumbs_down_answers_go_to_the_review_file_with_the_note(self):
        user = User.objects.create_user(username="ada", password="strongpassword123")
        self._chat(user, "dose question", "take 5 tablets", consent=True, feedback=-1, note="unsafe, mentions a dose")
        good, review = self._export()
        self.assertEqual(good, [])
        self.assertEqual(review[0]["note"], "unsafe, mentions a dose")

    def test_the_export_is_anonymised(self):
        user = User.objects.create_user(username="adaobi_secret", password="strongpassword123", email="ada@example.com")
        self._chat(
            user, "call me on 0803 123 4567 or ada@example.com, my NIN is 12345678901",
            "ok", consent=True, feedback=1,
        )
        good, _ = self._export()
        blob = json.dumps(good)
        for secret in ("0803", "ada@example.com", "12345678901", "adaobi_secret"):
            self.assertNotIn(secret, blob)
        self.assertIn("[phone]", blob)
        self.assertIn("[email]", blob)
        self.assertIn("[number]", blob)
        self.assertNotIn("user", good[0])  # no user id field at all

    def test_scrub_helper(self):
        self.assertEqual(scrub_for_test("mail a.b@x.ng now"), "mail [email] now")

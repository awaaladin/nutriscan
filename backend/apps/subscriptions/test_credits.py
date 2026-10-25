from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from . import credits
from .models import AiUsage, Subscription

User = get_user_model()
GENERATE = "apps.assistant.views.generate"
USAGE = {"model": "gemini-3.5-flash-lite", "prompt_tokens": 1800, "output_tokens": 240, "search_queries": 0}
REPLY = {"answer": "Fine in small portions.", "sources": [], "web_research": False, "usage": USAGE}


def make_member(user, tier):
    Subscription.objects.update_or_create(
        user=user, defaults={"tier": tier, "status": "active", "expires_at": timezone.now() + timedelta(days=20)}
    )
    user.is_pro = True
    user.save(update_fields=["is_pro"])


class CreditTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.client.force_authenticate(self.user)

    def chat(self, **data):
        with patch(GENERATE, return_value=REPLY) as gen:
            response = self.client.post(reverse("assistant-chat"), {"message": "Is garri ok?", **data}, format="multipart")
        return response, gen

    def test_allowance_by_tier(self):
        self.assertEqual(credits.balance(self.user)["monthly_allowance"], 25)
        for tier, allowance in (("pro", 250), ("plus", 500), ("care", 750)):
            make_member(self.user, tier)
            self.assertEqual(credits.balance(self.user)["monthly_allowance"], allowance)

    def test_each_answer_is_charged_and_its_real_cost_logged(self):
        response, _ = self.chat()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["credits_left"], 24)
        usage = AiUsage.objects.get()
        self.assertEqual((usage.action, usage.credits, usage.prompt_tokens), ("chat", 1, 1800))
        # 1800 x $0.30/M + 240 x $2.50/M on Flash-Lite
        self.assertAlmostEqual(float(usage.cost_usd), 0.00114, places=5)

    def test_a_failed_answer_costs_nothing(self):
        from apps.integrations.vision_identify import IdentifyError

        with patch(GENERATE, side_effect=IdentifyError("ai_error", "down")):
            self.client.post(reverse("assistant-chat"), {"message": "hi"}, format="multipart")
        self.assertFalse(AiUsage.objects.exists())

    def test_out_of_credits_is_a_clear_402(self):
        AiUsage.objects.create(user=self.user, action="chat", credits=25, created_at=timezone.now())
        AiUsage.objects.filter(user=self.user).update(created_at=timezone.now() - timedelta(hours=2))
        response, gen = self.chat()
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(response.data["reason"], "out_of_credits")
        self.assertIn("renews_on", response.data)
        gen.assert_not_called()

    def test_topup_credits_are_spent_after_the_allowance(self):
        AiUsage.objects.create(user=self.user, action="chat", credits=25)
        AiUsage.objects.filter(user=self.user).update(created_at=timezone.now() - timedelta(hours=2))
        self.user.bonus_credits = 5
        self.user.save()
        response, _ = self.chat()
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bonus_credits, 4)

    @override_settings(AI_CREDITS_PER_HOUR=3)
    def test_heavy_use_gets_an_honest_cooldown(self):
        for _ in range(3):
            self.assertEqual(self.chat()[0].status_code, 200)
        response, gen = self.chat()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["reason"], "cooldown")
        self.assertIn("minute", response.data["detail"])
        self.assertNotIn("server", response.data["detail"].lower())  # never blames a fake outage
        self.assertGreaterEqual(response.data["retry_after_minutes"], 1)
        gen.assert_not_called()

    def test_research_mode_is_for_members_and_searches_trusted_sources(self):
        response, gen = self.chat(research=True)
        self.assertEqual(response.data["reason"], "upgrade_required")
        gen.assert_not_called()

        make_member(self.user, "pro")
        researched = {**REPLY, "web_research": True,
                      "sources": [{"title": "who.int", "url": "https://x"}, {"title": "someblog.ng", "url": "https://y"}]}
        with patch(GENERATE, return_value=researched) as gen:
            response = self.client.post(reverse("assistant-chat"), {"message": "Is zobo good for BP?", "research": True},
                                        format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(gen.call_args.kwargs["search"])
        self.assertIn("RESEARCH MODE IS ON", gen.call_args.args[0])
        self.assertEqual([s["trusted"] for s in response.data["message"]["sources"]], [True, False])
        self.assertEqual(AiUsage.objects.get().credits, 10)

    def test_research_that_could_not_search_is_charged_as_a_normal_answer(self):
        make_member(self.user, "pro")
        self.chat(research=True)
        self.assertEqual(AiUsage.objects.get().credits, 1)

    def test_ordinary_chat_never_pays_for_web_search_and_keeps_six_turns(self):
        _, gen = self.chat()
        self.assertFalse(gen.call_args.kwargs["search"])
        self.assertEqual(gen.call_args.kwargs["max_history"], 6)
        self.assertEqual(gen.call_args.kwargs["max_answer_tokens"], 600)

    def test_credits_endpoint(self):
        make_member(self.user, "care")
        data = self.client.get(reverse("credits")).data
        self.assertEqual((data["tier"], data["monthly_remaining"]), ("care", 750))

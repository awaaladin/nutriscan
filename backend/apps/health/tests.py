from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.assistant.context import build_context
from apps.subscriptions.models import AiUsage
from apps.subscriptions.test_credits import make_member

from .models import HealthLog

User = get_user_model()
WRITE = "apps.health.ai.generate"


class HealthLogTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123", height_cm=165)
        self.client.force_authenticate(self.user)

    def log(self, **data):
        return self.client.post(reverse("health-logs"), data, format="json")

    def test_each_tracker_unlocks_with_its_plan(self):
        weight = {"kind": "weight", "value": 82.5}
        bp = {"kind": "blood_pressure", "systolic": 138, "diastolic": 88}
        sugar = {"kind": "glucose", "value": 145, "timing": "fasting"}
        self.assertEqual(self.log(**weight).data["reason"], "upgrade_required")
        make_member(self.user, "pro")
        self.assertEqual(self.log(**weight).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.log(**bp).data["required_tier"], "plus")
        make_member(self.user, "plus")
        self.assertEqual(self.log(**bp).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.log(**sugar).data["required_tier"], "care")
        make_member(self.user, "care")
        self.assertEqual(self.log(**sugar).status_code, status.HTTP_201_CREATED)

    def test_impossible_readings_are_rejected(self):
        make_member(self.user, "care")
        self.assertEqual(self.log(kind="blood_pressure", systolic=80, diastolic=120).status_code, 400)
        self.assertEqual(self.log(kind="glucose", value=5000).status_code, 400)
        self.assertEqual(self.log(kind="weight", value=None).status_code, 400)

    def test_dangerous_readings_carry_an_urgent_alert(self):
        make_member(self.user, "care")
        low = self.log(kind="glucose", value=55, timing="random").data
        self.assertIn("low blood sugar", low["alert"])
        self.assertIn("112", low["alert"])
        crisis = self.log(kind="blood_pressure", systolic=190, diastolic=110).data
        self.assertIn("dangerously high", crisis["alert"])
        self.assertIsNone(self.log(kind="glucose", value=110, timing="fasting").data["alert"])

    def test_summary_trends_and_targets(self):
        make_member(self.user, "care")
        now = timezone.now()
        HealthLog.objects.create(user=self.user, kind="weight", value=85, measured_at=now - timedelta(days=20))
        HealthLog.objects.create(user=self.user, kind="weight", value=82, measured_at=now)
        HealthLog.objects.create(user=self.user, kind="glucose", value=120, timing="fasting", measured_at=now)
        HealthLog.objects.create(user=self.user, kind="glucose", value=210, timing="after_meal", measured_at=now)
        data = self.client.get(reverse("health-summary")).data
        self.assertEqual(data["weight"]["change_kg"], -3.0)
        self.assertEqual(data["weight"]["bmi"], 30.1)
        self.assertEqual(data["glucose"]["in_target_pct"], 50)
        self.assertTrue(data["unlocked"]["doctor_summary"])

    def test_the_assistant_sees_the_users_readings(self):
        HealthLog.objects.create(user=self.user, kind="glucose", value=160, timing="after_meal", measured_at=timezone.now())
        self.assertIn("Blood glucose", build_context(self.user, "what should I eat"))

    def test_readings_belong_to_one_account(self):
        other = User.objects.create_user(username="bayo", password="strongpassword123")
        theirs = HealthLog.objects.create(user=other, kind="weight", value=70, measured_at=timezone.now())
        self.assertEqual(self.client.get(reverse("health-logs")).data, [])
        response = self.client.delete(reverse("health-log-detail", args=[theirs.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class HealthToolTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123", is_diabetic=True)
        self.client.force_authenticate(self.user)

    def test_meal_plan_needs_plus_and_costs_three_credits(self):
        make_member(self.user, "pro")
        self.assertEqual(self.client.post(reverse("health-tool", args=["meal_plan"])).data["required_tier"], "plus")
        make_member(self.user, "plus")
        reply = {"answer": "Monday: moi moi and pap.", "sources": [], "web_research": False, "usage": {}}
        with patch(WRITE, return_value=reply) as gen:
            response = self.client.post(reverse("health-tool", args=["meal_plan"]), {"note": "No beef"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["text"], "Monday: moi moi and pap.")
        self.assertIn("Nigerian", gen.call_args.args[0])
        self.assertIn("No beef", gen.call_args.args[2])
        self.assertEqual(AiUsage.objects.get().credits, 3)

    def test_doctor_summary_is_pro_care(self):
        make_member(self.user, "plus")
        response = self.client.post(reverse("health-tool", args=["doctor_summary"]))
        self.assertEqual(response.data["required_tier"], "care")

    def test_unknown_tool(self):
        self.assertEqual(self.client.post(reverse("health-tool", args=["horoscope"])).status_code, 404)

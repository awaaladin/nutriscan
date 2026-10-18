from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.scans.models import Scan

from .models import Product
from .scoring_helpers import profile_for

User = get_user_model()
BARCODE = "6154000256692"


def gum(**extra):
    fields = dict(
        barcode=BARCODE, name="Fresh Action Chewing Gum", brand="Mentos", sugar_g=72.1, saturated_fat_g=0.0,
        sodium_mg=9.0, calories_kcal=380.0, carbohydrates_g=97.0, ingredients_text="Sugar, gum base, glucose syrup",
    )
    fields.update(extra)
    return Product.objects.create(**fields)


def make_user(name="ada", **extra):
    return User.objects.create_user(username=name, password="strongpassword123", **extra)


class PersonalVerdictApiTests(APITestCase):
    def scan(self, user, barcode=BARCODE):
        self.client.force_authenticate(user)
        return self.client.post(reverse("scan"), {"barcode": barcode}, format="json")

    def test_a_diabetic_user_gets_a_personal_avoid_for_a_sugary_gum(self):
        gum()
        resp = self.scan(make_user(is_diabetic=True))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        fy = resp.data["for_you"]
        self.assertEqual(fy["verdict"], "Avoid")
        self.assertEqual(fy["conditions"], ["diabetes"])
        self.assertTrue(fy["reasons"])
        self.assertEqual(resp.data["label"], "Moderate")  # the universal score is unchanged for everyone

    def test_a_user_with_no_conditions_gets_no_personal_verdict(self):
        gum()
        self.assertIsNone(self.scan(make_user()).data["for_you"])

    def test_the_health_goal_counts_even_without_the_condition_ticked(self):
        gum()
        resp = self.scan(make_user(primary_goal="diabetes"))
        self.assertEqual(resp.data["for_you"]["conditions"], ["diabetes"])

    def test_an_allergy_in_the_health_notes_flags_a_matching_ingredient(self):
        gum(ingredients_text="Sugar, peanut oil, flavour", sugar_g=1, carbohydrates_g=5)
        resp = self.scan(make_user(health_notes="Allergic to peanuts. Takes metformin."))
        fy = resp.data["for_you"]
        self.assertEqual(fy["verdict"], "Avoid")
        self.assertIn("peanut", " ".join(fy["reasons"]))

    def test_every_scan_response_explains_its_score(self):
        gum()
        data = self.scan(make_user()).data
        self.assertTrue(any("Sugar: 72.1 g" in r for r in data["reasons"]))
        self.assertTrue(data["diabetic_reasons"])
        self.assertFalse(data["beverage"])

    def test_a_cola_is_judged_as_a_drink(self):
        gum(barcode="111", name="Coca-Cola Classic", sugar_g=10.6, saturated_fat_g=0, sodium_mg=10,
            ingredients_text="Carbonated water, sugar, colour")
        data = self.scan(make_user(), "111").data
        self.assertTrue(data["beverage"])
        self.assertIn("high_sugar", data["flags"])

    def test_sugar_free_gum_is_not_flagged_for_a_diabetic(self):
        gum(barcode="222", name="Orbit Sugarfree Gum", sugar_g=0.5, saturated_fat_g=0, sodium_mg=5, carbohydrates_g=65,
            ingredients_text="Sorbitol, gum base, sugar free flavours, aspartame")
        data = self.scan(make_user(is_diabetic=True), "222").data
        self.assertEqual(data["diabetic_risk"], "Safe")
        self.assertNotEqual(data["for_you"]["verdict"], "Avoid")

    def test_history_rows_carry_the_personal_verdict_for_their_owner(self):
        product = gum()
        ada = make_user(is_diabetic=True)
        bayo = make_user("bayo")
        for user in (ada, bayo):
            Scan.objects.create(user=user, product=product, score=7, label="Good", diabetic_risk="Safe", flags=[])
        self.client.force_authenticate(ada)
        row = self.client.get(reverse("history")).data[0]
        self.assertEqual(row["for_you"]["verdict"], "Avoid")
        self.assertEqual(row["label"], "Moderate")
        self.client.force_authenticate(bayo)
        self.assertIsNone(self.client.get(reverse("history")).data[0]["for_you"])

    def test_non_food_history_rows_are_left_alone(self):
        med = gum(barcode="999", product_type="medicine")
        user = make_user(is_diabetic=True)
        Scan.objects.create(user=user, product=med, score=5, label="Moderate", diabetic_risk="Safe", flags=[])
        self.client.force_authenticate(user)
        self.assertNotIn("for_you", self.client.get(reverse("history")).data[0])

    def test_the_ask_screen_gives_the_ai_the_personal_verdict_to_explain(self):
        gum()
        self.client.force_authenticate(make_user(is_diabetic=True))
        reply = {"answer": "x", "sources": [], "web_research": False}
        with patch("apps.products.qa_view.ask_about_product", return_value=reply) as ask:
            self.client.post(reverse("product-ask", args=[BARCODE]), {"question": "ok for me?"}, format="json")
        context = ask.call_args.args[0]
        self.assertIn("VERDICT FOR THIS USER (diabetes): Avoid", context)
        self.assertIn("do not contradict", context)

    def test_the_assistant_sees_the_personal_verdict_for_products_it_mentions(self):
        gum()
        user = make_user(is_diabetic=True)
        from apps.assistant.context import build_context

        context = build_context(user, "Is Fresh Action Chewing Gum bad for me?")
        self.assertIn("For THIS user (diabetes): Avoid", context)


class ProfileTests(APITestCase):
    def test_goals_map_to_conditions(self):
        self.assertTrue(profile_for(make_user("a", primary_goal="diabetes")).diabetic)
        self.assertTrue(profile_for(make_user("b", primary_goal="hypertension")).hypertension)
        self.assertTrue(profile_for(make_user("c", primary_goal="weight_loss")).weight_loss)
        none = profile_for(make_user("d"))
        self.assertFalse(none.has_conditions())

    def test_ticked_conditions_and_notes_count(self):
        profile = profile_for(make_user("e", is_diabetic=True, has_hypertension=True, health_notes="allergic to eggs"))
        self.assertTrue(profile.diabetic and profile.hypertension)
        self.assertEqual(profile.allergens, ["egg"])

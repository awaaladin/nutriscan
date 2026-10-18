import io
import json
import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.assistant.context import build_context
from apps.assistant.models import ChatMessage, ChatThread
from apps.integrations.vision_identify import IdentifyError
from apps.products.models import Product
from apps.scans.models import Scan

from . import corrections, off, web_ai
from .agent import research_product
from .knowledge import relevant_entries
from .matching import agreement, barcode_country, match_score, values_agree
from .models import DataCorrection, KnowledgeEntry, ProductEvidence, ResearchRun
from .trust import data_trust

User = get_user_model()
SEARCH = "apps.research.agent.off.search"
WEB = "apps.research.agent.web_ai.research"
NIGERIA = "en:nigeria"
PEAK = dict(sugar_g=39.0, saturated_fat_g=5.5, sodium_mg=110.0, calories_kcal=370.0)


def user(name="ada", age_days=60, **extra):
    u = User.objects.create_user(username=name, password="strongpassword123", **extra)
    User.objects.filter(pk=u.pk).update(date_joined=timezone.now() - timedelta(days=age_days))
    u.refresh_from_db()
    return u


def product(**extra):
    fields = dict(barcode="6154000256692", name="Peak Milk", brand="Peak", source="ai_vision", is_estimated=True)
    fields.update(extra)
    return Product.objects.create(**fields)


def candidate(name="Peak Milk", brands=("Peak",), countries=(NIGERIA,), code="8716200449250", facts=None, ingredients=""):
    return {
        "code": code, "name": name, "brands": list(brands), "countries": list(countries),
        "facts": facts if facts is not None else dict(PEAK), "ingredients_text": ingredients,
        "url": f"https://world.openfoodfacts.org/product/{code}",
    }


class MatchingTests(SimpleTestCase):
    def test_nigerian_barcode_prefix_gives_the_country(self):
        self.assertEqual(barcode_country("6154000256692"), NIGERIA)
        self.assertIsNone(barcode_country("5000112637922"))
        self.assertIsNone(barcode_country("12345"))

    def test_same_name_brand_and_country_is_a_strong_match(self):
        self.assertGreaterEqual(match_score("Peak Milk", "Peak", NIGERIA, "Peak Milk", ["Peak"], [NIGERIA, "en:togo"]), 0.9)

    def test_a_different_countrys_version_is_never_a_match(self):
        # Milo in Australia is not Milo in Nigeria: same name and brand, different formulation
        score = match_score("Milo", "Nestle", NIGERIA, "Milo", ["Nestle", "Milo"], ["en:australia"])
        self.assertLessEqual(score, 0.4)

    def test_a_different_brand_is_penalised(self):
        self.assertLess(match_score("Peak Milk", "Peak", NIGERIA, "Peak Milk", ["Cowbell"], [NIGERIA]), 0.6)

    def test_unknown_country_lowers_confidence_but_can_still_match(self):
        score = match_score("Peak Milk", "Peak", None, "Peak Milk", ["Peak"], [NIGERIA])
        self.assertTrue(0.6 <= score < 1.0)

    def test_value_agreement_uses_relative_and_absolute_tolerance(self):
        self.assertTrue(values_agree("sugar_g", 39.0, 41.0))
        self.assertFalse(values_agree("sugar_g", 39.0, 55.0))
        self.assertTrue(values_agree("sodium_mg", 9.0, 20.0))  # small numbers: absolute tolerance
        self.assertFalse(values_agree("sodium_mg", 9.0, 300.0))

    def test_agreement_counts_only_fields_both_sources_have(self):
        self.assertEqual(agreement({"sugar_g": 39.0, "sodium_mg": 110.0}, {"sugar_g": 40.0, "protein_g": 7.0}), (1, 0, 1))
        self.assertEqual(agreement({"sugar_g": 39.0, "sodium_mg": 110.0}, {"sugar_g": 5.0, "sodium_mg": 900.0}), (0, 2, 2))


class OpenFoodFactsParsingTests(SimpleTestCase):
    def test_nutrition_is_converted_to_our_units(self):
        facts = off.normalise_nutrition({"sugars_100g": 5, "salt_100g": 2.5, "energy-kj_100g": 418.4, "saturated-fat_100g": 1})
        self.assertEqual(facts["sodium_mg"], 1000.0)  # salt 2.5 g -> sodium 1 g -> 1000 mg
        self.assertAlmostEqual(facts["calories_kcal"], 100.0, places=1)
        self.assertEqual(facts["sugar_g"], 5.0)

    def test_missing_or_bad_nutriments_give_nothing(self):
        self.assertEqual(off.normalise_nutrition(None), {})
        self.assertEqual(off.normalise_nutrition({"sugars_100g": "n/a"}), {})

    def test_emoji_and_symbols_are_stripped_from_queries(self):
        self.assertEqual(off.clean_text("Fresh Action \U0001F353 Chewing Gum"), "Fresh Action  Chewing Gum")

    def test_network_failure_returns_no_candidates_instead_of_raising(self):
        with patch("apps.research.off.requests.get", side_effect=requests.ConnectionError()):
            self.assertEqual(off.search("Peak Milk"), [])


class ResearchAgentTests(APITestCase):
    def test_a_matching_source_fills_only_blanks_when_it_agrees_on_what_we_already_hold(self):
        p = product(sugar_g=39.0, sodium_mg=110.0)  # partial: lets the sources be cross-checked
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            outcome = research_product(p)
        p.refresh_from_db()
        self.assertEqual((p.sugar_g, p.sodium_mg), (39.0, 110.0))  # never overwritten
        self.assertEqual((p.saturated_fat_g, p.calories_kcal), (5.5, 370.0))  # blanks filled
        self.assertCountEqual(outcome["applied"], ["saturated_fat_g", "calories_kcal"])
        self.assertEqual(p.evidence.get().status, ProductEvidence.Status.APPLIED)
        self.assertTrue(p.is_estimated)

    def test_a_source_from_another_country_is_kept_for_reference_and_never_used(self):
        p = product(sugar_g=39.0, sodium_mg=110.0)
        other = candidate(countries=("en:australia",), facts=dict(sugar_g=45.0, saturated_fat_g=0.1, sodium_mg=40.0))
        with patch(SEARCH, return_value=[other]), patch(WEB, return_value=None):
            outcome = research_product(p)
        p.refresh_from_db()
        self.assertIsNone(p.saturated_fat_g)
        self.assertEqual(outcome["applied"], [])
        self.assertEqual(p.evidence.get().status, ProductEvidence.Status.REFERENCE)

    def test_a_lone_source_with_nothing_to_cross_check_is_only_a_suggestion(self):
        p = product()  # we hold no values at all
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            outcome = research_product(p)
        p.refresh_from_db()
        self.assertIsNone(p.sugar_g)  # conservative: not applied on one source's word
        self.assertEqual(outcome["applied"], [])
        self.assertEqual(p.evidence.get().status, ProductEvidence.Status.SUGGESTED)

    def test_a_perfect_match_agreeing_on_one_value_corroborates_but_fills_nothing(self):
        p = product(sugar_g=39.0)  # one comparable field: too little to copy other values from
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            outcome = research_product(p)
        p.refresh_from_db()
        self.assertEqual(outcome["applied"], [])
        self.assertIsNone(p.saturated_fat_g)
        self.assertEqual(p.evidence.get().status, ProductEvidence.Status.AGREES)
        self.assertEqual(outcome["trust"]["level"], "corroborated")

    def test_a_weaker_match_agreeing_on_one_value_is_only_a_suggestion(self):
        # no recognisable country prefix on our barcode: we can't confirm it's the same market
        p = product(barcode="5000000000001", sugar_g=39.0)
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            research_product(p)
        evidence = p.evidence.get()
        self.assertTrue(0.6 <= evidence.match_score < 0.9)
        self.assertEqual(evidence.status, ProductEvidence.Status.SUGGESTED)

    def test_a_strong_conflict_is_flagged_for_review_and_nothing_is_overwritten(self):
        p = product(sugar_g=2.0, sodium_mg=900.0)
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            outcome = research_product(p)
        p.refresh_from_db()
        self.assertEqual((p.sugar_g, p.sodium_mg), (2.0, 900.0))
        self.assertEqual(p.evidence.get().status, ProductEvidence.Status.CONFLICTS)
        self.assertEqual(len(outcome["conflicts"]), 1)
        open_ones = DataCorrection.objects.filter(product=p, status="open", user__isnull=True)
        self.assertEqual({c.field for c in open_ones}, {"sugar_g", "sodium_mg"})

    def test_running_again_does_not_duplicate_evidence_or_corrections(self):
        p = product(sugar_g=2.0, sodium_mg=900.0)
        for _ in range(2):
            with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
                research_product(p)
        self.assertEqual(p.evidence.count(), 1)
        self.assertEqual(DataCorrection.objects.filter(product=p).count(), 2)

    def test_the_products_own_barcode_is_left_to_the_normal_scan_path(self):
        p = product(sugar_g=39.0, sodium_mg=110.0)
        with patch(SEARCH, return_value=[candidate(code=p.barcode)]), patch(WEB, return_value=None):
            research_product(p)
        self.assertEqual(p.evidence.count(), 0)

    def test_web_research_is_used_when_available_and_skipped_quietly_when_not(self):
        p = product(sugar_g=39.0, sodium_mg=110.0)
        web = {"url": "https://nestle.example/peak", "label": "Peak Milk - manufacturer", "score": 0.9,
               "facts": dict(PEAK), "ingredients": "Milk"}
        with patch(SEARCH, return_value=[]), patch(WEB, return_value=web):
            result = research_product(p)
        self.assertTrue(p.evidence.filter(source_type="web_ai").exists())
        self.assertIn("saturated_fat_g", result["applied"])
        q = product(barcode="6154000000001", name="Other Milk", sugar_g=1)
        with patch(SEARCH, return_value=[]), patch(WEB, return_value=None):
            skipped = research_product(q)
        self.assertTrue(any("web research isn't available" in s for s in skipped["skipped"]))

    def test_medicines_are_not_researched_as_food(self):
        med = product(product_type="medicine")
        with patch(SEARCH) as search:
            outcome = research_product(med)
        search.assert_not_called()
        self.assertTrue(outcome["skipped"])

    def test_every_run_is_remembered_even_when_it_finds_nothing(self):
        p = product()
        with patch(SEARCH, return_value=[]), patch(WEB, return_value=None):
            research_product(p)
        self.assertEqual(ResearchRun.objects.filter(product=p).count(), 1)


class TrustTests(APITestCase):
    def test_a_single_ai_record_is_unverified(self):
        trust = data_trust(product())
        self.assertEqual(trust["level"], "unverified")
        self.assertTrue(trust["evidence"])

    def test_two_independent_sources_agreeing_is_corroborated(self):
        p = product()
        ProductEvidence.objects.create(
            product=p, source_type="open_food_facts", source_ref="https://off.example/1", source_label="Peak Milk (nigeria)",
            status="agrees", match_score=0.95,
        )
        trust = data_trust(p)
        self.assertEqual(trust["level"], "corroborated")
        self.assertEqual(trust["sources"][0]["url"], "https://off.example/1")

    def test_two_records_of_the_same_kind_are_not_independent(self):
        p = product()  # origin: label photo
        ProductEvidence.objects.create(product=p, source_type="label_photo", source_label="second photo", status="agrees")
        self.assertEqual(data_trust(p)["level"], "unverified")

    def test_a_confirmed_nafdac_number_makes_it_verified(self):
        self.assertEqual(data_trust(product(nafdac_number="A4-1234", nafdac_verified=True))["level"], "verified")

    def test_an_open_food_facts_product_is_sourced(self):
        self.assertEqual(data_trust(product(source="off", is_estimated=False))["level"], "sourced")

    def test_a_conflict_is_shown_as_a_warning_not_hidden(self):
        p = product()
        ProductEvidence.objects.create(product=p, source_type="open_food_facts", source_label="Peak Milk", status="conflicts", match_score=0.9)
        self.assertTrue(data_trust(p)["warnings"])

    def test_reference_only_sources_are_not_listed_as_sources(self):
        p = product()
        ProductEvidence.objects.create(product=p, source_type="open_food_facts", source_ref="https://off.example/au",
                                       source_label="Milo (australia)", status="reference", match_score=0.3)
        self.assertEqual(data_trust(p)["sources"], [])

    def test_trust_is_on_every_product_response(self):
        p = product(sugar_g=1, saturated_fat_g=0, sodium_mg=1)
        client = self.client
        client.force_authenticate(user())
        self.assertIn("level", client.get(reverse("product-detail", args=[p.barcode])).data["data_trust"])


class CorrectionTests(APITestCase):
    def test_validation_messages_are_for_users(self):
        p = product(sugar_g=10.0)
        ada = user()
        for field, value in (("sugar_g", "abc"), ("sugar_g", "500"), ("nafdac_number", "nonsense"), ("name", "x"), ("ingredients_text", "")):
            with self.assertRaises(ValueError, msg=(field, value)):
                corrections.submit(ada, p, field, value)

    def test_repeating_the_value_we_already_have_is_not_a_correction(self):
        p = product(sugar_g=10.0)
        ada = user()
        for same in ("10", "10.0", "10,0", "10.02"):
            with self.assertRaises(ValueError, msg=same):
                corrections.submit(ada, p, "sugar_g", same)

    def test_a_genuinely_different_value_is_a_correction_even_if_it_is_within_source_tolerance(self):
        # 45 vs 39 is within the 15% two SOURCES may differ by, but a person saying 45 is correcting us
        p = product(sugar_g=39.0)
        correction, applied = corrections.submit(user(), p, "sugar_g", "45")
        self.assertEqual(correction.suggested_value, "45.0")
        self.assertFalse(applied)

    def test_one_vote_is_recorded_but_not_applied(self):
        p = product(sugar_g=10.0)
        _, applied = corrections.submit(user(), p, "sugar_g", "30")
        p.refresh_from_db()
        self.assertFalse(applied)
        self.assertEqual(p.sugar_g, 10.0)

    def test_three_established_users_agreeing_apply_the_correction(self):
        p = product(sugar_g=10.0)
        results = [corrections.submit(user(f"u{i}"), p, "sugar_g", v)[1] for i, v in enumerate(["30", "31", "29.5"])]
        p.refresh_from_db()
        self.assertEqual(results, [False, False, True])
        self.assertAlmostEqual(p.sugar_g, 30.0, places=1)  # the median
        self.assertTrue(p.evidence.filter(source_type="community", status="applied").exists())
        self.assertEqual(DataCorrection.objects.filter(status="accepted").count(), 3)

    def test_a_pile_of_brand_new_accounts_cannot_rewrite_the_data(self):
        p = product(sugar_g=10.0)
        for i in range(8):
            corrections.submit(user(f"new{i}", age_days=0), p, "sugar_g", "60")
        p.refresh_from_db()
        self.assertEqual(p.sugar_g, 10.0)  # 8 x 0.25 = 2.0, under the threshold

    def test_a_vetted_reviewer_alone_is_enough(self):
        p = product(sugar_g=10.0)
        _, applied = corrections.submit(user("pharm", is_verified_reviewer=True), p, "sugar_g", "30")
        self.assertTrue(applied)

    def test_the_same_person_voting_twice_still_counts_once(self):
        p = product(sugar_g=10.0)
        ada = user()
        for value in ("30", "31", "29"):
            corrections.submit(ada, p, "sugar_g", value)
        p.refresh_from_db()
        self.assertEqual(p.sugar_g, 10.0)
        self.assertEqual(DataCorrection.objects.filter(product=p, user=ada, status="open").count(), 1)

    def test_disagreeing_values_do_not_combine(self):
        p = product(sugar_g=10.0)
        for i, value in enumerate(["30", "55", "80"]):
            corrections.submit(user(f"d{i}"), p, "sugar_g", value)
        p.refresh_from_db()
        self.assertEqual(p.sugar_g, 10.0)

    def test_text_fields_need_identical_values(self):
        p = product()
        outcomes = [corrections.submit(user(f"n{i}"), p, "nafdac_number", v)[1] for i, v in enumerate(["a4-1234", "A4-1234", " A4-1234 "])]
        p.refresh_from_db()
        self.assertEqual(outcomes[-1], True)
        self.assertEqual(p.nafdac_number, "A4-1234")

    def test_a_research_conflict_plus_two_users_is_enough(self):
        p = product(sugar_g=2.0)
        DataCorrection.objects.create(product=p, user=None, field="sugar_g", current_value="2.0", suggested_value="39.0")
        corrections.submit(user("a"), p, "sugar_g", "39")
        _, applied = corrections.submit(user("b"), p, "sugar_g", "40")
        self.assertTrue(applied)

    def test_an_admin_can_accept_directly(self):
        p = product(sugar_g=2.0)
        c = DataCorrection.objects.create(product=p, user=None, field="sugar_g", suggested_value="39.0")
        corrections.accept(c)
        p.refresh_from_db()
        self.assertEqual(p.sugar_g, 39.0)
        self.assertTrue(p.evidence.filter(source_type="admin").exists())


class ResearchApiTests(APITestCase):
    def setUp(self):
        self.user = user()
        self.client.force_authenticate(self.user)
        self.p = product(sugar_g=39.0, sodium_mg=110.0)

    def test_research_returns_the_updated_scored_record_without_recording_a_scan(self):
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            resp = self.client.post(reverse("product-research", args=[self.p.barcode]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["research"]["ran"])
        self.assertIn("saturated_fat_g", resp.data["research"]["applied"])
        self.assertIn("level", resp.data["product"]["data_trust"])
        self.assertIn("for_you", resp.data)
        self.assertEqual(Scan.objects.count(), 0)

    def test_it_is_not_repeated_within_a_day(self):
        with patch(SEARCH, return_value=[]) as search, patch(WEB, return_value=None):
            self.client.post(reverse("product-research", args=[self.p.barcode]))
            again = self.client.post(reverse("product-research", args=[self.p.barcode]))
        self.assertEqual(search.call_count, 1)
        self.assertFalse(again.data["research"]["ran"])

    def test_requires_auth_and_a_known_product(self):
        self.assertEqual(self.client.post(reverse("product-research", args=["999"])).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(reverse("product-research", args=[self.p.barcode])).status_code, 401)

    def test_corrections_endpoint(self):
        url = reverse("product-corrections", args=[self.p.barcode])
        ok = self.client.post(url, {"field": "sugar_g", "value": "45", "reason": "label says 45"}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertFalse(ok.data["applied"])
        bad = self.client.post(url, {"field": "sugar_g", "value": "9000"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad.data["reason"], "bad_correction")


class SearchApiTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(user())
        product(barcode="6154000256692", name="Peak Milk Powder", brand="Peak", nafdac_number="A4-0001",
                sugar_g=39, saturated_fat_g=5, sodium_mg=100)
        product(barcode="6154000254667", name="Golden Morn Cereal", brand="Nestle", source="off", is_estimated=False,
                sugar_g=20, saturated_fat_g=1, sodium_mg=100)

    def search(self, q):
        return self.client.get(reverse("product-search"), {"q": q})

    def test_find_by_name_brand_barcode_and_nafdac(self):
        for q, expected in (("peak milk", "Peak Milk Powder"), ("nestle", "Golden Morn Cereal"),
                            ("06154000254667", "Golden Morn Cereal"), ("a4-0001", "Peak Milk Powder")):
            names = [r["name"] for r in self.search(q).data["results"]]
            self.assertEqual(names[0], expected, q)

    def test_results_carry_trust_and_the_verdict(self):
        row = next(r for r in self.search("golden morn").data["results"] if r["name"].startswith("Golden"))
        self.assertEqual(row["trust"]["level"], "sourced")
        self.assertIn("label", row)

    def test_a_search_route_is_not_mistaken_for_a_barcode(self):
        self.assertEqual(self.search("peak").status_code, 200)  # "search" must not hit the product-detail route

    def test_short_or_unmatched_queries(self):
        self.assertEqual(self.search("a").status_code, 400)
        self.assertEqual(self.search("zzzzqqq").data["results"], [])


class KnowledgeBaseTests(APITestCase):
    def test_only_approved_matching_entries_are_retrieved(self):
        KnowledgeEntry.objects.create(question="Can diabetics eat plantain every day?", answer="In portions.", approved=True)
        KnowledgeEntry.objects.create(question="Can diabetics eat yam every day?", answer="Draft", approved=False)
        found = relevant_entries("Is plantain okay for diabetics to eat daily?")
        self.assertEqual([e.answer for e in found], ["In portions."])
        self.assertEqual(relevant_entries("how do I cook rice"), [])

    def test_the_assistant_is_given_the_reviewed_answer(self):
        KnowledgeEntry.objects.create(question="How can I check a NAFDAC number?", answer="Use the NAFDAC Greenbook.", approved=True)
        context = build_context(user(), "How do I check a NAFDAC number properly?")
        self.assertIn("REVIEWED NUTRISCAN ANSWERS", context)
        self.assertIn("Use the NAFDAC Greenbook.", context)


class DatasetCommandTests(APITestCase):
    def _chat(self, u, q, a, consent=True, feedback=1):
        t = ChatThread.objects.create(user=u, title=q[:30])
        ChatMessage.objects.create(thread=t, role="user", text=q, training_ok=consent)
        ChatMessage.objects.create(thread=t, role="assistant", text=a, training_ok=consent, feedback=feedback)

    def test_candidates_come_only_from_consented_rated_general_questions_and_start_unapproved(self):
        u = user()
        self._chat(u, "Is plantain good for blood sugar control?", "In portions, yes.")
        self._chat(u, "Is plantain good for my own diabetes?", "personal")      # personal: skipped
        self._chat(u, "Is garri good for blood sugar control?", "Small portions.", consent=False)  # no consent
        self._chat(u, "Is yam good for blood sugar control?", "Small portions.", feedback=-1)       # not rated helpful
        self._chat(u, "short q", "x")
        out = io.StringIO()
        call_command("build_knowledge_base", stdout=out)
        entries = KnowledgeEntry.objects.all()
        self.assertEqual([e.question for e in entries], ["Is plantain good for blood sugar control?"])
        self.assertFalse(entries[0].approved)
        self.assertEqual(entries[0].source, "chat")

    def test_chat_candidates_are_scrubbed_of_personal_identifiers(self):
        self._chat(user(), "Can I email ada@example.com about sugar and diabetes advice?", "Call 08031234567 or ask a pharmacist.")
        call_command("build_knowledge_base", stdout=io.StringIO())
        # contains "I": treated as personal and skipped entirely; nothing leaks
        self.assertEqual(KnowledgeEntry.objects.count(), 0)

    def test_running_it_twice_does_not_duplicate(self):
        self._chat(user(), "Is plantain good for blood sugar control?", "In portions.")
        for _ in range(2):
            call_command("build_knowledge_base", stdout=io.StringIO())
        self.assertEqual(KnowledgeEntry.objects.count(), 1)

    def test_export_contains_only_approved_entries(self):
        KnowledgeEntry.objects.create(question="Approved question here", answer="A1", approved=True, topic="x")
        KnowledgeEntry.objects.create(question="Draft question here", answer="A2", approved=False)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kb.jsonl")
            call_command("export_knowledge_base", out=path, stdout=io.StringIO())
            rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
            call_command("export_knowledge_base", out=path, format="qa", stdout=io.StringIO())
            qa = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["messages"][1], {"role": "model", "content": "A1"})
        self.assertEqual(qa[0]["topic"], "x")

    def test_readiness_says_not_ready_with_little_data_and_why(self):
        out = io.StringIO()
        call_command("dataset_readiness", stdout=out)
        text = out.getvalue()
        self.assertIn("NOT READY", text)
        self.assertIn("1000 minimum", text)

    def test_the_bulk_research_command_runs_the_same_step(self):
        product(sugar_g=39.0, sodium_mg=110.0)
        out = io.StringIO()
        with patch(SEARCH, return_value=[candidate()]), patch(WEB, return_value=None):
            call_command("research_products", stdout=out)
        self.assertIn("Researched 1 products", out.getvalue())


class WebResearchGuardTests(SimpleTestCase):
    FOUND = ('```json\n{"name":"Peak Milk","brand":"Peak","country":"Nigeria","per_100g":{"sugar_g":39,"sodium_mg":110},'
             '"ingredients_text":"Milk"}\n```')

    def test_an_answer_from_memory_is_never_evidence(self):
        reply = {"answer": self.FOUND, "sources": [], "web_research": False}
        with patch("apps.research.web_ai.generate", return_value=reply):
            self.assertIsNone(web_ai.research(type("P", (), {"name": "Peak Milk", "brand": "Peak", "barcode": "6154000256692"})()))

    def test_a_cited_answer_becomes_evidence_with_its_source(self):
        reply = {"answer": self.FOUND, "sources": [{"title": "Peak Milk | Nestle", "url": "https://nestle.example/peak"}], "web_research": True}
        p = type("P", (), {"name": "Peak Milk", "brand": "Peak", "barcode": "6154000256692"})()
        with patch("apps.research.web_ai.generate", return_value=reply):
            result = web_ai.research(p)
        self.assertEqual(result["url"], "https://nestle.example/peak")
        self.assertEqual(result["facts"], {"sugar_g": 39.0, "sodium_mg": 110.0})
        self.assertGreaterEqual(result["score"], 0.6)

    def test_search_unavailable_means_no_evidence_and_no_wasted_call(self):
        p = type("P", (), {"name": "Peak Milk", "brand": "Peak", "barcode": "6154000256692"})()
        with patch("apps.research.web_ai.generate", side_effect=IdentifyError("search_unavailable", "no")) as gen:
            self.assertIsNone(web_ai.research(p))
        self.assertTrue(gen.call_args.kwargs["require_search"])

    def test_unparseable_or_not_found_answers_are_ignored(self):
        p = type("P", (), {"name": "X", "brand": "", "barcode": "1"})()
        for answer in ("I could not find it", '{"found": false}', "{not json}"):
            reply = {"answer": answer, "sources": [{"title": "t", "url": "https://x.example"}], "web_research": True}
            with patch("apps.research.web_ai.generate", return_value=reply):
                self.assertIsNone(web_ai.research(p), answer)

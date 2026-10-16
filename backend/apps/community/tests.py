import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.products.models import Product

from .integrity import compute_integrity, gtin_checksum_valid
from .models import ProductDispute, ProductReport
from .nafdac import normalize_nafdac_number

User = get_user_model()

VALID_EAN13 = "6001068591206"  # valid GS1 checksum
GOOD = "4006381333931"  # valid GS1 checksum


def assess(barcode=GOOD, db=False, nafdac=False, maker=False, reports=()):
    return compute_integrity(barcode, db, nafdac, maker, list(reports))


class IntegrityEngineTests(SimpleTestCase):
    def test_checksum(self):
        self.assertTrue(gtin_checksum_valid(GOOD))
        self.assertFalse(gtin_checksum_valid("4006381333932"))
        self.assertFalse(gtin_checksum_valid("abc"))

    def test_default_is_unverified(self):
        result = assess()
        self.assertEqual(result.tier, "unverified")
        self.assertEqual(result.confidence, "low")

    def test_open_food_facts_listing_alone_does_not_verify(self):
        self.assertEqual(assess(db=True).tier, "unverified")

    def test_nafdac_or_manufacturer_verification_gives_verified(self):
        self.assertEqual(assess(nafdac=True).tier, "verified")
        self.assertEqual(assess(maker=True).tier, "verified")

    def test_invalid_or_synthetic_barcode_is_suspicious(self):
        self.assertEqual(assess(barcode="1234567890123").tier, "suspicious")
        self.assertEqual(assess(barcode="AI-abc123").tier, "suspicious")

    def test_registry_verification_beats_a_bad_barcode_warning(self):
        self.assertEqual(assess(barcode="1234567890123", nafdac=True).tier, "verified")

    def test_enough_weighted_fake_reports_means_reported_fake(self):
        self.assertEqual(assess(reports=[("fake", 1.5), ("fake", 1.5)]).tier, "reported_fake")

    def test_a_single_lone_report_is_not_enough(self):
        self.assertEqual(assess(reports=[("fake", 1.0)]).tier, "unverified")

    def test_reports_override_a_registry_match(self):
        result = assess(nafdac=True, reports=[("fake", 2.0), ("fake", 2.0)])
        self.assertEqual(result.tier, "reported_fake")
        self.assertTrue(any("copy real registration numbers" in r for r in result.reasons))

    def test_both_sides_credible_is_disputed(self):
        self.assertEqual(assess(reports=[("fake", 2.0), ("real", 2.0)]).tier, "disputed")

    def test_many_real_reports_outvote_fakes(self):
        reports = [("fake", 3.0)] + [("real", 1.0)] * 5
        self.assertNotEqual(assess(reports=reports).tier, "reported_fake")

    def test_confidence_levels(self):
        self.assertEqual(assess(reports=[("real", 1)] * 3).confidence, "medium")
        self.assertEqual(assess(reports=[("real", 1)] * 10).confidence, "high")


class NafdacNumberTests(SimpleTestCase):
    def test_normalizes_plausible_numbers(self):
        self.assertEqual(normalize_nafdac_number(" a4-1234 "), "A4-1234")
        self.assertEqual(normalize_nafdac_number("NAFDAC: 04-8861"), "04-8861")
        self.assertEqual(normalize_nafdac_number("B1-6789L"), "B1-6789L")

    def test_rejects_junk(self):
        self.assertIsNone(normalize_nafdac_number("hello"))
        self.assertIsNone(normalize_nafdac_number("12"))
        self.assertIsNone(normalize_nafdac_number(""))
        self.assertIsNone(normalize_nafdac_number(None))


def _png(name="p.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _user(name, age_days=60, **extra):
    user = User.objects.create_user(username=name, password="strongpassword123", **extra)
    User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=age_days))
    user.refresh_from_db()
    return user


@override_settings(MEDIA_ROOT="/tmp/nutriscan-test-media")
class ReportApiTests(APITestCase):
    def setUp(self):
        self.user = _user("ada")
        self.other = _user("bayo")
        self.product = Product.objects.create(barcode=VALID_EAN13, name="Milk", source="off")
        self.url = reverse("product-reports", args=[VALID_EAN13])

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_report_with_photos_is_saved(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            self.url,
            {"verdict": "fake", "comment": "Cap was loose", "where_bought": "Mile 12", "photos": [_png(), _png("b.png")]},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data["report"]["photos"]), 2)
        self.assertEqual(resp.data["integrity"]["fake_votes"], 1)

    def test_one_report_per_user_resubmit_updates(self):
        self.client.force_authenticate(self.user)
        self.client.post(self.url, {"verdict": "fake"}, format="json")
        resp = self.client.post(self.url, {"verdict": "real"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(ProductReport.objects.filter(product=self.product).count(), 1)
        self.assertEqual(resp.data["integrity"]["real_votes"], 1)
        self.assertEqual(resp.data["integrity"]["fake_votes"], 0)

    def test_rejects_non_image_and_too_many_photos(self):
        self.client.force_authenticate(self.user)
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        resp = self.client.post(self.url, {"verdict": "real", "photos": [bad]}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ProductReport.objects.filter(product=self.product).count(), 0)
        resp = self.client.post(
            self.url, {"verdict": "real", "photos": [_png(f"{i}.png") for i in range(5)]}, format="multipart"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hidden_reports_excluded_from_votes_and_list(self):
        report = ProductReport.objects.create(product=self.product, user=self.other, verdict="fake")
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(self.url).data["integrity"]["fake_votes"], 1)
        report.is_hidden = True
        report.save()
        data = self.client.get(self.url).data
        self.assertEqual(data["integrity"]["fake_votes"], 0)
        self.assertEqual(data["reports"], [])

    def test_flagging(self):
        report = ProductReport.objects.create(product=self.product, user=self.other, verdict="fake")
        flag_url = reverse("report-flag", args=[report.id])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(flag_url, {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(flag_url, {"reason": "spam"}, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post(flag_url, {}, format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(report.flags.count(), 1)

    def test_product_detail_includes_integrity_and_nafdac_fields(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse("product-detail", args=[VALID_EAN13]))
        self.assertIn("tier", resp.data["integrity"])
        self.assertFalse(resp.data["nafdac_verified"])


class ReputationWeightTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(barcode=VALID_EAN13, name="Milk", source="off")
        self.url = reverse("product-reports", args=[VALID_EAN13])

    def _fake_weight(self):
        viewer = _user("viewer")
        self.client.force_authenticate(viewer)
        return self.client.get(self.url).data["integrity"]["fake_weight"]

    def test_brand_new_accounts_count_for_little(self):
        for i in range(5):
            ProductReport.objects.create(product=self.product, user=_user(f"new{i}", age_days=0), verdict="fake")
        # five throwaway accounts must not be enough to call a product fake
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertLess(self._fake_weight(), 3.0)
        self.assertNotEqual(self.client.get(self.url).data["integrity"]["tier"], "reported_fake")

    def test_established_accounts_with_evidence_do_count(self):
        for i in range(2):
            report = ProductReport.objects.create(
                product=self.product, user=_user(f"old{i}"), verdict="fake", batch_number="B12"
            )
        viewer = _user("viewer")
        self.client.force_authenticate(viewer)
        self.assertEqual(self.client.get(self.url).data["integrity"]["fake_weight"], 3.0)

    def test_verified_reviewer_counts_triple(self):
        ProductReport.objects.create(
            product=self.product, user=_user("pharm", is_verified_reviewer=True), verdict="fake"
        )
        self.assertEqual(self._fake_weight(), 3.0)

    def test_nafdac_number_on_report_becomes_product_claim_but_not_verified(self):
        self.client.force_authenticate(_user("ada"))
        resp = self.client.post(self.url, {"verdict": "real", "nafdac_number": "a4-1234"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.nafdac_number, "A4-1234")
        self.assertFalse(self.product.nafdac_verified)
        self.assertEqual(resp.data["integrity"]["tier"], "unverified")

    def test_junk_nafdac_number_rejected(self):
        self.client.force_authenticate(_user("ada"))
        resp = self.client.post(self.url, {"verdict": "real", "nafdac_number": "nonsense"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_verified_product_shows_verified_tier(self):
        self.product.nafdac_number = "A4-1234"
        self.product.nafdac_verified = True
        self.product.save()
        self.client.force_authenticate(_user("ada"))
        self.assertEqual(self.client.get(self.url).data["integrity"]["tier"], "verified")


class AlertsAndDisputeTests(APITestCase):
    def setUp(self):
        self.viewer = _user("viewer")
        self.client.force_authenticate(self.viewer)
        self.product = Product.objects.create(barcode=VALID_EAN13, name="Fake Milk", source="off")

    def _fake_reports(self, n, product=None):
        for i in range(n):
            ProductReport.objects.create(
                product=product or self.product, user=_user(f"rep{product and product.id}{i}"),
                verdict="fake", where_bought="Mile 12", batch_number="B1",
            )

    def test_alerts_lists_products_over_the_fake_threshold_with_places(self):
        self._fake_reports(2)
        resp = self.client.get(reverse("alerts"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["barcode"], VALID_EAN13)
        self.assertEqual(resp.data[0]["tier"], "reported_fake")
        self.assertEqual(resp.data[0]["places"], ["Mile 12"])

    def test_a_single_report_does_not_create_an_alert(self):
        ProductReport.objects.create(product=self.product, user=_user("one"), verdict="fake")
        self.assertEqual(self.client.get(reverse("alerts")).data, [])

    def test_hidden_reports_do_not_alert(self):
        self._fake_reports(2)
        ProductReport.objects.update(is_hidden=True)
        self.assertEqual(self.client.get(reverse("alerts")).data, [])

    def test_dispute_is_queued_for_admin(self):
        resp = self.client.post(
            reverse("product-dispute", args=[VALID_EAN13]),
            {"company_name": "Acme Foods", "contact": "legal@acme.ng", "message": "Rival is mass reporting us.",
             "nafdac_number": "A4-1234"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        dispute = ProductDispute.objects.get()
        self.assertEqual(dispute.status, "open")
        self.assertEqual(dispute.nafdac_number, "A4-1234")
        # nothing about the product changes until an admin acts
        self.product.refresh_from_db()
        self.assertFalse(self.product.manufacturer_verified)

    def test_dispute_requires_message_and_contact(self):
        resp = self.client.post(reverse("product-dispute", args=[VALID_EAN13]), {"company_name": "Acme"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

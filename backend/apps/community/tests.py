import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.products.models import Product

from .integrity import compute_integrity, gtin_checksum_valid
from .models import ProductReport

User = get_user_model()

VALID_EAN13 = "6001068591209"  # valid GS1 checksum


class IntegrityEngineTests(SimpleTestCase):
    def test_checksum(self):
        self.assertTrue(gtin_checksum_valid("4006381333931"))
        self.assertFalse(gtin_checksum_valid("4006381333932"))
        self.assertFalse(gtin_checksum_valid("abc"))

    def test_independent_db_raises_prior(self):
        known = compute_integrity("4006381333931", in_independent_db=True, real_votes=0, fake_votes=0)
        unknown = compute_integrity("4006381333931", in_independent_db=False, real_votes=0, fake_votes=0)
        self.assertGreater(known.percent, unknown.percent)

    def test_invalid_or_synthetic_barcodes_start_low(self):
        self.assertLess(compute_integrity("1234567890123", True, 0, 0).percent, 20)
        self.assertLess(compute_integrity("AI-abc123", False, 0, 0).percent, 30)

    def test_fake_votes_pull_down_and_real_votes_pull_up(self):
        base = compute_integrity("4006381333931", True, 0, 0).percent
        self.assertLess(compute_integrity("4006381333931", True, 0, 6).percent, base)
        self.assertGreater(compute_integrity("4006381333931", True, 6, 0).percent, base)

    def test_single_vote_cannot_zero_out_a_product(self):
        self.assertGreater(compute_integrity("4006381333931", True, 0, 1).percent, 30)

    def test_confidence_levels(self):
        self.assertEqual(compute_integrity("4006381333931", True, 0, 0).confidence, "low")
        self.assertEqual(compute_integrity("4006381333931", True, 2, 1).confidence, "medium")
        self.assertEqual(compute_integrity("4006381333931", True, 10, 0).confidence, "high")


def _png(name="p.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT="/tmp/nutriscan-test-media")
class ReportApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="strongpassword123")
        self.other = User.objects.create_user(username="bayo", password="strongpassword123")
        self.product = Product.objects.create(barcode=VALID_EAN13, name="Milk", source="off")
        self.url = reverse("product-reports", args=[VALID_EAN13])

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_report_with_photos_updates_integrity(self):
        self.client.force_authenticate(self.user)
        before = self.client.get(self.url).data["integrity"]["percent"]
        resp = self.client.post(
            self.url,
            {"verdict": "fake", "comment": "Cap was loose", "where_bought": "Mile 12", "photos": [_png(), _png("b.png")]},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data["report"]["photos"]), 2)
        self.assertLess(resp.data["integrity"]["percent"], before)

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

    def test_product_detail_includes_integrity(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse("product-detail", args=[VALID_EAN13]))
        self.assertIn("percent", resp.data["integrity"])

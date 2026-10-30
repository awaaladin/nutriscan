"""Email: welcome, receipt, forgot-password. SMTP is never contacted (Django test mailbox)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.subscriptions.models import PaystackPayment
from apps.subscriptions.services import apply_paystack_transaction
from apps.users import mailer

User = get_user_model()


class MailerTests(TestCase):
    def test_a_broken_mail_server_never_raises(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")):
            self.assertFalse(mailer.send_email("a@example.com", "Hi", "welcome", {"name": "A"}))

    def test_user_text_is_escaped_and_subject_has_no_newlines(self):
        mailer.send_email("a@example.com", "Hi\nBcc: x@y.z", "welcome", {"name": "<script>x</script>"})
        message = mail.outbox[0]
        self.assertNotIn("\n", message.subject)
        self.assertNotIn("<script>", message.alternatives[0][0])

    def test_nothing_is_sent_when_the_transaction_rolls_back(self):
        from django.db import transaction

        try:
            with transaction.atomic():
                mailer.send_after_commit("a@example.com", "Hi", "welcome", {"name": "A"})
                raise RuntimeError("rolled back")
        except RuntimeError:
            pass
        self.assertEqual(len(mail.outbox), 0)


class WelcomeAndReceiptTests(TestCase):
    def test_registration_sends_a_welcome_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = APIClient().post("/api/auth/register/", {
                "username": "ada", "email": "ada@example.com", "password": "Strong-pass-1234!",
                "accept_terms": True, "health_consent": True,
            }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual([m.to for m in mail.outbox], [["ada@example.com"]])
        self.assertIn("Welcome", mail.outbox[0].subject)

    def test_a_paid_top_up_sends_one_receipt_even_if_reported_twice(self):
        user = User.objects.create_user("buyer", "buyer@example.com", "Strong-pass-1234!")
        PaystackPayment.objects.create(user=user, reference="NUTRISCAN-CREDITS-20261030-ABC", kind="credits", credits=50, amount_kobo=150000)
        data = {"status": "success", "currency": "NGN", "amount": 150000, "id": 77}
        with self.captureOnCommitCallbacks(execute=True):
            apply_paystack_transaction("NUTRISCAN-CREDITS-20261030-ABC", data)
            apply_paystack_transaction("NUTRISCAN-CREDITS-20261030-ABC", data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("1,500.00", mail.outbox[0].subject)
        self.assertIn("NUTRISCAN-CREDITS-20261030-ABC", mail.outbox[0].body)

    def test_a_failed_or_short_payment_sends_no_receipt(self):
        user = User.objects.create_user("buyer2", "buyer2@example.com", "Strong-pass-1234!")
        PaystackPayment.objects.create(user=user, reference="NUTRISCAN-CREDITS-20261030-DEF", kind="credits", credits=50, amount_kobo=150000)
        with self.captureOnCommitCallbacks(execute=True):
            apply_paystack_transaction("NUTRISCAN-CREDITS-20261030-DEF", {"status": "success", "currency": "NGN", "amount": 100})
        self.assertEqual(len(mail.outbox), 0)


@override_settings(PUBLIC_BASE_URL="https://nutri.test")
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reset", "reset@example.com", "Old-pass-12345!")
        mail.outbox.clear()

    def _parts(self):
        link = next(w for w in mail.outbox[-1].body.split() if w.startswith("https://nutri.test/reset-password/"))
        uid, token = link.partition("/reset-password/")[2].strip("/").split("/")
        return uid, token

    def test_api_flow_changes_the_password_once(self):
        c = APIClient()
        self.assertEqual(c.post("/api/auth/password-reset/", {"email": "reset@example.com"}, format="json").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        uid, token = self._parts()
        self.assertEqual(c.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "password": "123"}, format="json").status_code, 400)
        ok = c.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "password": "A-new-strong-pass-77!"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password("A-new-strong-pass-77!"))
        again = c.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "password": "Another-strong-pass-88!"}, format="json")
        self.assertEqual(again.status_code, 400, "a reset link must work only once")

    def test_unknown_email_gets_the_same_answer_and_no_email(self):
        r = APIClient().post("/api/auth/password-reset/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_the_web_page_from_the_email_works(self):
        APIClient().post("/api/auth/password-reset/", {"email": "reset@example.com"}, format="json")
        uid, token = self._parts()
        path = f"/reset-password/{uid}/{token}/"
        self.assertEqual(self.client.get(path).status_code, 200)
        mismatch = self.client.post(path, {"password": "A-new-strong-pass-77!", "confirm": "different"})
        self.assertContains(mismatch, "do not match")
        done = self.client.post(path, {"password": "A-new-strong-pass-77!", "confirm": "A-new-strong-pass-77!"})
        self.assertContains(done, "Your password was changed")
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password("A-new-strong-pass-77!"))
        self.assertEqual(self.client.get(path).status_code, 400)

    def test_a_tampered_link_is_refused(self):
        APIClient().post("/api/auth/password-reset/", {"email": "reset@example.com"}, format="json")
        uid, token = self._parts()
        self.assertEqual(self.client.get(f"/reset-password/{uid}/{token[:-2]}xx/").status_code, 400)


class ForgotPasswordPageTests(TestCase):
    def test_the_page_sends_the_link_and_gives_the_same_answer_for_unknown_emails(self):
        User.objects.create_user("known", "known@example.com", "Old-pass-12345!")
        mail.outbox.clear()
        self.assertEqual(self.client.get("/forgot-password/").status_code, 200)
        known = self.client.post("/forgot-password/", {"email": "known@example.com"})
        self.assertContains(known, "we just sent a link")
        self.assertEqual(len(mail.outbox), 1)
        unknown = self.client.post("/forgot-password/", {"email": "nobody@example.com"})
        self.assertContains(unknown, "we just sent a link")
        self.assertEqual(len(mail.outbox), 1)

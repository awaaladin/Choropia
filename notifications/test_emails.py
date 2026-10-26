"""Choropia's emails: rendering, safety, and that each trigger point sends the right one."""
import re
import smtplib
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts import otp
from accounts.models import EmailOTP, User
from notifications import emails
from orders.state_machine import OrderStatus
from payments import payouts
from payments.models import Payment, PayoutAccount
from payments.services import confirm_paystack_payment
from payments.tests.test_paystack import charge, make_order

SETTINGS = dict(
    DEFAULT_FROM_EMAIL="Choropia <no-reply@mail.choropia.test>",
    SUPPORT_EMAIL="support@mail.choropia.test",
    CHOROPIA_SITE_URL="https://choropia.test",
)


def html_of(message):
    return message.alternatives[0][0]


@override_settings(**SETTINGS)
class MailerTests(TestCase):
    def test_sends_html_and_a_plain_text_alternative_from_the_configured_address(self):
        self.assertTrue(emails.send_email("a@example.com", "Hi", "verify_code", {"name": "Ada", "code": "123456", "minutes": 10}))
        message = mail.outbox[0]
        self.assertEqual(message.from_email, "Choropia <no-reply@mail.choropia.test>")
        self.assertEqual(message.to, ["a@example.com"])
        self.assertIn("123456", message.body)  # the text version carries the code too
        self.assertNotIn("<", message.body)
        self.assertIn("text/html", message.alternatives[0][1])
        self.assertIn("https://choropia.test/logo.png", html_of(message))

    def test_a_delivery_failure_returns_false_and_never_raises(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=smtplib.SMTPAuthenticationError(535, b"bad")):
            self.assertFalse(emails.send_email("a@example.com", "Hi", "verify_code", {"name": "Ada", "code": "1", "minutes": 1}))

    def test_a_missing_template_returns_false_and_never_raises(self):
        self.assertFalse(emails.send_email("a@example.com", "Hi", "does_not_exist"))

    def test_no_recipient_sends_nothing(self):
        self.assertFalse(emails.send_email("", "Hi", "verify_code"))
        self.assertEqual(len(mail.outbox), 0)

    def test_user_text_is_escaped_in_the_html(self):
        emails.send_email("a@example.com", "Hi", "order_update", {
            "name": "<b>Ada</b>", "headline": "Delivered", "body": "ok", "order_id": 1,
            "listing_title": "<script>alert(1)</script>", "status": "delivered",
        })
        html = html_of(mail.outbox[0])
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<b>Ada</b>", html)

    def test_newlines_in_a_subject_cannot_inject_headers(self):
        emails.send_email("a@example.com", "Hello\nBcc: attacker@example.com", "verify_code", {"name": "A", "code": "1", "minutes": 1})
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].bcc, [])

    def test_amounts_are_formatted_in_naira(self):
        self.assertEqual(emails.naira(Decimal("200000")), "₦200,000.00")
        self.assertEqual(emails.naira("1234.5"), "₦1,234.50")


@override_settings(**SETTINGS, PASSWORD_RESET_URL_BASE="https://choropia.test/reset-password")
class AccountEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()

    def test_signup_sends_one_welcome_email_with_a_code_that_verifies(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/api/v1/auth/register/", {"email": "new@example.com", "password": "Str0ng-Passw0rd!", "first_name": "Ngozi"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["new@example.com"])
        self.assertIn("Welcome to Choropia", html_of(message))
        self.assertIn("Ngozi", html_of(message))
        code = re.search(r"\b(\d{6})\b", message.body).group(1)

        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.profile.email_verified)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post("/api/v1/auth/email-otp/confirm/", {"code": code}, format="json").status_code, 200)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.email_verified)

    def test_signup_still_works_when_email_is_down(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=smtplib.SMTPServerDisconnected("down")), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/api/v1/auth/register/", {"email": "new2@example.com", "password": "Str0ng-Passw0rd!"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email="new2@example.com").exists())

    def test_password_reset_email_is_branded_and_the_link_still_parses(self):
        User.objects.create_user("known@example.com", "OldPassw0rd!", first_name="Kemi")
        response = self.client.post("/api/v1/auth/password-reset/", {"email": "known@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        message = mail.outbox[0]
        self.assertIn("Reset your password", html_of(message))
        self.assertRegex(message.body, r"uid=([^&\s]+)&token=([^\s]+)")
        self.assertIn("https://choropia.test/reset-password?uid=", html_of(message))

    def test_a_reset_for_an_unknown_address_sends_nothing(self):
        self.client.post("/api/v1/auth/password-reset/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(len(mail.outbox), 0)


@override_settings(**SETTINGS, EMAIL_OTP_MINUTES=10, EMAIL_OTP_MAX_ATTEMPTS=3, EMAIL_OTP_RESEND_SECONDS=60)
class EmailOtpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("otp@example.com", "pw12345!", first_name="Ola")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def request_code(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/v1/auth/email-otp/request/")

    def confirm(self, code):
        return self.client.post("/api/v1/auth/email-otp/confirm/", {"code": code}, format="json")

    def test_request_emails_a_six_digit_code_and_stores_only_a_hash(self):
        self.assertEqual(self.request_code().status_code, 200)
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        stored = EmailOTP.objects.get()
        self.assertNotIn(code, stored.code_hash)
        self.assertEqual(len(stored.code_hash), 64)

    def test_the_right_code_verifies_once_only(self):
        self.request_code()
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.assertEqual(self.confirm(code).status_code, 200)
        self.assertEqual(self.confirm(code).status_code, 400)  # single use

    def test_a_wrong_code_is_rejected_and_the_good_one_dies_after_too_many_guesses(self):
        self.request_code()
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(3):
            self.assertEqual(self.confirm(wrong).status_code, 400)
        self.assertEqual(self.confirm(code).status_code, 400)  # locked out: must request a new code
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)

    def test_an_expired_code_is_rejected(self):
        self.request_code()
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        from datetime import timedelta

        from django.utils import timezone

        EmailOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.confirm(code).status_code, 400)

    def test_asking_again_too_soon_is_refused(self):
        self.request_code()
        again = self.request_code()
        self.assertEqual(again.status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_new_code_replaces_the_old_one(self):
        self.request_code()
        first = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        EmailOTP.objects.update(created_at=EmailOTP.objects.get().created_at.replace(year=2000))  # skip the cooldown
        self.request_code()
        second = re.search(r"\b(\d{6})\b", mail.outbox[1].body).group(1)
        if first != second:
            self.assertEqual(self.confirm(first).status_code, 400)
        self.assertEqual(self.confirm(second).status_code, 200)

    def test_codes_belong_to_one_user(self):
        self.request_code()
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        other = User.objects.create_user("other@example.com", "pw12345!")
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.post("/api/v1/auth/email-otp/confirm/", {"code": code}, format="json").status_code, 400)

    def test_malformed_codes_are_rejected_without_touching_the_attempt_counter(self):
        self.request_code()
        for bad in ("12345", "abcdef", "", "1234567"):
            self.assertEqual(self.confirm(bad).status_code, 400)
        self.assertEqual(EmailOTP.objects.get().attempts, 0)

    def test_everything_needs_login(self):
        anon = APIClient()
        self.assertEqual(anon.post("/api/v1/auth/email-otp/request/").status_code, 401)
        self.assertEqual(anon.post("/api/v1/auth/email-otp/confirm/", {"code": "123456"}, format="json").status_code, 401)

    def test_an_already_verified_user_gets_no_email(self):
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.assertEqual(self.request_code().status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_client_cannot_mark_itself_verified(self):
        response = self.client.patch("/api/v1/users/me/", {"profile": {"email_verified": True, "bio": "hi"}}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)
        self.assertEqual(self.user.profile.bio, "hi")

    def test_otp_module_matches_the_hash_it_stores(self):
        code = otp.issue_code(self.user)
        self.assertTrue(otp.check_code(self.user, code))

    @override_settings(REQUIRE_VERIFIED_EMAIL_FOR_PAYOUT=True)
    def test_payout_account_can_require_a_verified_email(self):
        response = self.client.put("/api/v1/payouts/account/", {"bank_code": "058", "account_number": "0123456789"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "email_not_verified")


@override_settings(**SETTINGS, PAYSTACK_SECRET_KEY="sk_test_unit", PAYOUT_MAX_NGN=Decimal("2000000"), PAYOUTS_ENABLED=True)
class OrderAndPaymentEmailTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.payment = Payment.objects.create(
            order=self.order, reference="CHOROPIA-ORDER-20261024-ABCDEF123456", amount=self.order.price,
            provider="paystack", authorization_url="https://checkout.paystack.com/x",
        )

    def pay(self):
        with self.captureOnCommitCallbacks(execute=True):
            confirm_paystack_payment(self.payment.reference, charge(self.payment.reference))

    def test_a_confirmed_payment_emails_a_receipt_to_the_buyer_and_a_dispatch_notice_to_the_seller(self):
        self.pay()
        by_recipient = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(by_recipient), {self.order.buyer.email, self.order.seller.email})
        buyer_mail, seller_mail = by_recipient[self.order.buyer.email], by_recipient[self.order.seller.email]
        self.assertIn("Payment received", html_of(buyer_mail))
        self.assertIn("₦200,000.00", html_of(buyer_mail))
        self.assertIn(self.payment.reference, html_of(buyer_mail))
        self.assertIn("You have a paid order", html_of(seller_mail))
        self.assertIn(f"https://choropia.test/orders/{self.order.id}", seller_mail.body)

    def test_a_duplicate_confirmation_sends_no_second_set_of_emails(self):
        self.pay()
        mail.outbox.clear()
        self.pay()
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_if_the_transaction_rolls_back(self):
        from django.db import transaction

        try:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with transaction.atomic():
                    confirm_paystack_payment(self.payment.reference, charge(self.payment.reference))
                    raise RuntimeError("rolled back")
        except RuntimeError:
            pass
        self.assertEqual(callbacks, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_delivery_emails_the_buyer_with_the_confirm_prompt(self):
        self.order.status = OrderStatus.IN_TRANSIT
        self.order.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.order.transition_to(OrderStatus.DELIVERED, actor=self.order.seller)
        self.assertEqual([m.to[0] for m in mail.outbox], [self.order.buyer.email])
        self.assertIn("confirm receipt", html_of(mail.outbox[0]))

    def test_a_dispute_emails_the_other_party_but_not_the_person_who_raised_it(self):
        self.order.status = OrderStatus.DELIVERED
        self.order.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.order.transition_to(OrderStatus.DISPUTED, actor=self.order.buyer)
        self.assertEqual([m.to[0] for m in mail.outbox], [self.order.seller.email])

    def test_internal_statuses_send_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.order.transition_to(OrderStatus.PAID_ESCROW, actor=None)
        self.assertEqual(len(mail.outbox), 0)  # the payment emails cover this step

    def test_an_email_failure_never_blocks_the_order_transition(self):
        self.order.status = OrderStatus.IN_TRANSIT
        self.order.save()
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=smtplib.SMTPException("down")), self.captureOnCommitCallbacks(execute=True):
            self.order.transition_to(OrderStatus.DELIVERED, actor=self.order.seller)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)


@override_settings(**SETTINGS, PAYSTACK_SECRET_KEY="sk_test_unit", PAYOUTS_ENABLED=True, COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"), PAYOUT_MAX_NGN=Decimal("2000000"))
class PayoutEmailTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.payment = Payment.objects.create(
            order=self.order, reference="CHOROPIA-ORDER-20261024-ABCDEF123456", amount=self.order.price,
            provider="paystack", status=Payment.Status.RELEASED,
        )

    def test_a_seller_without_a_bank_account_is_told_to_add_one(self):
        with self.captureOnCommitCallbacks(execute=True):
            payouts.create_payout(self.payment)
            payouts.create_payout(self.payment)  # idempotent: no second email
        self.assertEqual([m.to[0] for m in mail.outbox], [self.order.seller.email])
        self.assertIn("Add your bank account", html_of(mail.outbox[0]))
        self.assertIn("₦190,000.00", html_of(mail.outbox[0]))

    def test_a_paid_payout_emails_the_seller_the_breakdown_once(self):
        PayoutAccount.objects.create(
            user=self.order.seller, bank_code="058", bank_name="Guaranty Trust Bank", account_last4="1234",
            account_name="ADA OBI", recipient_code="RCP_abc",
        )
        ps = mock.Mock()
        ps.initiate_transfer.return_value = {"status": "success", "transfer_code": "TRF_1"}
        with mock.patch("payments.payouts._paystack", return_value=ps), self.captureOnCommitCallbacks(execute=True):
            payout = payouts.create_payout(self.payment)
            payouts.process_payout(payout.pk)
            payouts.process_payout(payout.pk)
        sent = [m for m in mail.outbox if "on its way" in m.subject]
        self.assertEqual(len(sent), 1)
        html = html_of(sent[0])
        for expected in ("₦200,000.00", "₦10,000.00", "₦190,000.00", "5%", "Guaranty Trust Bank", "1234"):
            self.assertIn(expected, html)


class EmailSettingsTests(TestCase):
    def test_ssl_wins_over_a_stale_tls_flag(self):
        import importlib
        import os

        from config.settings import base

        keep = {k: os.environ.get(k) for k in ("EMAIL_USE_SSL", "EMAIL_USE_TLS")}
        try:
            os.environ["EMAIL_USE_SSL"], os.environ["EMAIL_USE_TLS"] = "true", "true"
            reloaded = importlib.reload(base)
            self.assertTrue(reloaded.EMAIL_USE_SSL)
            self.assertFalse(reloaded.EMAIL_USE_TLS)  # both true would make Django raise on every send
        finally:
            for k, v in keep.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            importlib.reload(base)

"""Seller payouts and Choropia's 5% commission. Paystack is always mocked: no test moves money."""
import json
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from payments import payouts
from payments.models import Payment, Payout, PayoutAccount
from payments.paystack import PaystackError
from payments.services import refund_escrow, release_escrow
from payments.tests.test_paystack import SECRET, make_order
from payments.tests.test_webhook_router import sign

PS = "payments.payouts._paystack"


class _NoRealPaystack:
    """Fails loudly if a test ever lets a request reach the real Paystack API."""

    def __getattr__(self, name):
        raise AssertionError(f"A test tried to call the real Paystack ({name}); mock payments.payouts._paystack")


def held_payment(price="200000.00"):
    order = make_order()
    order.price = Decimal(price)
    order.save()
    return Payment.objects.create(
        order=order, reference=f"CHOROPIA-ORDER-20261024-{order.id:012X}", amount=order.price,
        provider="paystack", status=Payment.Status.PAID_HELD, authorization_url="https://checkout.paystack.com/x",
    )


def add_account(user, code="RCP_abc"):
    return PayoutAccount.objects.create(
        user=user, bank_code="058", bank_name="Guaranty Trust Bank", account_last4="1234",
        account_name="ADA OBI", recipient_code=code,
    )


def transfer_ok(status="pending", code="TRF_123"):
    ps = mock.Mock()
    ps.initiate_transfer.return_value = {"status": status, "transfer_code": code}
    return ps


class TieredCommissionTests(SimpleTestCase):
    """The launch rates: 6% under 10,000; 5% up to and including 100,000; 4% above."""

    def rate(self, price):
        return payouts.commission_percent_for(price)

    def test_the_rate_steps_down_with_the_price(self):
        self.assertEqual(self.rate("1000"), Decimal("6"))
        self.assertEqual(self.rate("9999.99"), Decimal("6"))
        self.assertEqual(self.rate("10000"), Decimal("5"))
        self.assertEqual(self.rate("100000"), Decimal("5"))
        self.assertEqual(self.rate("100000.01"), Decimal("4"))
        self.assertEqual(self.rate("310000"), Decimal("4"))

    def test_the_numbers_quoted_to_the_owner(self):
        for price, commission in (("1000", "60.00"), ("5000", "300.00"), ("20000", "1000.00"), ("100000", "5000.00"), ("150000", "6000.00"), ("310000", "12400.00")):
            got, net = payouts.commission_split(price)
            self.assertEqual(got, Decimal(commission), price)
            self.assertEqual(got + net, Decimal(price))

    def test_the_preview_matches_what_a_payout_will_use(self):
        preview = payouts.commission_preview("15000")
        self.assertEqual((preview["commission_percent"], preview["commission_amount"], preview["you_receive"]),
                         (Decimal("5"), Decimal("750.00"), Decimal("14250.00")))

    @override_settings(COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"))
    def test_flat_rate_is_one_setting_away(self):
        self.assertEqual({self.rate(p) for p in ("500", "50000", "900000")}, {Decimal("5")})

    @override_settings(COMMISSION_TIERS=[(Decimal("10000"), Decimal("8"))], PLATFORM_COMMISSION_PERCENT=Decimal("3"))
    def test_tiers_are_configurable(self):
        self.assertEqual((self.rate("9999"), self.rate("10000")), (Decimal("8"), Decimal("3")))


class TieredPayoutTests(TestCase):
    @override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYOUTS_ENABLED=True)
    def test_a_payout_records_the_rate_that_applied(self):
        for price, rate, commission in (("5000.00", "6.00", "300.00"), ("200000.00", "4.00", "8000.00")):
            payment = held_payment(price)
            payment.status = Payment.Status.RELEASED
            payment.save()
            payout = payouts.create_payout(payment)
            self.assertEqual((payout.commission_rate, payout.commission_amount), (Decimal(rate), Decimal(commission)), price)
            self.assertEqual(payout.commission_amount + payout.net_amount, payout.gross_amount)

    def test_the_preview_endpoint_is_public_and_validates(self):
        client = APIClient()
        body = client.get("/api/v1/payouts/preview/?price=15000").json()
        self.assertEqual(body, {"price": "15000.00", "commission_percent": "5", "commission_amount": "750.00", "you_receive": "14250.00"})
        self.assertEqual(client.get("/api/v1/payouts/preview/?price=1,500").json()["commission_amount"], "90.00")  # commas are fine
        for bad in ("", "abc", "0", "-5", "99999999999"):
            self.assertEqual(client.get(f"/api/v1/payouts/preview/?price={bad}").status_code, 400, bad)

    def test_the_wallet_summary_lists_the_tiers(self):
        user = held_payment().order.seller
        client = APIClient()
        client.force_authenticate(user)
        tiers = client.get("/api/v1/wallet/summary/").json()["commission_tiers"]
        self.assertEqual(tiers, [{"below": "10000", "percent": "6"}, {"below": "100000.01", "percent": "5"}, {"below": None, "percent": "4"}])


class CommissionTests(SimpleTestCase):
    def test_five_percent_of_a_round_amount(self):
        self.assertEqual(payouts.commission_split("200000.00", 5), (Decimal("10000.00"), Decimal("190000.00")))

    def test_rounds_to_the_kobo_and_always_adds_back_to_gross(self):
        commission, net = payouts.commission_split("1234.57", 5)  # 5% = 61.7285
        self.assertEqual(commission, Decimal("61.73"))
        self.assertEqual(net, Decimal("1172.84"))
        for gross in ("0.01", "99.99", "15000.00", "310000.50", "7.35"):
            c, n = payouts.commission_split(gross, 5)
            self.assertEqual(c + n, Decimal(gross))

    def test_other_percentages(self):
        self.assertEqual(payouts.commission_split("1000", "7.5"), (Decimal("75.00"), Decimal("925.00")))

    @override_settings(COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"))
    def test_default_comes_from_settings(self):
        self.assertEqual(payouts.commission_split("100")[0], Decimal("5.00"))


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYOUTS_ENABLED=True, COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"),
                   PAYOUT_MAX_NGN=Decimal("2000000"), PAYOUT_MAX_ATTEMPTS=3)
class ReleaseCreatesPayoutTests(TestCase):
    def release(self, payment, ps=None):
        with mock.patch(PS, return_value=ps or transfer_ok()), self.captureOnCommitCallbacks(execute=True):
            release_escrow(payment.order)
        return Payout.objects.filter(payment=payment).first()

    def test_seller_without_a_bank_account_waits_and_nothing_is_sent(self):
        payment = held_payment()
        ps = transfer_ok()
        payout = self.release(payment, ps)
        self.assertEqual(payout.status, Payout.Status.AWAITING_ACCOUNT)
        self.assertEqual((payout.gross_amount, payout.commission_amount, payout.net_amount),
                         (Decimal("200000.00"), Decimal("10000.00"), Decimal("190000.00")))
        ps.initiate_transfer.assert_not_called()

    def test_with_an_account_the_seller_gets_95_percent_and_choropia_keeps_5(self):
        payment = held_payment()
        add_account(payment.order.seller)
        ps = transfer_ok("pending")
        payout = self.release(payment, ps)

        ps.initiate_transfer.assert_called_once()
        kwargs = ps.initiate_transfer.call_args.kwargs
        self.assertEqual(kwargs["amount"], Decimal("190000.00"))
        self.assertEqual(kwargs["recipient_code"], "RCP_abc")
        self.assertRegex(kwargs["reference"], r"^choropia-payout-\d{8}-[0-9a-f]{12}$")
        self.assertEqual(kwargs["reference"], kwargs["reference"].lower())  # Paystack: transfer refs are lowercase
        self.assertIn(f"#{payment.order_id}", kwargs["reason"])
        self.assertEqual(payout.status, Payout.Status.PROCESSING)
        self.assertEqual(payout.transfer_reference, kwargs["reference"])
        self.assertEqual(payout.attempts, 1)
        self.assertEqual((payout.bank_name, payout.account_last4, payout.account_name), ("Guaranty Trust Bank", "1234", "ADA OBI"))

    def test_an_instantly_successful_transfer_is_marked_paid(self):
        payment = held_payment()
        add_account(payment.order.seller)
        payout = self.release(payment, transfer_ok("success", "TRF_9"))
        self.assertEqual(payout.status, Payout.Status.SUCCESS)
        self.assertIsNotNone(payout.completed_at)
        payment.refresh_from_db()
        self.assertEqual(payment.transfer_reference, payout.transfer_reference)

    def test_releasing_twice_pays_once(self):
        payment = held_payment()
        add_account(payment.order.seller)
        ps = transfer_ok()
        self.release(payment, ps)
        self.release(payment, ps)  # release_escrow is idempotent
        self.assertEqual(Payout.objects.filter(payment=payment).count(), 1)
        ps.initiate_transfer.assert_called_once()

    def test_processing_a_payout_twice_never_sends_twice(self):
        payment = held_payment()
        add_account(payment.order.seller)
        ps = transfer_ok()
        payout = self.release(payment, ps)
        with mock.patch(PS, return_value=ps):
            payouts.process_payout(payout.pk)
            payouts.process_payout(payout.pk)
        ps.initiate_transfer.assert_called_once()

    def test_a_refund_creates_no_payout(self):
        payment = held_payment()
        add_account(payment.order.seller)
        with mock.patch("payments.services._paystack"):
            refund_escrow(payment.order)
        self.assertFalse(Payout.objects.exists())

    @override_settings(PAYOUTS_ENABLED=False)
    def test_kill_switch_records_but_sends_nothing(self):
        payment = held_payment()
        add_account(payment.order.seller)
        ps = transfer_ok()
        payout = self.release(payment, ps)
        self.assertEqual(payout.status, Payout.Status.PENDING)
        ps.initiate_transfer.assert_not_called()

    @override_settings(PAYOUT_MAX_NGN=Decimal("100000"))
    def test_a_payout_above_the_limit_is_held_for_a_person(self):
        payment = held_payment()
        add_account(payment.order.seller)
        ps = transfer_ok()
        payout = self.release(payment, ps)
        self.assertEqual(payout.status, Payout.Status.NEEDS_ATTENTION)
        self.assertIn("limit", payout.failure_reason)
        ps.initiate_transfer.assert_not_called()

    def test_only_released_payments_are_ever_paid_out(self):
        payment = held_payment()
        add_account(payment.order.seller)
        payout = payouts.create_payout(payment)  # payment is still PAID_HELD, not RELEASED
        ps = transfer_ok()
        with mock.patch(PS, return_value=ps):
            payouts.process_payout(payout.pk)
        ps.initiate_transfer.assert_not_called()


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYOUTS_ENABLED=True, COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"), PAYOUT_MAX_NGN=Decimal("2000000"), PAYOUT_MAX_ATTEMPTS=3)
class FailureHandlingTests(TestCase):
    def setUp(self):
        self.payment = held_payment()
        add_account(self.payment.order.seller)
        self.payment.status = Payment.Status.RELEASED
        self.payment.save()
        self.payout = payouts.create_payout(self.payment)

    def run_payout(self, ps):
        with mock.patch(PS, return_value=ps):
            payouts.process_payout(self.payout.pk)
        self.payout.refresh_from_db()
        return self.payout

    def test_insufficient_balance_is_retried_with_a_new_reference_then_given_to_a_person(self):
        ps = mock.Mock()
        ps.initiate_transfer.side_effect = PaystackError("Your balance is not enough to fulfil this request", http_status=400)
        first = self.run_payout(ps).transfer_reference
        self.assertEqual(self.payout.status, Payout.Status.PENDING)
        self.assertIn("balance", self.payout.failure_reason)
        second = self.run_payout(ps).transfer_reference
        self.assertNotEqual(first, second)  # a reference is never reused
        self.run_payout(ps)
        self.assertEqual(self.payout.status, Payout.Status.NEEDS_ATTENTION)  # 3 attempts
        self.assertEqual(len(self.payout.transfer_references), 3)

    def test_permission_errors_go_straight_to_a_person(self):
        ps = mock.Mock()
        ps.initiate_transfer.side_effect = PaystackError("IP not whitelisted", http_status=403)
        self.assertEqual(self.run_payout(ps).status, Payout.Status.NEEDS_ATTENTION)

    def test_a_timeout_is_never_retried_blindly(self):
        ps = mock.Mock()
        ps.initiate_transfer.side_effect = PaystackError("Paystack unreachable: timed out")  # outcome unknown
        self.assertEqual(self.run_payout(ps).status, Payout.Status.PROCESSING)
        self.run_payout(ps)  # a second run must not send again
        ps.initiate_transfer.assert_called_once()

    def test_reconcile_adopts_a_transfer_that_actually_went_through(self):
        ps = mock.Mock()
        ps.initiate_transfer.side_effect = PaystackError("Paystack unreachable: timed out")
        self.run_payout(ps)
        ps.verify_transfer.return_value = {"status": "success", "transfer_code": "TRF_77"}
        with mock.patch(PS, return_value=ps):
            payouts.reconcile_payout(self.payout.pk)
        self.payout.refresh_from_db()
        self.assertEqual((self.payout.status, self.payout.paystack_transfer_code), (Payout.Status.SUCCESS, "TRF_77"))

    def test_reconcile_requeues_when_paystack_never_heard_of_it(self):
        ps = mock.Mock()
        ps.initiate_transfer.side_effect = PaystackError("Paystack unreachable: timed out")
        self.run_payout(ps)
        ps.verify_transfer.side_effect = PaystackError("Transfer not found", http_status=404)
        with mock.patch(PS, return_value=ps):
            payouts.reconcile_payout(self.payout.pk)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.PENDING)

    def test_reconcile_leaves_a_genuinely_in_progress_transfer_alone(self):
        self.run_payout(transfer_ok("pending"))
        ps = mock.Mock()
        ps.verify_transfer.return_value = {"status": "pending"}
        with mock.patch(PS, return_value=ps):
            payouts.reconcile_payout(self.payout.pk)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.PROCESSING)

    def test_otp_required_goes_to_a_person_with_instructions(self):
        self.assertEqual(self.run_payout(transfer_ok("otp")).status, Payout.Status.NEEDS_ATTENTION)
        self.assertIn("Confirm transfers before sending", self.payout.failure_reason)

    def test_a_failed_transfer_status_is_requeued(self):
        self.assertEqual(self.run_payout(transfer_ok("failed")).status, Payout.Status.PENDING)

    def test_scheduler_sends_queued_payouts_and_reconciles_stale_ones(self):
        ps = transfer_ok("success")
        with mock.patch(PS, return_value=ps):
            result = payouts.process_pending_payouts()
        self.assertEqual(result["sent"], [self.payout.pk])
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.SUCCESS)

    @override_settings(PAYOUTS_ENABLED=False)
    def test_scheduler_does_nothing_when_disabled(self):
        ps = transfer_ok()
        with mock.patch(PS, return_value=ps):
            self.assertEqual(payouts.process_pending_payouts(), {"enabled": False})
        ps.initiate_transfer.assert_not_called()


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYOUTS_ENABLED=True, COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"), PAYOUT_MAX_NGN=Decimal("2000000"), PAYOUT_MAX_ATTEMPTS=3)
class TransferWebhookTests(TestCase):
    def setUp(self):
        payment = held_payment()
        add_account(payment.order.seller)
        payment.status = Payment.Status.RELEASED
        payment.save()
        self.payout = payouts.create_payout(payment)
        with mock.patch(PS, return_value=transfer_ok("pending")):
            payouts.process_payout(self.payout.pk)
        self.payout.refresh_from_db()
        self.reference = self.payout.transfer_reference

    def send(self, event, reference=None, url="/api/paystack-webhook"):
        raw = json.dumps({"event": event, "data": {"reference": reference or self.reference, "transfer_code": "TRF_1", "reason": "Account closed"}}).encode()
        return self.client.post(url, data=raw, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sign(raw))

    def test_success_event_marks_paid_and_is_idempotent(self):
        self.assertEqual(self.send("transfer.success").status_code, 200)
        self.assertEqual(self.send("transfer.success").status_code, 200)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.SUCCESS)

    def test_failed_event_requeues(self):
        self.send("transfer.failed")
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.PENDING)
        self.assertIn("Account closed", self.payout.failure_reason)

    def test_reversed_event_goes_to_a_person(self):
        self.send("transfer.reversed")
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.NEEDS_ATTENTION)

    def test_late_failure_after_success_does_not_undo_it(self):
        self.send("transfer.success")
        self.send("transfer.failed")
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.SUCCESS)

    def test_unknown_reference_is_acknowledged_and_changes_nothing(self):
        self.assertEqual(self.send("transfer.success", "choropia-payout-20200101-000000000000").status_code, 200)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.PROCESSING)

    def test_choropia_s_own_direct_endpoint_handles_it_too(self):
        self.send("transfer.success", url="/api/v1/payments/webhook/paystack/")
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.SUCCESS)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYOUTS_ENABLED=True, COMMISSION_TIERS=[], PLATFORM_COMMISSION_PERCENT=Decimal("5"), PAYOUT_MAX_NGN=Decimal("2000000"), PAYOUT_MAX_ATTEMPTS=3)
class PayoutAccountApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.payment = held_payment()
        self.seller = self.payment.order.seller
        self.client = APIClient()
        self.client.force_authenticate(self.seller)
        self.ps = mock.Mock()
        self.ps.list_banks.return_value = [
            {"code": "058", "name": "Guaranty Trust Bank", "active": True},
            {"code": "044", "name": "Access Bank", "active": True},
        ]
        self.ps.resolve_account.return_value = {"account_name": "ADA OBI", "account_number": "0123456789"}
        self.ps.create_recipient.return_value = {"recipient_code": "RCP_new"}

    def put(self, **body):
        payload = {"bank_code": "058", "account_number": "0123456789", **body}
        with mock.patch(PS, return_value=self.ps):
            return self.client.put("/api/v1/payouts/account/", payload, format="json")

    def test_everything_needs_login(self):
        anon = APIClient()
        for method, url in (("get", "/api/v1/payouts/banks/"), ("get", "/api/v1/payouts/account/"), ("put", "/api/v1/payouts/account/"), ("get", "/api/v1/payouts/")):
            self.assertEqual(getattr(anon, method)(url).status_code, 401, url)

    def test_banks_are_listed_alphabetically(self):
        with mock.patch(PS, return_value=self.ps):
            response = self.client.get("/api/v1/payouts/banks/")
        self.assertEqual([b["name"] for b in response.json()], ["Access Bank", "Guaranty Trust Bank"])

    def test_not_configured_by_default(self):
        self.assertEqual(self.client.get("/api/v1/payouts/account/").json(), {"configured": False})

    def test_saving_verifies_with_the_bank_and_never_echoes_the_full_number(self):
        response = self.put()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body, {"configured": True, "bank_code": "058", "bank_name": "Guaranty Trust Bank", "account_last4": "6789", "account_name": "ADA OBI"})
        self.assertNotIn("0123456789", json.dumps(body))
        self.assertNotIn("RCP_new", json.dumps(body))
        account = PayoutAccount.objects.get(user=self.seller)
        self.assertEqual((account.account_last4, account.recipient_code), ("6789", "RCP_new"))
        self.assertNotIn("0123456789", json.dumps(list(PayoutAccount.objects.values()), default=str))  # the full number is not stored

    def test_the_account_name_used_is_the_banks_not_the_users(self):
        self.put()
        self.ps.create_recipient.assert_called_once_with("ADA OBI", "0123456789", "058")

    def test_bad_input_is_rejected_before_paystack_is_called(self):
        self.assertEqual(self.put(account_number="12345").status_code, 400)
        self.assertEqual(self.put(account_number="01234567ab").status_code, 400)
        self.ps.resolve_account.assert_not_called()

    def test_unknown_bank_is_rejected(self):
        self.assertEqual(self.put(bank_code="999").status_code, 400)
        self.ps.resolve_account.assert_not_called()

    def test_an_account_the_bank_cannot_resolve_gives_a_friendly_error(self):
        self.ps.resolve_account.side_effect = PaystackError("Could not resolve account name", http_status=422)
        response = self.put()
        self.assertEqual(response.status_code, 400)
        self.assertIn("couldn't verify", response.json()["detail"])
        self.assertFalse(PayoutAccount.objects.exists())

    def test_adding_an_account_pays_out_what_was_waiting(self):
        self.payment.status = Payment.Status.RELEASED
        self.payment.save()
        payout = payouts.create_payout(self.payment)
        self.assertEqual(payout.status, Payout.Status.AWAITING_ACCOUNT)
        self.ps.initiate_transfer.return_value = {"status": "pending", "transfer_code": "TRF_5"}
        # The mock must still be active when the after-commit callbacks run.
        with mock.patch(PS, return_value=self.ps), self.captureOnCommitCallbacks(execute=True):
            response = self.client.put("/api/v1/payouts/account/", {"bank_code": "058", "account_number": "0123456789"}, format="json")
        self.assertEqual(response.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, Payout.Status.PROCESSING)
        self.assertEqual(self.ps.initiate_transfer.call_args.kwargs["amount"], Decimal("190000.00"))

    def test_delete_removes_the_account(self):
        self.put()
        self.assertEqual(self.client.delete("/api/v1/payouts/account/").status_code, 204)
        self.assertFalse(PayoutAccount.objects.exists())

    def test_sellers_see_only_their_own_payouts(self):
        self.payment.status = Payment.Status.RELEASED
        self.payment.save()
        payouts.create_payout(self.payment)
        mine = self.client.get("/api/v1/payouts/").json()["results"]
        self.assertEqual(len(mine), 1)
        self.assertEqual((mine[0]["commission_amount"], mine[0]["net_amount"]), ("10000.00", "190000.00"))
        other = APIClient()
        other.force_authenticate(self.payment.order.buyer)
        self.assertEqual(other.get("/api/v1/payouts/").json()["results"], [])

    def test_only_the_seller_sees_the_payout_on_the_order(self):
        self.payment.status = Payment.Status.RELEASED
        self.payment.save()
        payouts.create_payout(self.payment)
        url = f"/api/v1/orders/{self.payment.order_id}/"
        seller_view = self.client.get(url).json()["payout"]
        self.assertEqual(seller_view["net_amount"], "190000.00")
        buyer = APIClient()
        buyer.force_authenticate(self.payment.order.buyer)
        self.assertIsNone(buyer.get(url).json()["payout"])

    def test_wallet_summary_states_the_commission(self):
        self.assertEqual(self.client.get("/api/v1/wallet/summary/").json()["commission_percent"], "5")


class ScheduledJobsEndpointTests(TestCase):
    URL = "/api/v1/internal/jobs/run/"

    @override_settings(CRON_SECRET="")
    def test_disabled_until_a_secret_is_configured(self):
        self.assertEqual(self.client.post(self.URL).status_code, 503)

    @override_settings(CRON_SECRET="s3cret")
    def test_rejects_missing_and_wrong_tokens(self):
        self.assertEqual(self.client.post(self.URL).status_code, 401)
        self.assertEqual(self.client.post(self.URL, HTTP_AUTHORIZATION="Bearer nope").status_code, 401)

    @override_settings(CRON_SECRET="s3cret")
    def test_runs_every_job_for_post_and_for_vercel_crons_get(self):
        with mock.patch("payments.tasks.poll_paystack_payments_task", return_value={"confirmed": []}), mock.patch(
            "payments.tasks.auto_release_escrow_task", return_value={"released": []}
        ), mock.patch("payments.payouts.process_pending_payouts", return_value={"sent": []}):
            for method in (self.client.post, self.client.get):
                response = method(self.URL, HTTP_AUTHORIZATION="Bearer s3cret")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json()), {"paystack_payments", "auto_release", "auto_refund_undispatched", "pending_refunds", "payouts", "dispatch_nudges"})

    @override_settings(CRON_SECRET="s3cret")
    def test_one_failing_job_does_not_stop_the_others(self):
        with mock.patch("payments.tasks.poll_paystack_payments_task", side_effect=RuntimeError("boom")), mock.patch(
            "payments.tasks.auto_release_escrow_task", return_value={"released": []}
        ), mock.patch("payments.payouts.process_pending_payouts", return_value={"sent": []}):
            body = self.client.post(self.URL, HTTP_AUTHORIZATION="Bearer s3cret").json()
        self.assertEqual(body["paystack_payments"], "failed")
        self.assertEqual(body["payouts"], {"sent": []})


def setUpModule():
    global _real_patch
    _real_patch = mock.patch(PS, return_value=_NoRealPaystack())
    _real_patch.start()


def tearDownModule():
    _real_patch.stop()

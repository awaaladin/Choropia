"""The money gaps closed after Copilot's checkout: verified webhooks with exact amounts, refunds instead of lost money,
checkouts that can't lock an offer forever, and the handover code for orders without a rider."""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from offers import settlement
from offers.models import HandoverCode, Offer
from orders.models import Order
from payments import ledger
from payments.models import LedgerEntry, Payment, Payout

from .test_offers_api import OfferFixture

SECRET = "sk_test_settlement"
AMOUNT = 18_500_000  # the offer: ₦185,000


def success(amount=AMOUNT, currency="NGN", status="success", reference="CHOROPIA-OFFER-T1"):
    return {"status": status, "amount": amount, "currency": currency, "reference": reference, "id": 99}


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYMENT_PROVIDER="paystack")
class SettlementFixture(OfferFixture):
    def setUp(self):
        super().setUp()
        self.offer_id = self.make().json()["id"]
        with mock.patch("payments.services.initialize_payment") as init:
            init.return_value.authorization_url = "https://checkout.example/pay"
            r = self.client_for(self.buyer).post(f"/api/v1/offers/{self.offer_id}/checkout/", {"delivery_method": "meetup"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.order = Order.objects.get(pk=r.json()["order_id"])
        self.payment = Payment.objects.create(
            order=self.order, reference="CHOROPIA-OFFER-T1", amount=self.order.price, provider="paystack",
            authorization_url="https://checkout.example/pay",
        )

    def offer(self):
        return Offer.objects.get(pk=self.offer_id)

    def webhook(self, verify_data, body=None, signature=None):
        body = json.dumps(body or {"event": "charge.success", "data": success()}).encode()
        sig = signature or hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
        ps = mock.Mock()
        ps.verify_transaction.return_value = verify_data
        with mock.patch("payments.payouts._paystack", return_value=ps):
            r = self.client.post("/api/v1/payments/webhook/paystack/", body, content_type="application/json",
                                 HTTP_X_PAYSTACK_SIGNATURE=sig)
        return r, ps


class WebhookVerifiesWithPaystackTests(SettlementFixture):
    def test_exact_amount_goes_into_escrow_and_marks_the_offer_paid(self):
        r, ps = self.webhook(success())
        self.assertEqual(r.status_code, 200, r.content)
        ps.verify_transaction.assert_called_once_with("CHOROPIA-OFFER-T1")
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual((self.payment.status, self.order.status, self.offer().status), ("paid_held", "paid_escrow", "paid"))
        self.assertTrue(HandoverCode.objects.filter(order=self.order).exists())
        self.assertEqual(ledger.balance_kobo(self.payment), AMOUNT)

    def test_the_webhook_body_is_not_trusted_paystack_verify_is(self):
        # The signed body says success, but Paystack's verify says the charge failed: nothing is held.
        r, _ = self.webhook(success(status="failed"))
        self.assertEqual(r.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.offer().status), ("initialized", "payment_processing"))

    def test_a_tampered_amount_is_refunded_not_held(self):
        for amount in (AMOUNT - 100, AMOUNT + 100):
            Payment.objects.filter(pk=self.payment.pk).update(status="initialized")
            Order.objects.filter(pk=self.order.pk).update(status="pending_payment")
            self.webhook(success(amount=amount))
            self.payment.refresh_from_db()
            self.assertEqual(self.payment.status, "refund_pending", amount)
        self.assertNotEqual(self.offer().status, "paid")
        self.assertTrue(LedgerEntry.objects.filter(payment=self.payment, kind="received_for_refund").exists())

    def test_wrong_currency_is_refunded(self):
        self.webhook(success(currency="USD"))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "refund_pending")

    def test_a_duplicate_webhook_never_creates_two_orders_or_two_holds(self):
        for _ in range(3):
            self.webhook(success())
        self.assertEqual(Order.objects.filter(listing=self.listing).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(payment=self.payment, kind="held").count(), 1)
        self.assertEqual(HandoverCode.objects.filter(order=self.order).count(), 1)

    def test_an_invalid_signature_changes_nothing(self):
        r, ps = self.webhook(success(), signature="0" * 128)
        self.assertEqual(r.status_code, 400)
        ps.verify_transaction.assert_not_called()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "initialized")

    def test_paystack_unreachable_makes_paystack_retry(self):
        from payments.paystack import PaystackError

        ps = mock.Mock()
        ps.verify_transaction.side_effect = PaystackError("down")
        body = json.dumps({"event": "charge.success", "data": success()}).encode()
        sig = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
        self.client.raise_request_exception = False
        with mock.patch("payments.payouts._paystack", return_value=ps):
            r = self.client.post("/api/v1/payments/webhook/paystack/", body, content_type="application/json",
                                 HTTP_X_PAYSTACK_SIGNATURE=sig)
        self.assertGreaterEqual(r.status_code, 500)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "initialized")


class UnfinishedCheckoutTests(SettlementFixture):
    def age(self, minutes=31):
        Offer.objects.filter(pk=self.offer_id).update(updated_at=timezone.now() - timedelta(minutes=minutes))

    def run_job(self, paystack_status):
        with mock.patch("offers.settlement._paystack_status", return_value=success(status=paystack_status)):
            from offers.services import expire_due_offers

            return expire_due_offers()

    def test_an_abandoned_checkout_frees_the_offer_after_the_timeout(self):
        self.age(10)
        self.run_job("abandoned")
        self.assertEqual(self.offer().status, "payment_processing")  # not yet
        self.age(31)
        result = self.run_job("abandoned")
        self.assertEqual(result["released_checkouts"], [self.offer_id])
        offer = self.offer()
        self.order.refresh_from_db()
        self.assertEqual((offer.status, offer.order_id, self.order.status), ("pending", None, "cancelled"))
        # The seller can now cancel or make a new offer again.
        self.assertEqual(self.client_for(self.seller).post(f"/api/v1/offers/{self.offer_id}/cancel/").status_code, 200)

    def test_a_checkout_that_was_actually_paid_is_applied_not_released(self):
        self.age()
        self.run_job("success")
        self.assertEqual(self.offer().status, "paid")

    def test_paying_the_old_link_after_release_is_refunded_automatically(self):
        self.age()
        self.run_job("abandoned")
        self.webhook(success())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "refund_pending")
        self.assertEqual(self.offer().status, "pending")  # untouched; the buyer can still pay it properly

    def test_payment_after_the_offer_expired_is_refunded(self):
        Offer.objects.filter(pk=self.offer_id).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.age()
        self.run_job("abandoned")
        self.assertEqual(self.offer().status, "expired")
        self.webhook(success())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "refund_pending")

    def test_a_failed_payment_reopens_the_offer_and_says_so(self):
        with mock.patch("offers.settlement._paystack_status", return_value=success(status="failed")):
            r = self.client_for(self.buyer).post(f"/api/v1/offers/{self.offer_id}/verify-payment/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["status"], r.json()["last_payment_failed"]), ("pending", True))

    def test_verify_payment_success_puts_it_in_escrow_at_once(self):
        with mock.patch("offers.settlement._paystack_status", return_value=success()):
            r = self.client_for(self.buyer).post(f"/api/v1/offers/{self.offer_id}/verify-payment/")
        self.assertEqual((r.json()["status"], r.json()["order_stage"]), ("paid", "escrow_held"))

    def test_only_the_buyer_can_verify(self):
        self.assertEqual(self.client_for(self.seller).post(f"/api/v1/offers/{self.offer_id}/verify-payment/").status_code, 403)
        self.assertEqual(self.client_for(self.outsider).post(f"/api/v1/offers/{self.offer_id}/verify-payment/").status_code, 404)


class HandoverCodeTests(SettlementFixture):
    def setUp(self):
        super().setUp()
        self.webhook(success())
        self.url = f"/api/v1/orders/{self.order.pk}/"

    def code(self):
        return self.client_for(self.buyer).get(self.url + "handover-code/")

    def enter(self, code, user=None):
        return self.client_for(user or self.seller).post(self.url + "confirm-handover/", {"code": code}, format="json")

    def test_only_the_buyer_sees_the_code_and_it_is_hashed_at_rest(self):
        r = self.code()
        self.assertEqual(r.status_code, 200, r.content)
        code = r.json()["code"]
        self.assertRegex(code, r"^\d{6}$")
        row = HandoverCode.objects.get(order=self.order)
        self.assertNotIn(code, row.code_hash)
        self.assertNotIn(code.encode(), bytes(row.code_encrypted))
        self.assertEqual(self.client_for(self.seller).get(self.url + "handover-code/").status_code, 404)
        self.assertEqual(self.client_for(self.outsider).get(self.url + "handover-code/").status_code, 404)

    def test_right_code_releases_escrow_and_queues_the_seller_payout(self):
        code = self.code().json()["code"]
        r = self.enter(code)
        self.assertEqual(r.status_code, 200, r.content)
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual((self.order.status, self.payment.status), ("completed", "released"))
        payout = Payout.objects.get(payment=self.payment, kind="seller")
        offer = self.offer()
        self.assertEqual(int(payout.commission_amount * 100), offer.fee_kobo)  # the fee locked on the offer
        self.assertEqual(payout.status, Payout.Status.AWAITING_ACCOUNT)  # manual queue; no transfer sent
        self.assertEqual(ledger.balance_kobo(self.payment), 0)
        self.assertEqual(self.enter(code).status_code, 409)  # only once
        self.assertTrue(self.code().json()["used"])

    def test_wrong_codes_are_limited_and_counted(self):
        for i in range(5):
            r = self.enter("000000" if self.code().json()["code"] != "000000" else "111111")
            self.assertEqual(r.json()["code"], "wrong_code")
            self.assertEqual(r.json()["attempts_left"], 4 - i)
        r = self.enter(self.code().json()["code"])
        self.assertEqual((r.status_code, r.json()["code"]), (423, "code_locked"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid_escrow")

    def test_the_buyer_cannot_enter_the_code(self):
        r = self.enter(self.code().json()["code"], user=self.buyer)
        self.assertEqual(r.status_code, 403)


class LedgerTests(SettlementFixture):
    def test_entries_are_append_only(self):
        self.webhook(success())
        entry = LedgerEntry.objects.get(payment=self.payment, kind="held")
        with self.assertRaises(ValueError):
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()

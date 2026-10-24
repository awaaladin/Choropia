import hashlib
import hmac
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from listings.models import Category, Listing
from orders.models import Order
from orders.state_machine import OrderStatus
from payments.models import Payment
from payments.services import initialize_payment, refund_escrow

User = get_user_model()
SECRET = "sk_test_unit"
WEBHOOK_URL = "/api/v1/payments/webhook/paystack/"


def make_order(status=OrderStatus.PENDING_PAYMENT):
    n = User.objects.count()
    buyer = User.objects.create_user(email=f"buyer{n}@example.com", password="pw12345!")
    seller = User.objects.create_user(email=f"seller{n}@example.com", password="pw12345!")
    category = Category.objects.get_or_create(name="Electronics")[0]
    listing = Listing.objects.create(owner=seller, category=category, title="Laptop", price="200000.00")
    return Order.objects.create(listing=listing, buyer=buyer, seller=seller, price=listing.price, status=status)


def paystack_mock():
    client = mock.Mock()
    client.initialize_transaction.return_value = {"authorization_url": "https://checkout.paystack.com/abc"}
    return client


def charge(reference, amount_kobo=20_000_000, status="success", currency="NGN"):
    return {"id": 5551234, "reference": reference, "amount": amount_kobo, "status": status, "currency": currency}


@override_settings(PAYMENT_PROVIDER="paystack", PAYSTACK_SECRET_KEY=SECRET, CHOROPIA_SITE_URL="https://choropia.test")
class PaystackCheckoutTests(TestCase):
    def test_reference_and_metadata_identify_choropia(self):
        order = make_order()
        client = paystack_mock()
        with mock.patch("payments.services._paystack", return_value=client):
            payment = initialize_payment(order)

        self.assertRegex(payment.reference, r"^CHOROPIA-ORDER-\d{8}-[0-9A-F]{12}$")
        self.assertEqual(payment.provider, Payment.Provider.PAYSTACK)
        self.assertEqual(payment.authorization_url, "https://checkout.paystack.com/abc")
        kwargs = client.initialize_transaction.call_args.kwargs
        self.assertEqual(kwargs["callback_url"], f"https://choropia.test/orders/{order.id}")
        self.assertEqual(kwargs["metadata"]["app"], "CHOROPIA")
        self.assertEqual(kwargs["metadata"]["order_id"], order.id)
        self.assertEqual(kwargs["metadata"]["custom_fields"][1]["value"], f"Order #{order.id}: Laptop")

    def test_second_initialize_reuses_the_checkout(self):
        order = make_order()
        client = paystack_mock()
        with mock.patch("payments.services._paystack", return_value=client):
            first = initialize_payment(order)
            second = initialize_payment(order)
        self.assertEqual(first.reference, second.reference)
        self.assertEqual(client.initialize_transaction.call_count, 1)

    def test_switching_provider_starts_a_fresh_reference(self):
        order = make_order()
        Payment.objects.create(order=order, reference="order-1-old", amount=order.price, provider="gaxtron",
                               authorization_url="https://gaxtron.test/pay")
        with mock.patch("payments.services._paystack", return_value=paystack_mock()):
            payment = initialize_payment(order)
        self.assertTrue(payment.reference.startswith("CHOROPIA-ORDER-"))
        self.assertEqual(payment.provider, "paystack")


@override_settings(PAYMENT_PROVIDER="paystack", PAYSTACK_SECRET_KEY=SECRET)
class PaystackWebhookTests(TestCase):
    def setUp(self):
        self.order = make_order()
        self.payment = Payment.objects.create(
            order=self.order, reference="CHOROPIA-ORDER-20261023-ABCDEF123456", amount=self.order.price,
            provider="paystack", authorization_url="https://checkout.paystack.com/abc",
        )
        self.client = APIClient()

    def post(self, payload, secret=SECRET):
        body = json.dumps(payload).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
        return self.client.post(WEBHOOK_URL, data=body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig)

    def test_charge_success_moves_order_into_escrow_once(self):
        payload = {"event": "charge.success", "data": charge(self.payment.reference)}
        self.assertEqual(self.post(payload).status_code, 200)
        self.assertEqual(self.post(payload).status_code, 200)  # re-delivery

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID_HELD)
        self.assertEqual(self.payment.paystack_transaction_id, "5551234")
        self.assertEqual(self.order.status, OrderStatus.PAID_ESCROW)
        self.assertEqual(self.order.history.filter(to_status=OrderStatus.PAID_ESCROW).count(), 1)

    def test_bad_signature_is_rejected(self):
        response = self.post({"event": "charge.success", "data": charge(self.payment.reference)}, secret="wrong")
        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.INITIALIZED)

    def test_short_payment_is_not_accepted(self):
        self.post({"event": "charge.success", "data": charge(self.payment.reference, amount_kobo=100)})
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, OrderStatus.PENDING_PAYMENT)

    def test_other_apps_references_are_acknowledged_and_ignored(self):
        response = self.post({"event": "charge.success", "data": charge("NUTRISCAN-PROMONTH-20261023-ABC")})
        self.assertEqual(response.status_code, 200)

    def test_buyer_verify_confirms_without_webhook(self):
        client = mock.Mock()
        client.verify_transaction.return_value = charge(self.payment.reference)
        self.client.force_authenticate(self.order.buyer)
        with mock.patch("payments.services._paystack", return_value=client):
            response = self.client.post("/api/v1/payments/verify/", {"order_id": self.order.id}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order_status"], OrderStatus.PAID_ESCROW)

    def test_only_the_buyer_can_verify(self):
        self.client.force_authenticate(self.order.seller)
        response = self.client.post("/api/v1/payments/verify/", {"order_id": self.order.id}, format="json")
        self.assertEqual(response.status_code, 400)


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class PaystackRefundTests(TestCase):
    def test_refund_goes_through_paystack(self):
        order = make_order(status=OrderStatus.REFUNDED)
        Payment.objects.create(order=order, reference="CHOROPIA-ORDER-X", amount=order.price,
                               provider="paystack", status=Payment.Status.PAID_HELD)
        client = mock.Mock()
        with mock.patch("payments.services._paystack", return_value=client):
            payment = refund_escrow(order)
        client.refund.assert_called_once_with("CHOROPIA-ORDER-X")
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

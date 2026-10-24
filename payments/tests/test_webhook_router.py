"""Ported from the standalone paystack-router's tests, plus Choropia handling its own events."""
import hashlib
import hmac
import json
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings

from orders.state_machine import OrderStatus
from payments.models import Payment
from payments.tests.test_paystack import charge, make_order
from payments.webhook_router import app_for, routes_from

SECRET = "sk_test_unit"
URL = "/api/paystack-webhook"


def sign(body: bytes, secret=SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


class AppForTests(SimpleTestCase):
    def test_routes_by_reference_prefix(self):
        self.assertEqual(app_for({"data": {"reference": "CHOROPIA-ORDER-20261023-ABC"}}), "CHOROPIA")
        self.assertEqual(app_for({"data": {"reference": "NUTRISCAN-PROYEAR-20261023-ABC"}}), "NUTRISCAN")
        self.assertEqual(app_for({"data": {"reference": "VISIONMIRROR-SUPPORT-20261023-ABC"}}), "VISIONMIRROR")

    def test_routes_lowercase_transfer_references(self):
        self.assertEqual(app_for({"data": {"reference": "splitstay-payout-20261023-9c1e"}}), "SPLITSTAY")

    def test_metadata_app_wins_even_as_a_string(self):
        self.assertEqual(app_for({"data": {"reference": "T123456", "metadata": {"app": "MIRROR"}}}), "MIRROR")
        self.assertEqual(app_for({"data": {"reference": "T123456", "metadata": '{"app":"VOICEVERSE"}'}}), "VOICEVERSE")

    def test_refunds_and_disputes_route_by_the_original_transaction(self):
        self.assertEqual(app_for({"data": {"transaction_reference": "CHOROPIA-ORDER-1-ABC"}}), "CHOROPIA")
        self.assertEqual(app_for({"data": {"transaction": {"reference": "MIRROR-PRO-1"}}}), "MIRROR")

    def test_splitstay_references_from_before_the_naming_scheme(self):
        self.assertEqual(app_for({"data": {"reference": "CP-0A1B2C3D4E5F60718293"}}), "SPLITSTAY")
        self.assertEqual(app_for({"data": {"reference": "cp-po-0a1b2c3d4e5f607182930a1b"}}), "SPLITSTAY")

    def test_unknown_and_old_style_references_are_unclaimed(self):
        self.assertEqual(app_for({"data": {"reference": "order-12-abcdef"}}), "")  # old Gaxtron-era Choropia
        self.assertEqual(app_for({"data": {"reference": "T123456"}}), "")
        self.assertEqual(app_for({}), "")
        self.assertEqual(app_for({"data": None}), "")

    def test_routes_read_only_known_apps_and_never_choropia(self):
        env = {"ROUTE_MIRROR": " https://m/hook ", "ROUTE_OTHER": "https://x", "ROUTE_CHOROPIA": "https://self/"}
        self.assertEqual(routes_from(env), {"MIRROR": "https://m/hook"})


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class RouterViewTests(TestCase):
    def post(self, body, signature=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        return self.client.post(
            URL, data=raw, content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sign(raw) if signature is None else signature,
        )

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(URL).status_code, 405)

    def test_bad_signature_is_rejected_and_nothing_is_forwarded(self):
        with mock.patch("payments.webhook_router.requests.post") as post, mock.patch.dict(
            "os.environ", {"ROUTE_NUTRISCAN": "https://n/hook"}
        ):
            response = self.post({"data": {"reference": "NUTRISCAN-PROMONTH-1"}}, signature="nope")
        self.assertEqual(response.status_code, 401)
        post.assert_not_called()

    def test_signature_from_the_wrong_secret_is_rejected(self):
        raw = b'{"data":{"reference":"CHOROPIA-ORDER-1"}}'
        self.assertEqual(self.post(raw, signature=sign(raw, secret="sk_test_other")).status_code, 401)

    def test_forwards_the_exact_bytes_and_signature_to_the_right_app(self):
        body = b'{"event":"charge.success","data":{"reference":"NUTRISCAN-PROMONTH-20261023-ABC","amount":150000}}'
        upstream = mock.Mock(ok=True, status_code=200)
        with mock.patch("payments.webhook_router.requests.post", return_value=upstream) as post, mock.patch.dict(
            "os.environ", {"ROUTE_NUTRISCAN": "https://n/hook", "ROUTE_MIRROR": "https://m/hook"}
        ):
            response = self.post(body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"routed": True, "app": "NUTRISCAN"})
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://n/hook")
        self.assertEqual(kwargs["data"], body)  # byte for byte
        self.assertEqual(kwargs["headers"]["x-paystack-signature"], sign(body))
        self.assertFalse(kwargs["allow_redirects"])

    def test_acknowledges_events_no_app_claims(self):
        with mock.patch("payments.webhook_router.requests.post") as post:
            response = self.post({"event": "charge.success", "data": {"reference": "T999"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["routed"], False)
        post.assert_not_called()

    def test_acknowledges_a_known_app_with_no_route_configured(self):
        with mock.patch.dict("os.environ", {}, clear=False), mock.patch(
            "payments.webhook_router.routes_from", return_value={}
        ):
            response = self.post({"data": {"reference": "VOICEVERSE-SUPPORT-1"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"routed": False, "app": "VOICEVERSE"})

    def test_tells_paystack_to_retry_when_the_app_refuses(self):
        upstream = mock.Mock(ok=False, status_code=500)
        with mock.patch("payments.webhook_router.requests.post", return_value=upstream), mock.patch.dict(
            "os.environ", {"ROUTE_MIRROR": "https://m/hook"}
        ):
            response = self.post({"event": "charge.success", "data": {"reference": "MIRROR-PRO-1"}})
        self.assertEqual(response.status_code, 502)

    def test_tells_paystack_to_retry_when_the_app_is_unreachable(self):
        with mock.patch(
            "payments.webhook_router.requests.post", side_effect=requests.ConnectionError("down")
        ), mock.patch.dict("os.environ", {"ROUTE_MIRROR": "https://m/hook"}):
            response = self.post({"event": "charge.success", "data": {"reference": "MIRROR-PRO-1"}})
        self.assertEqual(response.status_code, 502)

    def test_invalid_json_is_a_400(self):
        self.assertEqual(self.post(b"{not json").status_code, 400)

    def test_choropia_events_are_handled_in_process_not_forwarded(self):
        order = make_order()
        payment = Payment.objects.create(
            order=order, reference="CHOROPIA-ORDER-20261023-ABCDEF123456", amount=order.price,
            provider="paystack", authorization_url="https://checkout.paystack.com/abc",
        )
        payload = {"event": "charge.success", "data": charge(payment.reference)}
        with mock.patch("payments.webhook_router.requests.post") as post:
            response = self.post(payload)
            self.assertEqual(self.post(payload).status_code, 200)  # Paystack re-delivers
        self.assertEqual(response.json(), {"routed": True, "app": "CHOROPIA"})
        post.assert_not_called()

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID_HELD)
        self.assertEqual(order.status, OrderStatus.PAID_ESCROW)
        self.assertEqual(order.history.filter(to_status=OrderStatus.PAID_ESCROW).count(), 1)

    def test_choropia_processing_failure_makes_paystack_retry(self):
        payload = {"event": "charge.success", "data": charge("CHOROPIA-ORDER-20261023-ABCDEF123456")}
        with mock.patch("payments.webhook_router.confirm_paystack_payment", side_effect=RuntimeError("db down")):
            self.assertEqual(self.post(payload).status_code, 502)

"""The escrow as a whole: one item sold once, a buyer who has the item can always release, a seller who never
ships cannot hold the money, and disputes can be resolved. Paystack is always mocked."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from delivery.models import Delivery
from listings.models import Category, Listing
from orders.admin import OrderAdmin
from orders.models import Order
from orders.state_machine import OrderStatus, validate_transition, InvalidOrderTransition
from payments import payouts, services
from payments.models import Payment, Payout, PayoutAccount
from payments.paystack import PaystackError
from payments.tasks import auto_refund_undispatched_task
from payments.tests.test_paystack import SECRET, charge

User = get_user_model()
PS_SERVICES = "payments.services._paystack"
PS_PAYOUTS = "payments.payouts._paystack"


def make_listing(price="20000.00"):
    seller = User.objects.create_user(f"seller{User.objects.count()}@example.com", "pw12345!", first_name="Seller")
    category = Category.objects.get_or_create(name="Electronics")[0]
    return Listing.objects.create(owner=seller, category=category, title="Laptop", price=price)


def make_buyer():
    return User.objects.create_user(f"buyer{User.objects.count()}@example.com", "pw12345!", first_name="Buyer")


def order_for(listing, buyer=None, status=OrderStatus.PENDING_PAYMENT):
    buyer = buyer or make_buyer()
    return Order.objects.create(listing=listing, buyer=buyer, seller=listing.owner, price=listing.price, status=status)


def payment_for(order, status=Payment.Status.INITIALIZED, paid_days_ago=None):
    payment = Payment.objects.create(
        order=order, reference=f"CHOROPIA-ORDER-20261026-{order.id:012X}", amount=order.price, provider="paystack",
        status=status, authorization_url="https://checkout.paystack.com/x",
    )
    if paid_days_ago is not None:
        payment.paid_at = timezone.now() - timedelta(days=paid_days_ago)
        payment.save(update_fields=["paid_at"])
    return payment


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class StateMachineAdditionsTests(TestCase):
    def test_new_transitions(self):
        for current, target in (
            (OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED),
            (OrderStatus.PAID_ESCROW, OrderStatus.REFUNDED),
            (OrderStatus.COURIER_ASSIGNED, OrderStatus.DISPUTED),
            (OrderStatus.IN_TRANSIT, OrderStatus.DISPUTED),
        ):
            validate_transition(current, target)

    def test_still_no_shortcuts_to_paid_out(self):
        for current, target in (
            (OrderStatus.PAID_ESCROW, OrderStatus.COMPLETED),
            (OrderStatus.PAID_ESCROW, OrderStatus.DELIVERED),
            (OrderStatus.PENDING_PAYMENT, OrderStatus.REFUNDED),
            (OrderStatus.CANCELLED, OrderStatus.PAID_ESCROW),
            (OrderStatus.REFUNDED, OrderStatus.PAID_ESCROW),
        ):
            with self.assertRaises(InvalidOrderTransition):
                validate_transition(current, target)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYMENT_PROVIDER="paystack", PAYOUTS_ENABLED=True, CHOROPIA_SITE_URL="https://choropia.test")
class OneItemSoldOnceTests(TestCase):
    def pay(self, payment):
        with mock.patch(PS_SERVICES) as ps, self.captureOnCommitCallbacks(execute=True):
            services.confirm_paystack_payment(payment.reference, charge(payment.reference, amount_kobo=int(Decimal(payment.amount) * 100)))
        return ps

    def test_a_confirmed_payment_marks_the_item_sold(self):
        listing = make_listing()
        payment = payment_for(order_for(listing))
        self.pay(payment)
        listing.refresh_from_db()
        self.assertEqual(listing.status, Listing.Status.SOLD)
        self.assertEqual(Payment.objects.get(pk=payment.pk).status, Payment.Status.PAID_HELD)

    def test_nobody_can_start_an_order_for_an_item_someone_has_paid_for(self):
        listing = make_listing()
        self.pay(payment_for(order_for(listing)))
        listing.status = Listing.Status.ACTIVE  # even if it somehow still shows as for sale
        listing.save()
        response = client_for(make_buyer()).post("/api/v1/orders/", {"listing": listing.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("bought by someone else", str(response.json()))

    def test_a_sold_listing_cannot_be_ordered_at_all(self):
        listing = make_listing()
        listing.status = Listing.Status.SOLD
        listing.save()
        self.assertEqual(client_for(make_buyer()).post("/api/v1/orders/", {"listing": listing.id}, format="json").status_code, 400)

    def test_checkout_is_refused_for_an_item_that_has_just_sold(self):
        listing = make_listing()
        first, second = order_for(listing), order_for(listing)
        self.pay(payment_for(first))
        response = client_for(second.buyer).post("/api/v1/payments/initialize/", {"order_id": second.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer available", str(response.json()))

    def test_the_second_payer_in_a_race_is_cancelled_and_refunded_in_full(self):
        listing = make_listing()
        first, second = order_for(listing), order_for(listing)
        first_payment, second_payment = payment_for(first), payment_for(second)  # both got to checkout
        self.pay(first_payment)

        ps = mock.Mock()
        with mock.patch(PS_SERVICES, return_value=ps), self.captureOnCommitCallbacks(execute=True):
            services.confirm_paystack_payment(second_payment.reference, charge(second_payment.reference, amount_kobo=2_000_000))
        second.refresh_from_db(), first.refresh_from_db(), second_payment.refresh_from_db()
        self.assertEqual(first.status, OrderStatus.PAID_ESCROW)  # the winner is untouched
        self.assertEqual(second.status, OrderStatus.CANCELLED)
        self.assertEqual(second_payment.status, Payment.Status.REFUNDED)
        ps.refund.assert_called_once_with(second_payment.reference)
        self.assertFalse(Payout.objects.filter(payment=second_payment).exists())

    def test_a_refund_paystack_cannot_make_yet_is_kept_pending_and_retried(self):
        listing = make_listing()
        first, second = order_for(listing), order_for(listing)
        self.pay(payment_for(first))
        second_payment = payment_for(second)
        broken = mock.Mock()
        broken.refund.side_effect = PaystackError("Paystack unreachable: timed out")
        with mock.patch(PS_SERVICES, return_value=broken), self.captureOnCommitCallbacks(execute=True):
            services.confirm_paystack_payment(second_payment.reference, charge(second_payment.reference, amount_kobo=2_000_000))
        second_payment.refresh_from_db()
        self.assertEqual(second_payment.status, Payment.Status.REFUND_PENDING)

        working = mock.Mock()
        with mock.patch(PS_SERVICES, return_value=working):
            result = services.retry_pending_refunds()
        second_payment.refresh_from_db()
        self.assertEqual(second_payment.status, Payment.Status.REFUNDED)
        self.assertEqual(result["refunded"], [second_payment.pk])

    def test_a_refund_paystack_says_is_already_done_counts_as_done(self):
        listing = make_listing()
        first, second = order_for(listing), order_for(listing)
        self.pay(payment_for(first))
        second_payment = payment_for(second)
        already = mock.Mock()
        already.refund.side_effect = PaystackError("Transaction has already been fully reversed. Refund already processed")
        with mock.patch(PS_SERVICES, return_value=already), self.captureOnCommitCallbacks(execute=True):
            services.confirm_paystack_payment(second_payment.reference, charge(second_payment.reference, amount_kobo=2_000_000))
        second_payment.refresh_from_db()
        self.assertEqual(second_payment.status, Payment.Status.REFUNDED)


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYMENT_PROVIDER="paystack", PAYOUTS_ENABLED=True, COMMISSION_TIERS=[],
                   PLATFORM_COMMISSION_PERCENT=Decimal("5"), PAYOUT_MAX_NGN=Decimal("2000000"), CHOROPIA_SITE_URL="https://choropia.test")
class BuyerAndSellerStepsTests(TestCase):
    def setUp(self):
        self.listing = make_listing("20000.00")
        self.order = order_for(self.listing, status=OrderStatus.PAID_ESCROW)
        self.payment = payment_for(self.order, status=Payment.Status.PAID_HELD, paid_days_ago=0)
        self.buyer, self.seller = self.order.buyer, self.order.seller
        PayoutAccount.objects.create(user=self.seller, bank_code="058", bank_name="GTBank", account_last4="1234", account_name="ADA", recipient_code="RCP_1")
        self.url = f"/api/v1/orders/{self.order.id}/"

    def confirm(self):
        ps = mock.Mock()
        ps.initiate_transfer.return_value = {"status": "pending", "transfer_code": "TRF_1"}
        with mock.patch(PS_PAYOUTS, return_value=ps), self.captureOnCommitCallbacks(execute=True):
            response = client_for(self.buyer).post(self.url + "confirm_receipt/")
        return response, ps

    def test_a_buyer_who_has_the_item_can_confirm_straight_from_paid(self):
        response, ps = self.confirm()
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(Payment.objects.get(pk=self.payment.pk).status, Payment.Status.RELEASED)
        ps.initiate_transfer.assert_called_once()
        self.assertEqual(ps.initiate_transfer.call_args.kwargs["amount"], Decimal("19000.00"))  # 95% of 20,000

    def test_the_skipped_courier_stages_are_recorded_in_the_history(self):
        self.confirm()
        stages = list(self.order.history.order_by("id").values_list("to_status", flat=True))
        self.assertEqual(stages, ["courier_assigned", "in_transit", "delivered", "confirmed", "completed"])

    def test_it_also_works_from_in_transit_and_from_delivered(self):
        for start in (OrderStatus.COURIER_ASSIGNED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED):
            order = order_for(make_listing(), status=start)
            payment_for(order, status=Payment.Status.PAID_HELD, paid_days_ago=0)
            with mock.patch(PS_PAYOUTS, return_value=mock.Mock()), self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(client_for(order.buyer).post(f"/api/v1/orders/{order.id}/confirm_receipt/").status_code, 200, start)
            order.refresh_from_db()
            self.assertEqual(order.status, OrderStatus.COMPLETED, start)

    def test_only_the_buyer_can_confirm_and_only_once(self):
        self.assertEqual(client_for(self.seller).post(self.url + "confirm_receipt/").status_code, 403)
        self.assertEqual(client_for(make_buyer()).post(self.url + "confirm_receipt/").status_code, 404)
        self.confirm()
        with mock.patch(PS_PAYOUTS, return_value=mock.Mock()):
            self.assertEqual(client_for(self.buyer).post(self.url + "confirm_receipt/").status_code, 400)
        self.assertEqual(Payout.objects.filter(payment=self.payment).count(), 1)

    def test_an_unpaid_or_disputed_order_cannot_be_confirmed(self):
        for status in (OrderStatus.PENDING_PAYMENT, OrderStatus.DISPUTED, OrderStatus.REFUNDED):
            order = order_for(make_listing(), status=status)
            self.assertEqual(client_for(order.buyer).post(f"/api/v1/orders/{order.id}/confirm_receipt/").status_code, 400, status)

    def test_the_automatic_stages_send_no_notifications_or_emails(self):
        from notifications.models import Notification

        before = Notification.objects.count()
        self.confirm()
        statuses = [n.verb for n in Notification.objects.all()[before:]]
        self.assertFalse(any("courier_assigned" in v or "in_transit" in v or "'delivered'" in v for v in statuses))
        self.assertFalse(any("Your order is on its way" in m.subject or "was delivered" in m.subject for m in mail.outbox))

    def test_seller_marks_in_transit_then_delivered(self):
        self.order.status = OrderStatus.COURIER_ASSIGNED
        self.order.save()
        Delivery.objects.create(order=self.order, provider_name="Mock", tracking_id="T1", status="pending")
        seller = client_for(self.seller)
        self.assertEqual(seller.post(self.url + "mark_in_transit/").status_code, 200)
        self.assertEqual(Delivery.objects.get(order=self.order).status, "in_transit")
        self.assertEqual(seller.post(self.url + "mark_delivered/").status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)
        self.assertIsNotNone(self.order.delivered_at)
        self.assertEqual(Delivery.objects.get(order=self.order).status, "delivered")

    def test_the_seller_cannot_skip_stages_and_the_buyer_cannot_do_seller_steps(self):
        seller, buyer = client_for(self.seller), client_for(self.buyer)
        self.assertEqual(seller.post(self.url + "mark_delivered/").status_code, 400)   # still PAID_ESCROW
        self.assertEqual(seller.post(self.url + "mark_in_transit/").status_code, 400)  # not dispatched yet
        self.assertEqual(buyer.post(self.url + "mark_in_transit/").status_code, 403)
        self.assertEqual(buyer.post(self.url + "mark_delivered/").status_code, 403)

    def test_a_buyer_can_dispute_an_item_that_never_arrived_while_it_is_in_transit(self):
        self.order.status = OrderStatus.IN_TRANSIT
        self.order.save()
        response = client_for(self.buyer).post(self.url + "open_dispute/", {"reason": "It never arrived"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DISPUTED)

    def test_the_buyer_cannot_fake_courier_progress_through_the_delivery_endpoint(self):
        self.order.status = OrderStatus.COURIER_ASSIGNED
        self.order.save()
        delivery = Delivery.objects.create(order=self.order, provider_name="Mock", tracking_id="T1", status="pending")
        url = f"/api/v1/deliveries/{delivery.id}/advance_status/"
        self.assertEqual(client_for(self.buyer).post(url, {"status": "delivered"}, format="json").status_code, 403)
        self.assertEqual(client_for(self.seller).post(url, {"status": "picked_up"}, format="json").status_code, 200)

    def test_the_seller_sees_the_commission_the_buyer_does_not(self):
        self.confirm()
        self.assertEqual(client_for(self.seller).get(self.url).json()["payout"]["commission_amount"], "1000.00")
        self.assertIsNone(client_for(self.buyer).get(self.url).json()["payout"])


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYMENT_PROVIDER="paystack", ESCROW_DISPATCH_DEADLINE_DAYS=7)
class SellerNeverShipsTests(TestCase):
    def make(self, paid_days_ago, status=OrderStatus.PAID_ESCROW):
        listing = make_listing()
        listing.status = Listing.Status.SOLD
        listing.save()
        order = order_for(listing, status=status)
        return order, payment_for(order, status=Payment.Status.PAID_HELD, paid_days_ago=paid_days_ago)

    def run_job(self, ps=None):
        with mock.patch(PS_SERVICES, return_value=ps or mock.Mock()):
            return auto_refund_undispatched_task()

    def test_an_order_left_undispatched_past_the_deadline_is_refunded_and_the_item_relisted(self):
        order, payment = self.make(paid_days_ago=8)
        ps = mock.Mock()
        result = self.run_job(ps)
        order.refresh_from_db(), payment.refresh_from_db(), order.listing.refresh_from_db()
        self.assertEqual(result["refunded"], [order.id])
        self.assertEqual(order.status, OrderStatus.REFUNDED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(order.listing.status, Listing.Status.ACTIVE)
        ps.refund.assert_called_once_with(payment.reference)
        self.assertFalse(Payout.objects.exists())  # the seller is never paid for an order that was refunded

    def test_orders_inside_the_deadline_or_already_dispatched_are_left_alone(self):
        recent, _ = self.make(paid_days_ago=3)
        dispatched, _ = self.make(paid_days_ago=30, status=OrderStatus.COURIER_ASSIGNED)
        ps = mock.Mock()
        result = self.run_job(ps)
        self.assertEqual(result["refunded"], [])
        ps.refund.assert_not_called()
        recent.refresh_from_db(), dispatched.refresh_from_db()
        self.assertEqual((recent.status, dispatched.status), (OrderStatus.PAID_ESCROW, OrderStatus.COURIER_ASSIGNED))

    def test_if_paystack_cannot_refund_nothing_changes_and_the_next_run_retries(self):
        order, payment = self.make(paid_days_ago=9)
        broken = mock.Mock()
        broken.refund.side_effect = PaystackError("Paystack unreachable: timed out")
        result = self.run_job(broken)
        order.refresh_from_db(), payment.refresh_from_db()
        self.assertEqual((result["refunded"], order.status, payment.status), ([], OrderStatus.PAID_ESCROW, Payment.Status.PAID_HELD))
        self.assertEqual(self.run_job()["refunded"], [order.id])  # the retry succeeds

    def test_running_it_twice_refunds_once(self):
        order, _ = self.make(paid_days_ago=9)
        ps = mock.Mock()
        self.run_job(ps)
        self.run_job(ps)
        ps.refund.assert_called_once()

    def test_the_item_is_not_relisted_if_another_buyer_holds_it(self):
        order, _ = self.make(paid_days_ago=9)
        other = order_for(order.listing, status=OrderStatus.PAID_ESCROW)  # defensive: should never happen
        self.run_job()
        order.listing.refresh_from_db()
        self.assertEqual(order.listing.status, Listing.Status.SOLD)

    def test_both_sides_are_told(self):
        order, _ = self.make(paid_days_ago=9)
        with mock.patch(PS_SERVICES, return_value=mock.Mock()), self.captureOnCommitCallbacks(execute=True):
            auto_refund_undispatched_task()
        self.assertEqual({m.to[0] for m in mail.outbox}, {order.buyer.email, order.seller.email})


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class AdminDisputeResolutionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser("boss@example.com", "pw12345!")
        listing = make_listing()
        self.order = order_for(listing, status=OrderStatus.DISPUTED)
        self.payment = payment_for(self.order, status=Payment.Status.PAID_HELD, paid_days_ago=1)
        self.admin = OrderAdmin(Order, django_admin.site)

    def request(self):
        request = RequestFactory().post("/admin/orders/order/")
        request.user = self.staff
        request.session = "session"
        request._messages = FallbackStorage(request)
        return request

    def test_refund_the_buyer(self):
        with mock.patch(PS_SERVICES) as ps:
            self.admin.resolve_refund_buyer(self.request(), Order.objects.filter(pk=self.order.pk))
        self.order.refresh_from_db(), self.payment.refresh_from_db()
        self.assertEqual((self.order.status, self.payment.status), (OrderStatus.REFUNDED, Payment.Status.REFUNDED))
        ps.return_value.refund.assert_called_once()

    def test_pay_the_seller(self):
        with mock.patch(PS_PAYOUTS, return_value=mock.Mock()):
            self.admin.resolve_release_to_seller(self.request(), Order.objects.filter(pk=self.order.pk))
        self.order.refresh_from_db(), self.payment.refresh_from_db()
        self.assertEqual((self.order.status, self.payment.status), (OrderStatus.COMPLETED, Payment.Status.RELEASED))
        self.assertTrue(Payout.objects.filter(payment=self.payment).exists())

    def test_only_disputed_orders_are_touched(self):
        other = order_for(make_listing(), status=OrderStatus.DELIVERED)
        payment_for(other, status=Payment.Status.PAID_HELD)
        with mock.patch(PS_SERVICES):
            self.admin.resolve_refund_buyer(self.request(), Order.objects.filter(pk=other.pk))
        other.refresh_from_db()
        self.assertEqual(other.status, OrderStatus.DELIVERED)

    def test_a_failed_paystack_refund_leaves_the_dispute_open(self):
        broken = mock.Mock()
        broken.refund.side_effect = PaystackError("Paystack unreachable")
        with mock.patch(PS_SERVICES, return_value=broken):
            self.admin.resolve_refund_buyer(self.request(), Order.objects.filter(pk=self.order.pk))
        self.order.refresh_from_db(), self.payment.refresh_from_db()
        self.assertEqual((self.order.status, self.payment.status), (OrderStatus.DISPUTED, Payment.Status.PAID_HELD))

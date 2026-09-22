from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from listings.models import Category, Listing
from orders.models import Order
from orders.state_machine import OrderStatus
from payments.models import Payment
from payments.services import release_escrow
from payments.tasks import auto_release_escrow_task

User = get_user_model()


def make_order(status=OrderStatus.PENDING_PAYMENT, delivered_at=None):
    buyer = User.objects.create_user(email=f"buyer{User.objects.count()}@example.com", password="pw12345!")
    seller = User.objects.create_user(email=f"seller{User.objects.count()}@example.com", password="pw12345!")
    category = Category.objects.get_or_create(name="Electronics")[0]
    listing = Listing.objects.create(owner=seller, category=category, title="Laptop", price="200000.00")
    order = Order.objects.create(listing=listing, buyer=buyer, seller=seller, price=listing.price, status=status)
    if delivered_at is not None:
        order.delivered_at = delivered_at
        order.save(update_fields=["delivered_at"])
    Payment.objects.create(
        order=order, reference=f"ref-{order.id}", amount=order.price, status=Payment.Status.PAID_HELD
    )
    return order


@override_settings(ESCROW_AUTO_RELEASE_DAYS=3, PAYSTACK_SECRET_KEY="")
class ReleaseEscrowServiceTests(TestCase):
    def test_release_marks_payment_released_and_not_auto(self):
        order = make_order(status=OrderStatus.CONFIRMED)
        payment = release_escrow(order, auto=False)

        self.assertEqual(payment.status, Payment.Status.RELEASED)
        self.assertFalse(payment.auto_released)
        self.assertIsNotNone(payment.released_at)

    def test_release_is_idempotent(self):
        order = make_order(status=OrderStatus.CONFIRMED)
        first = release_escrow(order, auto=False)
        second = release_escrow(order, auto=True)  # second call must be a harmless no-op

        self.assertEqual(first.released_at, second.released_at)
        self.assertFalse(second.auto_released)  # unaffected by the second call's flag

    def test_cannot_release_a_payment_that_was_never_held(self):
        order = make_order(status=OrderStatus.PENDING_PAYMENT)
        order.payment.status = Payment.Status.INITIALIZED
        order.payment.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            release_escrow(order)


@override_settings(ESCROW_AUTO_RELEASE_DAYS=3, PAYSTACK_SECRET_KEY="")
class AutoReleaseEscrowTaskTests(TestCase):
    def test_order_delivered_past_window_is_auto_completed_and_released(self):
        order = make_order(
            status=OrderStatus.DELIVERED, delivered_at=timezone.now() - timedelta(days=4)
        )

        result = auto_release_escrow_task()

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(order.payment.status, Payment.Status.RELEASED)
        self.assertTrue(order.payment.auto_released)
        self.assertIn(order.id, result["released"])

    def test_order_delivered_within_window_is_left_alone(self):
        order = make_order(
            status=OrderStatus.DELIVERED, delivered_at=timezone.now() - timedelta(days=1)
        )

        result = auto_release_escrow_task()

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED)
        self.assertEqual(order.payment.status, Payment.Status.PAID_HELD)
        self.assertNotIn(order.id, result["released"])

    def test_disputed_order_is_never_touched_even_if_past_window(self):
        order = make_order(
            status=OrderStatus.DELIVERED, delivered_at=timezone.now() - timedelta(days=10)
        )
        order.transition_to(OrderStatus.DISPUTED, note="item not as described")

        result = auto_release_escrow_task()

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DISPUTED)
        self.assertEqual(order.payment.status, Payment.Status.PAID_HELD)
        self.assertNotIn(order.id, result["released"])

    def test_buyer_confirmed_order_is_not_double_processed(self):
        order = make_order(
            status=OrderStatus.DELIVERED, delivered_at=timezone.now() - timedelta(days=10)
        )
        order.transition_to(OrderStatus.CONFIRMED)
        order.transition_to(OrderStatus.COMPLETED)
        release_escrow(order, auto=False)

        result = auto_release_escrow_task()

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertFalse(order.payment.auto_released)  # was released manually, task must not touch it
        self.assertNotIn(order.id, result["released"])

    def test_multiple_orders_are_processed_independently(self):
        due = make_order(status=OrderStatus.DELIVERED, delivered_at=timezone.now() - timedelta(days=5))
        not_due = make_order(status=OrderStatus.DELIVERED, delivered_at=timezone.now() - timedelta(hours=1))

        result = auto_release_escrow_task()

        self.assertIn(due.id, result["released"])
        self.assertNotIn(not_due.id, result["released"])

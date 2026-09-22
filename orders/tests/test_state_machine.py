from django.contrib.auth import get_user_model
from django.test import TestCase

from listings.models import Category, Listing
from orders.models import Order
from orders.state_machine import InvalidOrderTransition, OrderStatus, validate_transition

User = get_user_model()


class StateMachineGraphTests(TestCase):
    """Pure graph-level tests: no DB objects, just the transition table itself."""

    def test_valid_happy_path_transitions_are_allowed(self):
        happy_path = [
            (OrderStatus.PENDING_PAYMENT, OrderStatus.PAID_ESCROW),
            (OrderStatus.PAID_ESCROW, OrderStatus.COURIER_ASSIGNED),
            (OrderStatus.COURIER_ASSIGNED, OrderStatus.IN_TRANSIT),
            (OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED),
            (OrderStatus.DELIVERED, OrderStatus.CONFIRMED),
            (OrderStatus.CONFIRMED, OrderStatus.COMPLETED),
        ]
        for current, target in happy_path:
            validate_transition(current, target)  # should not raise

    def test_dispute_path_transitions_are_allowed(self):
        validate_transition(OrderStatus.DELIVERED, OrderStatus.DISPUTED)
        validate_transition(OrderStatus.DISPUTED, OrderStatus.REFUNDED)
        validate_transition(OrderStatus.DISPUTED, OrderStatus.COMPLETED)

    def test_cannot_skip_states(self):
        skips = [
            (OrderStatus.PENDING_PAYMENT, OrderStatus.COURIER_ASSIGNED),
            (OrderStatus.PENDING_PAYMENT, OrderStatus.DELIVERED),
            (OrderStatus.PAID_ESCROW, OrderStatus.DELIVERED),
            (OrderStatus.PAID_ESCROW, OrderStatus.COMPLETED),
            (OrderStatus.COURIER_ASSIGNED, OrderStatus.DELIVERED),
        ]
        for current, target in skips:
            with self.assertRaises(InvalidOrderTransition):
                validate_transition(current, target)

    def test_cannot_move_backwards(self):
        backwards = [
            (OrderStatus.PAID_ESCROW, OrderStatus.PENDING_PAYMENT),
            (OrderStatus.DELIVERED, OrderStatus.IN_TRANSIT),
            (OrderStatus.COMPLETED, OrderStatus.CONFIRMED),
        ]
        for current, target in backwards:
            with self.assertRaises(InvalidOrderTransition):
                validate_transition(current, target)

    def test_terminal_states_have_no_outgoing_transitions(self):
        self.assertEqual(validate_transition.__module__, "orders.state_machine")
        from orders.state_machine import TRANSITIONS

        self.assertEqual(TRANSITIONS[OrderStatus.COMPLETED], set())
        self.assertEqual(TRANSITIONS[OrderStatus.REFUNDED], set())

    def test_cannot_transition_from_or_to_unknown_status(self):
        with self.assertRaises(InvalidOrderTransition):
            validate_transition("not_a_real_status", OrderStatus.PAID_ESCROW)
        with self.assertRaises(InvalidOrderTransition):
            validate_transition(OrderStatus.PENDING_PAYMENT, "not_a_real_status")


class OrderTransitionToTests(TestCase):
    """Tests against the real Order model method, including the audit trail and timestamps."""

    def setUp(self):
        self.buyer = User.objects.create_user(email="buyer@example.com", password="pw12345!")
        self.seller = User.objects.create_user(email="seller@example.com", password="pw12345!")
        category = Category.objects.create(name="Phones")
        listing = Listing.objects.create(
            owner=self.seller, category=category, title="iPhone", price="150000.00"
        )
        self.order = Order.objects.create(listing=listing, buyer=self.buyer, seller=self.seller, price=listing.price)

    def test_transition_to_updates_status_and_records_history(self):
        self.order.transition_to(OrderStatus.PAID_ESCROW, actor=self.buyer, note="gaxtron webhook")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID_ESCROW)

        history = self.order.history.get()
        self.assertEqual(history.from_status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(history.to_status, OrderStatus.PAID_ESCROW)
        self.assertEqual(history.actor, self.buyer)

    def test_invalid_transition_raises_and_leaves_status_and_history_untouched(self):
        with self.assertRaises(InvalidOrderTransition):
            self.order.transition_to(OrderStatus.DELIVERED)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(self.order.history.count(), 0)

    def test_delivered_at_is_stamped_on_delivery(self):
        self.order.transition_to(OrderStatus.PAID_ESCROW)
        self.order.transition_to(OrderStatus.COURIER_ASSIGNED)
        self.order.transition_to(OrderStatus.IN_TRANSIT)
        self.assertIsNone(self.order.delivered_at)

        self.order.transition_to(OrderStatus.DELIVERED)
        self.assertIsNotNone(self.order.delivered_at)

    def test_full_happy_path_reaches_completed(self):
        for target in [
            OrderStatus.PAID_ESCROW,
            OrderStatus.COURIER_ASSIGNED,
            OrderStatus.IN_TRANSIT,
            OrderStatus.DELIVERED,
            OrderStatus.CONFIRMED,
            OrderStatus.COMPLETED,
        ]:
            self.order.transition_to(target)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertIsNotNone(self.order.completed_at)
        self.assertEqual(self.order.history.count(), 6)

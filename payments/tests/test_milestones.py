from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from accounts.models import User
from listings.models import Category, Listing
from orders.models import Order
from payments import milestones
from payments.models import Payment


class MilestoneStepTests(TestCase):
    def test_thresholds_step_up_and_never_show_exact_figures(self):
        steps = []
        for value in milestones.thresholds():
            if value > 1_000_000_000:
                break
            steps.append(value)
        self.assertEqual(steps, [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000, 50_000_000, 100_000_000, 500_000_000, 1_000_000_000])
        self.assertEqual(milestones.highest_milestone(0), 0)
        self.assertEqual(milestones.highest_milestone(99_999), 0)
        self.assertEqual(milestones.highest_milestone(100_000), 100_000)
        self.assertEqual(milestones.highest_milestone(499_999), 100_000)
        self.assertEqual(milestones.highest_milestone(2_300_000), 1_000_000)
        self.assertEqual(milestones.short_label(100_000), "\u20a6100,000")
        self.assertEqual(milestones.short_label(5_000_000), "\u20a65M")


class MilestoneEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.seller = User.objects.create_user("s@example.com", "pw12345!")
        self.buyer = User.objects.create_user("b@example.com", "pw12345!")
        self.listing = Listing.objects.create(owner=self.seller, category=Category.objects.create(name="Gadgets"), title="Phone", price="10.00")

    def _pay(self, amount, status, ref):
        order = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=amount, status="paid_escrow")
        Payment.objects.create(order=order, reference=ref, amount=Decimal(amount), status=status)

    def test_public_endpoint_hides_small_totals_and_exact_amounts(self):
        self._pay("200.00", Payment.Status.PAID_HELD, "CHOROPIA-ORDER-20261111-AAAAAAAAAAAA")
        body = self.client.get("/api/v1/escrow/milestone/").json()
        self.assertEqual(body, {"milestone": 0, "label": ""})

    def test_reaching_a_threshold_shows_it_and_ignores_unpaid_money(self):
        self._pay("150000.00", Payment.Status.RELEASED, "CHOROPIA-ORDER-20261111-BBBBBBBBBBBB")
        self._pay("900000.00", Payment.Status.INITIALIZED, "CHOROPIA-ORDER-20261111-CCCCCCCCCCCC")
        body = self.client.get("/api/v1/escrow/milestone/").json()
        self.assertEqual(body, {"milestone": 100_000, "label": "\u20a6100,000"})

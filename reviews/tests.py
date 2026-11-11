from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from listings.models import Category, Listing
from moderation.models import ContactMessage, Report
from orders.models import Order
from reviews.models import Review


class ReviewRulesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name="Gadgets")
        self.seller = User.objects.create_user("seller@example.com", "pw12345!", first_name="Sam")
        self.buyer = User.objects.create_user("buyer@example.com", "pw12345!", first_name="Bea", last_name="Okon")
        self.stranger = User.objects.create_user("stranger@example.com", "pw12345!")
        self.listing = self._listing("First")
        self.client = APIClient()

    def _listing(self, title):
        return Listing.objects.create(owner=self.seller, category=self.category, title=title, price="1000.00")

    def _order(self, status="completed"):
        return Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price="1000.00", status=status)

    def _post(self, order, user=None, rating=5):
        self.client.force_authenticate(user or self.buyer)
        return self.client.post("/api/v1/reviews/", {"order": order.id, "rating": rating, "comment": "Great"}, format="json")

    def test_a_seller_with_one_listing_cannot_be_reviewed(self):
        order = self._order()
        r = self._post(order)
        self.assertEqual(r.status_code, 400)
        self.assertIn("enough listings", str(r.json()))
        self.assertFalse(Review.objects.exists())

    def test_buyer_can_rate_a_consistent_seller_once_after_the_deal(self):
        self._listing("Second")
        order = self._order()
        r = self._post(order, rating=4)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["reviewer_name"], "Bea O.")
        self.assertEqual(self._post(order).status_code, 400)  # one per order
        self.assertEqual(Review.objects.get().reviewee, self.seller)

    def test_confirmed_counts_but_an_unfinished_order_does_not(self):
        self._listing("Second")
        self.assertEqual(self._post(self._order("confirmed")).status_code, 201)
        self.listing = self._listing("Third")
        self.assertEqual(self._post(self._order("in_transit")).status_code, 400)

    def test_only_the_buyer_reviews_and_outsiders_cannot(self):
        self._listing("Second")
        order = self._order()
        self.assertEqual(self._post(order, user=self.seller).status_code, 400)
        self.assertEqual(self._post(order, user=self.stranger).status_code, 400)

    def test_removed_listings_do_not_count_as_posting(self):
        extra = self._listing("Second")
        extra.status = Listing.Status.REMOVED
        extra.save()
        self.assertEqual(self._post(self._order()).status_code, 400)

    def test_summary_is_hidden_until_eligible_and_flags_verified(self):
        body = self.client.get(f"/api/v1/reviews/summary/?user={self.seller.id}").json()
        self.assertFalse(body["eligible"])
        self._listing("Second")
        self._post(self._order(), rating=5)
        self._post(Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price="1.00", status="completed"), rating=4)
        self.seller.profile.seller_verified = True
        self.seller.profile.save()
        body = APIClient().get(f"/api/v1/reviews/summary/?user={self.seller.id}").json()
        self.assertEqual((body["eligible"], body["average"], body["count"], body["verified"]), (True, 4.5, 2, True))

    def test_for_order_tells_the_buyer_why_not(self):
        order = self._order()
        self.client.force_authenticate(self.buyer)
        body = self.client.get(f"/api/v1/reviews/for-order/?order={order.id}").json()
        self.assertFalse(body["can_review"])
        self.assertIn("enough listings", body["reason"])

    @override_settings(STAFF_ALERTS_ENABLED=True, STAFF_ALERT_EMAILS=["boss@example.com"])
    def test_staff_are_emailed_about_every_review(self):
        self._listing("Second")
        order = self._order()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self._post(order, rating=2)
        self.assertTrue(any("2-star review" in m.subject and "boss@example.com" in m.to for m in mail.outbox))


@override_settings(STAFF_ALERTS_ENABLED=True, STAFF_ALERT_EMAILS=["boss@example.com"])
class ContactAndReportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_contact_form_saves_emails_staff_and_confirms_to_the_sender(self):
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/v1/contact/", {"name": "Ada Obi", "email": "ada@example.com", "topic": "problem", "message": "My parcel never arrived."}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ContactMessage.objects.get().email, "ada@example.com")
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertEqual(recipients, {"boss@example.com", "ada@example.com"})
        self.assertTrue(any("My parcel never arrived." in m.body for m in mail.outbox if "boss@example.com" in m.to))

    def test_contact_form_rejects_empty_messages_and_drops_bots_quietly(self):
        self.assertEqual(self.client.post("/api/v1/contact/", {"name": "A", "email": "a@example.com", "message": "hi"}, format="json").status_code, 400)
        mail.outbox.clear()
        r = self.client.post("/api/v1/contact/", {"name": "Bot", "email": "bot@example.com", "message": "Buy cheap watches now please", "website": "http://spam"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_reporting_a_listing_emails_staff_at_once(self):
        seller = User.objects.create_user("s@example.com", "pw12345!")
        reporter = User.objects.create_user("r@example.com", "pw12345!")
        listing = Listing.objects.create(owner=seller, category=Category.objects.create(name="Gadgets"), title="Fake phone", price="5.00")
        self.client.force_authenticate(reporter)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/v1/reports/", {"target_type": "listing", "target_id": listing.id, "reason": "Looks like a scam"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Report.objects.count(), 1)
        self.assertTrue(any("report" in m.subject.lower() and "boss@example.com" in m.to and "Fake phone" in m.body for m in mail.outbox))

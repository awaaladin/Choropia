from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from listings.models import Category, Listing


class SoldVisibilityTests(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Shoes")
        self.listing = Listing.objects.create(
            owner=self.seller,
            category=category,
            title="Trainers",
            price="100.00",
        )

    def test_seller_can_choose_sold_duration(self):
        client = APIClient()
        client.force_authenticate(self.seller)

        response = client.post(
            f"/api/v1/listings/{self.listing.pk}/mark_sold/",
            {"duration_days": 7},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.SOLD)
        self.assertAlmostEqual(
            (self.listing.market_visible_until - self.listing.sold_at).total_seconds(),
            7 * 24 * 60 * 60,
            delta=1,
        )

    def test_invalid_sold_duration_is_rejected(self):
        client = APIClient()
        client.force_authenticate(self.seller)

        response = client.post(
            f"/api/v1/listings/{self.listing.pk}/mark_sold/",
            {"duration_days": 60},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.ACTIVE)

    def test_sold_listing_visibility_ends_at_the_cutoff(self):
        self.listing.status = Listing.Status.SOLD
        self.listing.sold_at = timezone.now() - timedelta(days=4)
        self.listing.market_visible_until = timezone.now() - timedelta(microseconds=1)
        self.listing.save()
        client = APIClient()

        public = client.get("/api/v1/listings/")
        owner = APIClient()
        owner.force_authenticate(self.seller)
        mine = owner.get("/api/v1/listings/?mine=true")
        detail = client.get(f"/api/v1/listings/{self.listing.pk}/")

        self.assertNotIn(self.listing.pk, [row["id"] for row in public.json()["results"]])
        self.assertIn(self.listing.pk, [row["id"] for row in mine.json()["results"]])
        self.assertEqual(detail.status_code, 404)

    def test_sold_listing_is_public_until_its_visibility_deadline(self):
        self.listing.status = Listing.Status.SOLD
        self.listing.sold_at = timezone.now() - timedelta(days=1)
        self.listing.market_visible_until = timezone.now() + timedelta(days=2)
        self.listing.save()
        client = APIClient()

        feed = client.get("/api/v1/listings/")
        detail = client.get(f"/api/v1/listings/{self.listing.pk}/")

        self.assertIn(self.listing.pk, [row["id"] for row in feed.json()["results"]])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], Listing.Status.SOLD)
        self.assertEqual(
            parse_datetime(detail.json()["market_visible_until"]),
            self.listing.market_visible_until,
        )

    def test_relisting_expired_sold_item_clears_sold_metadata_and_restores_visibility(self):
        self.listing.status = Listing.Status.SOLD
        self.listing.quantity = 0
        self.listing.sold_at = timezone.now() - timedelta(days=5)
        self.listing.market_visible_until = timezone.now() - timedelta(days=1)
        self.listing.save()
        client = APIClient()
        client.force_authenticate(self.seller)

        response = client.post(f"/api/v1/listings/{self.listing.pk}/relist/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], Listing.Status.ACTIVE)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, 1)
        self.assertIsNone(self.listing.sold_at)
        self.assertIsNone(self.listing.market_visible_until)
        public = APIClient().get("/api/v1/listings/")
        self.assertIn(self.listing.pk, [row["id"] for row in public.json()["results"]])

    def test_extend_rejects_boolean_duration(self):
        client = APIClient()
        client.force_authenticate(self.seller)
        self.listing.status = Listing.Status.SOLD
        self.listing.save()

        response = client.post(
            f"/api/v1/listings/{self.listing.pk}/extend_market_visibility/",
            {"duration_days": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_owner_can_extend_an_expired_sold_listing_back_into_public_view(self):
        self.listing.status = Listing.Status.SOLD
        self.listing.sold_at = timezone.now() - timedelta(days=5)
        self.listing.market_visible_until = timezone.now() - timedelta(days=1)
        self.listing.save()
        client = APIClient()
        client.force_authenticate(self.seller)

        response = client.post(
            f"/api/v1/listings/{self.listing.pk}/extend_market_visibility/",
            {"duration_days": 7},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.SOLD)
        self.assertGreater(self.listing.market_visible_until, timezone.now())
        public = APIClient().get("/api/v1/listings/")
        self.assertIn(self.listing.pk, [row["id"] for row in public.json()["results"]])

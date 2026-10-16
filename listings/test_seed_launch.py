import shutil
import tempfile

from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from accounts.demo import DEMO_EMAIL_DOMAIN
from accounts.models import User
from listings.models import Category, Listing, ListingPhoto


class SeedLaunchTests(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

    def test_seeds_labelled_listings_with_photos_and_nonloginable_sellers(self):
        call_command("seed_launch", verbosity=0)

        sellers = User.objects.filter(email__endswith="@" + DEMO_EMAIL_DOMAIN)
        self.assertEqual(sellers.count(), 2)
        for seller in sellers:
            self.assertFalse(seller.has_usable_password())  # cannot log in, ever

        listings = Listing.objects.all()
        self.assertGreaterEqual(listings.count(), 8)
        self.assertTrue(all(l.title.startswith("Demo: ") for l in listings))
        self.assertTrue(all("demo listing" in l.description.lower() for l in listings))
        self.assertTrue(all(l.photos.count() == 1 for l in listings))

    def test_is_idempotent(self):
        call_command("seed_launch", verbosity=0)
        before = (User.objects.count(), Listing.objects.count(), ListingPhoto.objects.count())
        call_command("seed_launch", verbosity=0)
        self.assertEqual(before, (User.objects.count(), Listing.objects.count(), ListingPhoto.objects.count()))

    def test_remove_deletes_only_demo_content(self):
        real = User.objects.create_user("real@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Gadgets")
        keep = Listing.objects.create(owner=real, category=category, title="Real item", price="5.00", condition="new")
        call_command("seed_launch", verbosity=0)
        call_command("seed_launch", "--remove", verbosity=0)
        self.assertEqual(list(User.objects.values_list("email", flat=True)), ["real@example.com"])
        self.assertEqual(list(Listing.objects.values_list("id", flat=True)), [keep.id])
        self.assertEqual(ListingPhoto.objects.count(), 0)

    def test_demo_listings_cannot_be_bought_or_messaged(self):
        call_command("seed_launch", verbosity=0)
        buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        client = APIClient()
        client.force_authenticate(buyer)
        demo_listing = Listing.objects.first()

        order = client.post("/api/v1/orders/", {"listing": demo_listing.id}, format="json")
        self.assertEqual(order.status_code, 400)
        self.assertIn("demo listing", str(order.json()).lower())

        chat = client.post("/api/v1/conversations/", {"listing": demo_listing.id}, format="json")
        self.assertEqual(chat.status_code, 400)

    def test_real_listings_are_unaffected_by_the_guard(self):
        seller = User.objects.create_user("seller@example.com", "pw-12345-pw")
        buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Gadgets")
        listing = Listing.objects.create(owner=seller, category=category, title="Real", price="5.00", condition="new")
        client = APIClient()
        client.force_authenticate(buyer)
        self.assertEqual(client.post("/api/v1/orders/", {"listing": listing.id}, format="json").status_code, 201)

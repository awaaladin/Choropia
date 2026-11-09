from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from listings.models import Category, Listing


class PublicProfileTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "profile@example.com",
            "pw-12345-pw",
            first_name="Chidi",
            last_name="Okoro",
        )
        self.viewer = User.objects.create_user("viewer@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Bags")
        self.listing = Listing.objects.create(
            owner=self.owner,
            category=category,
            title="Travel bag",
            price="100.00",
        )

    def test_public_profile_exposes_only_public_fields(self):
        response = APIClient().get(f"/api/v1/users/{self.owner.pk}/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "Chidi Okoro")
        self.assertNotIn("email", response.json())
        self.assertNotIn("phone_number", response.json())
        self.assertNotIn("saved", response.json())
        self.assertNotIn("orders", response.json())

    def test_public_listing_page_shows_only_currently_visible_listings(self):
        response = APIClient().get(f"/api/v1/users/{self.owner.pk}/listings/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()["results"]], [self.listing.pk])

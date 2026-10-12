from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from listings.models import Category, Listing


class MyListingsFilterTests(APITestCase):
    def setUp(self):
        self.me = User.objects.create_user("me@example.com", "pw-12345-pw")
        self.other = User.objects.create_user("other@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Gadgets")

        def make(owner, title, status="active"):
            return Listing.objects.create(
                owner=owner, category=category, title=title, price="10.00", condition="used", status=status
            )

        self.mine_active = make(self.me, "My active")
        self.mine_sold = make(self.me, "My sold", status="sold")
        self.mine_removed = make(self.me, "My removed", status="removed")
        self.theirs = make(self.other, "Theirs")
        self.client = APIClient()

    def _titles(self, query):
        response = self.client.get(f"/api/v1/listings/{query}")
        self.assertEqual(response.status_code, 200)
        return {item["title"] for item in response.json()["results"]}

    def test_public_list_is_active_only(self):
        self.assertEqual(self._titles(""), {"My active", "Theirs"})

    def test_mine_returns_own_including_sold_but_not_removed(self):
        self.client.force_authenticate(self.me)
        self.assertEqual(self._titles("?mine=true"), {"My active", "My sold"})

    def test_mine_when_signed_out_is_empty_not_everyone(self):
        self.assertEqual(self._titles("?mine=true"), set())

    def test_owner_filter_shows_that_users_active_listings(self):
        self.assertEqual(self._titles(f"?owner={self.me.id}"), {"My active"})
        self.assertEqual(self._titles(f"?owner={self.other.id}"), {"Theirs"})

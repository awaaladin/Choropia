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


class DeleteAndPhotoTests(APITestCase):
    def setUp(self):
        from listings.models import ListingPhoto

        self.me = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.other = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        self.category = Category.objects.create(name="Gadgets")
        self.item = Listing.objects.create(owner=self.me, category=self.category, title="Phone", price="10.00", condition="used")
        self.photo = ListingPhoto.objects.create(listing=self.item, image="listings/x.jpg")
        self.client = APIClient()

    def test_owner_can_delete_and_it_disappears_everywhere(self):
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.delete(f"/api/v1/listings/{self.item.id}/").status_code, 204)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "removed")
        self.assertEqual(self.client.get(f"/api/v1/listings/{self.item.id}/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/listings/?mine=true").json()["results"], [])
        self.assertEqual(APIClient().get("/api/v1/listings/").json()["results"], [])

    def test_someone_else_cannot_delete(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.delete(f"/api/v1/listings/{self.item.id}/").status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "active")

    def test_cannot_delete_while_a_buyer_has_paid(self):
        from orders.models import Order

        Order.objects.create(listing=self.item, buyer=self.other, seller=self.me, price="10.00", status="paid_escrow")
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.delete(f"/api/v1/listings/{self.item.id}/").status_code, 403)

    def test_owner_can_remove_a_photo_but_others_cannot(self):
        url = f"/api/v1/listings/{self.item.id}/photos/{self.photo.id}/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertEqual(self.item.photos.count(), 0)

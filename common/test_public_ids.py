from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from chat.models import Conversation
from common.public_ids import ALPHABET, LENGTH, is_public_id, listing_slug, lookup_kwargs, new_public_id
from listings.models import Category, Listing
from orders.models import Order


class CodeTests(TestCase):
    def test_codes_are_random_fixed_length_and_unambiguous(self):
        codes = {new_public_id() for _ in range(2000)}
        self.assertEqual(len(codes), 2000)
        for code in codes:
            self.assertEqual(len(code), LENGTH)
            self.assertTrue(set(code) <= set(ALPHABET))
            self.assertTrue(is_public_id(code))
        self.assertFalse(set("01lio") & set(ALPHABET))

    def test_references_accept_numbers_codes_and_slugs(self):
        self.assertEqual(lookup_kwargs("19"), {"pk": 19})
        self.assertEqual(lookup_kwargs("k7f3q9x2ab"), {"public_id": "k7f3q9x2ab"})
        self.assertEqual(lookup_kwargs("iphone-13-k7f3q9x2ab"), {"public_id": "k7f3q9x2ab"})
        self.assertEqual(lookup_kwargs("iphone-13"), {"pk": -1})  # never treated as id 13
        self.assertEqual(lookup_kwargs("'; drop table"), {"pk": -1})
        self.assertEqual(listing_slug("iPhone 13 Pro!", "k7f3q9x2ab"), "iphone-13-pro-k7f3q9x2ab")


class ApiLookupTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("s@example.com", "pw-12345-pw")
        self.buyer = User.objects.create_user("b@example.com", "pw-12345-pw")
        self.outsider = User.objects.create_user("o@example.com", "pw-12345-pw")
        self.listing = Listing.objects.create(owner=self.seller, category=Category.objects.create(name="Phones"), title="Phone", price="5000.00")
        low, high = sorted([self.seller, self.buyer], key=lambda u: u.pk)
        self.chat = Conversation.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, user_low=low, user_high=high)
        self.order = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price="5000.00")

    def client_for(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        return client

    def test_every_object_gets_its_own_code(self):
        other = Listing.objects.create(owner=self.seller, category=self.listing.category, title="Phone", price="1.00")
        self.assertNotEqual(other.public_id, self.listing.public_id)
        for obj in (self.listing, self.chat, self.order):
            self.assertTrue(is_public_id(obj.public_id))

    def test_listing_by_code_by_slug_and_by_old_number(self):
        for ref in (self.listing.public_id, self.listing.slug, str(self.listing.pk)):
            body = self.client_for().get(f"/api/v1/listings/{ref}/").json()
            self.assertEqual((body["id"], body["public_id"], body["slug"]), (self.listing.pk, self.listing.public_id, self.listing.slug), ref)
        self.assertEqual(self.client_for().get("/api/v1/listings/zzzzzzzzzz/").status_code, 404)

    def test_knowing_a_chat_or_order_code_does_not_let_an_outsider_in(self):
        for path in (f"/api/v1/conversations/{self.chat.public_id}/", f"/api/v1/orders/{self.order.public_id}/"):
            self.assertIn(self.client_for(self.outsider).get(path).status_code, (403, 404), path)
            self.assertEqual(self.client_for(self.buyer).get(path).status_code, 200, path)
        self.assertEqual(self.client_for(self.buyer).get(f"/api/v1/orders/{self.order.public_id}/").json()["public_id"], self.order.public_id)

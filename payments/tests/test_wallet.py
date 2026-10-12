from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from listings.models import Category, Listing
from orders.models import Order
from orders.state_machine import OrderStatus
from payments.models import Payment

User = get_user_model()


class WalletApiTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(email="buyer@example.com", password="pw12345!")
        self.seller = User.objects.create_user(email="seller@example.com", password="pw12345!")
        category = Category.objects.create(name="Electronics")
        listing = Listing.objects.create(owner=self.seller, category=category, title="Laptop", price="200000.00")

        held_order = Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller, price="200000.00", status=OrderStatus.PAID_ESCROW
        )
        Payment.objects.create(order=held_order, reference="ref-held", amount="200000.00", status=Payment.Status.PAID_HELD)

        released_order = Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller, price="50000.00", status=OrderStatus.COMPLETED
        )
        Payment.objects.create(
            order=released_order, reference="ref-released", amount="50000.00", status=Payment.Status.RELEASED
        )

        self.client = APIClient()

    def test_summary_requires_auth(self):
        response = self.client.get("/api/v1/wallet/summary/")
        self.assertEqual(response.status_code, 401)

    def test_seller_summary_totals(self):
        self.client.force_authenticate(self.seller)
        response = self.client.get("/api/v1/wallet/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["selling"]["held_total"]), Decimal("200000.00"))
        self.assertEqual(Decimal(response.data["selling"]["released_total"]), Decimal("50000.00"))

    def test_buyer_summary_totals(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.get("/api/v1/wallet/summary/")
        self.assertEqual(Decimal(response.data["buying"]["held_total"]), Decimal("200000.00"))
        self.assertEqual(Decimal(response.data["buying"]["spent_total"]), Decimal("250000.00"))

    def test_transactions_list_shows_role(self):
        self.client.force_authenticate(self.seller)
        response = self.client.get("/api/v1/wallet/transactions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertTrue(all(row["role"] == "selling" for row in response.data["results"]))

    def test_transactions_excludes_unpaid_orders(self):
        unpaid_order = Order.objects.create(
            listing=Listing.objects.first(), buyer=self.buyer, seller=self.seller, price="1000.00"
        )
        Payment.objects.create(order=unpaid_order, reference="ref-initialized", amount="1000.00")

        self.client.force_authenticate(self.buyer)
        response = self.client.get("/api/v1/wallet/transactions/")
        self.assertEqual(response.data["count"], 2)


class LogoutAllTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="multi@example.com", password="pw12345!")
        self.client = APIClient()

    def test_logout_all_blacklists_every_refresh_token(self):
        first = self.client.post("/api/v1/auth/login/", {"identifier": "multi@example.com", "password": "pw12345!"}).data
        second = self.client.post("/api/v1/auth/login/", {"identifier": "multi@example.com", "password": "pw12345!"}).data

        self.client.force_authenticate(self.user)
        response = self.client.post("/api/v1/auth/logout-all/")
        self.assertEqual(response.status_code, 204)

        self.client.force_authenticate(None)
        for tokens in (first, second):
            refresh_response = self.client.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]})
            self.assertEqual(refresh_response.status_code, 401)

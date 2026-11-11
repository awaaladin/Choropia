"""Stock counts, cancelling orders, the home feed, reading messages, editing a listing, and returning to the app after paying.
Paystack is always mocked."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from chat.models import Conversation, Message
from listings.models import Listing
from notifications.models import Notification
from orders.models import Order
from orders.state_machine import OrderStatus
from payments import services
from payments.models import Payment
from payments.tasks import auto_refund_undispatched_task
from payments.tests.test_escrow_flow import PS_SERVICES, client_for, make_buyer, make_listing, order_for, payment_for
from payments.tests.test_paystack import SECRET, charge

User = get_user_model()


def pay(payment):
    services.confirm_paystack_payment(payment.reference, charge(payment.reference, amount_kobo=int(Decimal(payment.amount) * 100)))
    payment.refresh_from_db()
    return payment


class StockTests(TestCase):
    def test_each_paid_order_takes_one_and_the_last_marks_it_sold(self):
        listing = make_listing()
        Listing.objects.filter(pk=listing.pk).update(quantity=2)
        first, second, third = (payment_for(order_for(listing)) for _ in range(3))
        pay(first)
        listing.refresh_from_db()
        self.assertEqual((listing.quantity, listing.status), (1, Listing.Status.ACTIVE))
        pay(second)
        listing.refresh_from_db()
        self.assertEqual((listing.quantity, listing.status), (0, Listing.Status.SOLD))
        with mock.patch(PS_SERVICES, return_value=mock.Mock()), self.captureOnCommitCallbacks(execute=True):
            pay(third)
        third.refresh_from_db()
        self.assertEqual(third.status, Payment.Status.REFUNDED if third.status == Payment.Status.REFUNDED else Payment.Status.REFUND_PENDING)
        self.assertIn(third.status, (Payment.Status.REFUND_PENDING, Payment.Status.REFUNDED))

    def test_a_refund_after_payment_puts_one_back(self):
        listing = make_listing()
        order = order_for(listing)
        payment = pay(payment_for(order))
        Payment.objects.filter(pk=payment.pk).update(paid_at=timezone.now() - timedelta(days=9))
        with mock.patch(PS_SERVICES, return_value=mock.Mock()):
            auto_refund_undispatched_task()
        listing.refresh_from_db()
        self.assertEqual((listing.quantity, listing.status), (1, Listing.Status.ACTIVE))

    def test_no_new_order_when_none_are_left(self):
        listing = make_listing()
        Listing.objects.filter(pk=listing.pk).update(quantity=0)
        r = client_for(make_buyer()).post("/api/v1/orders/", {"listing": listing.id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("sold out", str(r.json()))

    def test_a_second_unit_can_be_ordered_and_paid_while_the_first_is_held(self):
        listing = make_listing()
        Listing.objects.filter(pk=listing.pk).update(quantity=3)
        pay(payment_for(order_for(listing)))
        r = client_for(make_buyer()).post("/api/v1/orders/", {"listing": listing.id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        buyer = User.objects.get(pk=r.json()["buyer"])
        with mock.patch("payments.services._paystack") as paystack:
            paystack.return_value.initialize_transaction.return_value = {"authorization_url": "https://checkout.paystack.com/x"}
            self.assertEqual(client_for(buyer).post("/api/v1/payments/initialize/", {"order_id": r.json()["id"]}, format="json").status_code, 200)

    def test_quantity_must_be_sensible(self):
        seller = User.objects.create_user("q@example.com", "pw12345!")
        listing = make_listing()
        c = client_for(listing.owner)
        for bad in (0, 1000, -3):
            self.assertEqual(c.patch(f"/api/v1/listings/{listing.pk}/", {"quantity": bad}, format="json").status_code, 400, bad)
        self.assertEqual(c.patch(f"/api/v1/listings/{listing.pk}/", {"quantity": 5}, format="json").status_code, 200)
        listing.refresh_from_db()
        self.assertEqual(listing.quantity, 5)
        del seller


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class CancelOrderTests(TestCase):
    def setUp(self):
        self.listing = make_listing()
        self.buyer = make_buyer()

    def cancel(self, order, user):
        return client_for(user).post(f"/api/v1/orders/{order.pk}/cancel/")

    def test_either_side_can_cancel_before_payment(self):
        for who in ("buyer", "seller"):
            order = order_for(self.listing, self.buyer)
            r = self.cancel(order, self.buyer if who == "buyer" else self.listing.owner)
            self.assertEqual(r.status_code, 200, r.content)
            order.refresh_from_db()
            self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_a_stranger_cannot_cancel(self):
        order = order_for(self.listing, self.buyer)
        self.assertIn(self.cancel(order, make_buyer()).status_code, (403, 404))
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PENDING_PAYMENT)

    def test_cancelling_after_payment_refunds_in_full_and_restocks(self):
        order = order_for(self.listing, self.buyer)
        payment = pay(payment_for(order))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.SOLD)
        with mock.patch(PS_SERVICES) as paystack:
            r = self.cancel(order, self.buyer)
        self.assertEqual(r.status_code, 200, r.content)
        paystack.return_value.refund.assert_called_once_with(payment.reference)
        order.refresh_from_db()
        payment.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual((order.status, payment.status), (OrderStatus.REFUNDED, Payment.Status.REFUNDED))
        self.assertEqual((self.listing.quantity, self.listing.status), (1, Listing.Status.ACTIVE))

    def test_if_paystack_cannot_refund_nothing_changes(self):
        from payments.paystack import PaystackError

        order = order_for(self.listing, self.buyer)
        payment = pay(payment_for(order))
        with mock.patch(PS_SERVICES) as paystack:
            paystack.return_value.refund.side_effect = PaystackError("down")
            r = self.cancel(order, self.buyer)
        self.assertEqual(r.status_code, 502)
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual((order.status, payment.status), (OrderStatus.PAID_ESCROW, Payment.Status.PAID_HELD))

    def test_once_it_is_on_its_way_it_cannot_be_cancelled(self):
        for status in (OrderStatus.COURIER_ASSIGNED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.COMPLETED):
            order = order_for(self.listing, self.buyer, status=status)
            self.assertEqual(self.cancel(order, self.buyer).status_code, 400, status)

    def test_paying_on_a_checkout_left_open_after_cancelling_is_refunded_not_held(self):
        order = order_for(self.listing, self.buyer)
        payment = payment_for(order)
        self.cancel(order, self.buyer)
        with mock.patch(PS_SERVICES, return_value=mock.Mock()), self.captureOnCommitCallbacks(execute=True):
            pay(payment)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertIn(payment.status, (Payment.Status.REFUND_PENDING, Payment.Status.REFUNDED))
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.listing.refresh_from_db()
        self.assertEqual((self.listing.quantity, self.listing.status), (1, Listing.Status.ACTIVE), "a cancelled order never takes stock")

    def test_a_driver_who_accepted_is_told_it_is_off(self):
        from dispatch.models import Area, DeliveryOffer, DriverProfile, OrderDelivery

        order = order_for(self.listing, self.buyer)
        pay(payment_for(order))
        area = Area.objects.first()
        driver_user = make_buyer()
        driver = DriverProfile.objects.create(user=driver_user, full_name="Ada Okon", phone="08011111111", whatsapp="08011111111", vehicle_type="bike",
                                              guarantor_name="G", guarantor_phone="08022222222", status="approved")
        delivery = OrderDelivery.objects.create(order=order, pickup_area=area, dropoff_area=area, payer="buyer", fee=Decimal("500"), buyer_share=Decimal("500"),
                                                seller_share=Decimal("0"), status="accepted", driver=driver)
        DeliveryOffer.objects.create(delivery=delivery, driver=driver, status="accepted")
        with mock.patch(PS_SERVICES, return_value=mock.Mock()):
            self.cancel(order, self.buyer)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "cancelled")


class FeedTests(TestCase):
    def test_your_own_listings_and_everyone_elses_are_in_the_feed(self):
        mine = make_listing()
        other = make_listing()
        r = client_for(mine.owner).get("/api/v1/feed/")
        ids = {row["id"] for row in (r.json()["results"] if isinstance(r.json(), dict) else r.json())}
        self.assertEqual(ids, {mine.pk, other.pk})

    def test_followed_sellers_come_first(self):
        from django.contrib.contenttypes.models import ContentType

        from social.models import Follow

        reader = make_buyer()
        older = make_listing()
        Listing.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=3))
        newer = make_listing()
        Follow.objects.create(follower=reader, content_type=ContentType.objects.get_for_model(User), object_id=older.owner_id)
        r = client_for(reader).get("/api/v1/feed/")
        rows = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual([row["id"] for row in rows], [older.pk, newer.pk])

    def test_sold_and_removed_listings_are_not_in_the_feed(self):
        gone = make_listing()
        Listing.objects.filter(pk=gone.pk).update(status=Listing.Status.REMOVED)
        r = client_for(make_buyer()).get("/api/v1/feed/")
        rows = r.json()["results"] if isinstance(r.json(), dict) else r.json()
        self.assertEqual(rows, [])


class ReadMessagesTests(TestCase):
    def setUp(self):
        self.listing = make_listing()
        self.buyer = make_buyer()
        self.seller = self.listing.owner
        self.conversation = Conversation.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller)
        self.other = Conversation.objects.create(listing=make_listing(), buyer=self.buyer, seller=User.objects.create_user("s2@example.com", "pw12345!"))
        for conversation in (self.conversation, self.other):
            Message.objects.create(conversation=conversation, sender=conversation.seller, body="hello")

    def unread(self, user):
        return Notification.objects.filter(recipient=user, is_read=False, notification_type="message").count()

    def test_opening_a_conversation_clears_only_its_notifications(self):
        self.assertEqual(self.unread(self.buyer), 2)
        client_for(self.buyer).get(f"/api/v1/messages/?conversation={self.conversation.pk}")
        self.assertEqual(self.unread(self.buyer), 1, "the other conversation stays unread")
        self.assertTrue(Message.objects.get(conversation=self.conversation).read_at is not None)
        self.assertTrue(Message.objects.get(conversation=self.other).read_at is None)

    def test_your_own_messages_and_other_peoples_conversations_are_untouched(self):
        client_for(self.seller).get(f"/api/v1/messages/?conversation={self.conversation.pk}")
        self.assertEqual(Message.objects.get(conversation=self.conversation).read_at, None, "the seller wrote it; they did not read it")
        stranger = make_buyer()
        client_for(stranger).get(f"/api/v1/messages/?conversation={self.conversation.pk}")
        self.assertEqual(self.unread(self.buyer), 2)


class EditListingTests(TestCase):
    def setUp(self):
        self.listing = make_listing(price="200.00")
        self.c = client_for(self.listing.owner)

    def patch(self, **body):
        return self.c.patch(f"/api/v1/listings/{self.listing.pk}/", body, format="json")

    def test_a_price_change_can_be_shown_to_buyers_or_hidden(self):
        r = self.patch(price="2500.00", show_price_change=True)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["price"], r.json()["previous_price"]), ("2500.00", "200.00"))
        r = self.patch(price="3000.00", show_price_change=False)
        self.assertEqual((r.json()["price"], r.json()["previous_price"]), ("3000.00", None))

    def test_a_listing_with_no_price_change_keeps_what_it_had(self):
        self.patch(price="2500.00", show_price_change=True)
        r = self.patch(description="Now with a free strap")
        self.assertEqual(r.json()["previous_price"], "200.00")

    def test_only_the_owner_can_edit(self):
        r = client_for(make_buyer()).patch(f"/api/v1/listings/{self.listing.pk}/", {"price": "1.00"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_restocking_a_sold_out_listing_puts_it_back_on_sale(self):
        Listing.objects.filter(pk=self.listing.pk).update(status=Listing.Status.SOLD, quantity=0)
        r = self.patch(quantity=4)
        self.assertEqual((r.json()["status"], r.json()["quantity"]), ("active", 4))

    def test_the_list_shows_the_old_price_too(self):
        self.patch(price="2500.00", show_price_change=True)
        rows = APIListing(self).rows()
        self.assertEqual(rows[0]["previous_price"], "200.00")


class APIListing:
    def __init__(self, case):
        self.case = case

    def rows(self):
        data = client_for(self.case.listing.owner).get("/api/v1/listings/").json()
        return data["results"] if isinstance(data, dict) else data


@override_settings(PAYSTACK_SECRET_KEY=SECRET, CHOROPIA_SITE_URL="https://choropia.test", PAYMENT_PROVIDER="paystack")
class ReturnToAppTests(TestCase):
    def setUp(self):
        self.listing = make_listing()
        self.buyer = make_buyer()
        self.order = order_for(self.listing, self.buyer)

    def start(self, **body):
        client = mock.MagicMock()
        client.initialize_transaction.return_value = {"authorization_url": "https://checkout.paystack.com/x"}
        with mock.patch("payments.services._paystack", return_value=client):
            r = client_for(self.buyer).post("/api/v1/payments/initialize/", {"order_id": self.order.pk, **body}, format="json")
        return r, client

    def test_the_app_is_sent_back_to_a_page_that_opens_the_app(self):
        r, client = self.start(source="app")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(client.initialize_transaction.call_args.kwargs["callback_url"], f"https://choropia.test/pay/return/{self.order.public_id}/")

    def test_the_website_still_returns_to_the_order_page(self):
        _, client = self.start()
        self.assertEqual(client.initialize_transaction.call_args.kwargs["callback_url"], f"https://choropia.test/order/{self.order.public_id}")

    def test_switching_from_website_to_app_starts_a_fresh_checkout_that_returns_to_the_app(self):
        first, _ = self.start()
        _, client = self.start(source="app")
        self.assertEqual(client.initialize_transaction.call_args.kwargs["callback_url"], f"https://choropia.test/pay/return/{self.order.public_id}/")
        self.assertNotEqual(first.json()["reference"], Payment.objects.get(order=self.order).reference)

    def test_the_return_page_confirms_the_payment_and_offers_the_app(self):
        self.start(source="app")
        payment = Payment.objects.get(order=self.order)
        verify = mock.Mock(return_value=charge(payment.reference, amount_kobo=int(Decimal(payment.amount) * 100)))
        with mock.patch("payments.services._paystack") as paystack:
            paystack.return_value.verify_transaction = verify
            page = self.client.get(f"/pay/return/{self.order.public_id}/?reference={payment.reference}")
        self.assertContains(page, "Payment received")
        self.assertContains(page, f"intent://order/{self.order.pk}#Intent;scheme=choropia")
        self.assertContains(page, "package=com.choropia.app")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID_ESCROW)

    def test_the_return_page_is_safe_for_anyone_and_shows_nothing_private(self):
        page = self.client.get(f"/pay/return/{self.order.pk}/")
        self.assertContains(page, "confirming your payment")
        self.assertNotContains(page, self.buyer.email)
        self.assertEqual(self.client.get("/pay/return/999999/").status_code, 200)

"""Dispatch: driver verification (encrypted documents), pricing, first-to-accept, the handover code, and payouts.
Paystack is never contacted: payouts are switched off (the payout rows are still created and checked)."""
import io
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from legal.models import Acceptance
from listings.models import Category, Listing
from orders.models import Order
from orders.state_machine import OrderStatus
from payments import services as pay_services
from payments.models import Payment, Payout, PayoutAccount
from payments.tests.test_paystack import charge

from . import crypto, services
from .models import Area, DeliveryOffer, DocumentAccessLog, DriverDocument, DriverProfile, DriverRoute, ListingDelivery, OrderDelivery

User = get_user_model()
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def upload(data, name="x.jpg"):
    f = io.BytesIO(data)
    f.name = name
    return f


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def make_user(label, **extra):
    return User.objects.create_user(f"{label}@example.com", "pw12345!", first_name=label.title(), **extra)


def make_driver(label, status=DriverProfile.Status.APPROVED, **extra):
    user = make_user(label, phone_number=f"0801{abs(hash(label)) % 10**7:07d}")
    return DriverProfile.objects.create(
        user=user, full_name=f"{label.title()} Okon", phone="08012345678", whatsapp="08012345678", vehicle_type="bike",
        guarantor_name="Mr Guarantor", guarantor_phone="08099999999", status=status, **extra,
    )


def route(driver, a, b, price):
    return DriverRoute.objects.create(driver=driver, from_area=a, to_area=b, price=Decimal(price))


@override_settings(PAYOUTS_ENABLED=False, PAYMENT_PROVIDER="paystack")
class DispatchBase(TestCase):
    def setUp(self):
        self.ewet = Area.objects.get(name="Ewet Housing")
        self.aka = Area.objects.get(name="Aka Road")
        self.seller = make_user("seller", phone_number="08031111111")
        self.buyer = make_user("buyer", phone_number="08032222222")
        cat = Category.objects.get_or_create(name="Electronics")[0]
        self.listing = Listing.objects.create(owner=self.seller, category=cat, title="Laptop", price="20000.00")
        self.d1, self.d2 = make_driver("ada"), make_driver("bayo")
        route(self.d1, self.ewet, self.aka, "1000")
        route(self.d2, self.ewet, self.aka, "800")  # cheaper than d1
        self.options = services.set_listing_delivery(self.listing, self.seller, True, "split", self.ewet, [self.d1.pk, self.d2.pk])

    def new_order(self):
        return Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=self.listing.price)

    def chosen(self, driver=None):
        order = self.new_order()
        delivery = services.choose_delivery(order, self.buyer, self.aka, driver or self.d1, "Block 3, Aka Road")
        return order, delivery

    def pay(self, order):
        from payments.services import initialize_payment

        client = mock.MagicMock()
        client.initialize_transaction.return_value = {"authorization_url": "https://checkout.paystack.com/x"}
        with mock.patch("payments.services._paystack", return_value=client):
            payment = initialize_payment(order)
        data = charge(payment.reference, amount_kobo=int(Decimal(payment.amount) * 100))
        pay_services.confirm_paystack_payment(payment.reference, data)
        order.refresh_from_db()
        return Payment.objects.get(pk=payment.pk)

    def paid_and_accepted(self, driver=None):
        order, delivery = self.chosen(driver)
        self.pay(order)
        delivery.refresh_from_db()
        services.accept_job(delivery.pk, (driver or self.d1).user)
        delivery.refresh_from_db()
        return order, delivery


class EncryptionTests(TestCase):
    def test_roundtrip_and_nothing_readable_is_stored(self):
        token = crypto.encrypt(b"PASSPORT-1234")
        self.assertNotIn(b"PASSPORT", token)
        self.assertEqual(crypto.decrypt(token), b"PASSPORT-1234")

    @override_settings(DOCUMENT_ENCRYPTION_KEYS="")
    def test_refuses_to_store_without_a_key(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            crypto.encrypt(b"x")

    def test_a_tampered_document_does_not_decrypt(self):
        token = bytearray(crypto.encrypt(b"abc"))
        token[-3] ^= 1
        with self.assertRaises(crypto.DocumentDecryptionError):
            crypto.decrypt(bytes(token))

    def test_old_keys_still_decrypt_after_rotation(self):
        from cryptography.fernet import Fernet

        old = Fernet.generate_key().decode()
        with override_settings(DOCUMENT_ENCRYPTION_KEYS=old):
            token = crypto.encrypt(b"id")
        with override_settings(DOCUMENT_ENCRYPTION_KEYS=f"{Fernet.generate_key().decode()},{old}"):
            self.assertEqual(crypto.decrypt(token), b"id")


class DriverApplicationTests(TestCase):
    def setUp(self):
        self.user = make_user("newdriver")
        self.client = client_for(self.user)
        self.body = {
            "full_name": "Emem Udo", "phone": "08012345678", "whatsapp": "08012345678", "vehicle_type": "bike",
            "plate_number": "uyo 123 ab", "guarantor_name": "Mr Etim", "guarantor_phone": "08055555555", "accept_terms": True,
        }

    def test_must_accept_the_terms(self):
        r = self.client.put("/api/v1/dispatch/driver/me/", {**self.body, "accept_terms": False}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "terms_required")

    def test_apply_records_acceptance_and_waits_for_review(self):
        r = self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "pending")
        self.assertFalse(r.json()["documents_complete"])
        self.assertEqual(set(Acceptance.objects.filter(user=self.user).values_list("document", flat=True)), {"driver_terms", "privacy"})

    def test_bad_phone_is_rejected(self):
        r = self.client.put("/api/v1/dispatch/driver/me/", {**self.body, "phone": "abc"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_documents_are_stored_encrypted_and_never_served_back(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        r = self.client.post("/api/v1/dispatch/driver/documents/", {"kind": "id_card", "file": upload(JPEG)}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        doc = DriverDocument.objects.get()
        self.assertNotIn(b"\xff\xd8\xff", bytes(doc.encrypted_data))
        self.assertEqual(crypto.decrypt(doc.encrypted_data), JPEG)
        self.assertNotIn("encrypted", r.content.decode())
        self.assertEqual(self.client.get("/api/v1/dispatch/driver/documents/").status_code, 200)

    def test_rejects_files_that_are_not_images_or_pdfs(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        r = self.client.post("/api/v1/dispatch/driver/documents/", {"kind": "id_card", "file": upload(b"MZ\x90\x00 evil", "id.jpg")}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_passport_photo_must_be_an_image(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        r = self.client.post("/api/v1/dispatch/driver/documents/", {"kind": "passport_photo", "file": upload(b"%PDF-1.4 x", "p.pdf")}, format="multipart")
        self.assertEqual(r.status_code, 400)

    @override_settings(DOCUMENT_MAX_BYTES=100)
    def test_too_large_is_rejected(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        r = self.client.post("/api/v1/dispatch/driver/documents/", {"kind": "id_card", "file": upload(JPEG)}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_unapproved_driver_cannot_publish_prices_or_take_jobs(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        a, b = Area.objects.all()[:2]
        self.assertEqual(self.client.post("/api/v1/dispatch/driver/routes/", {"from_area": a.id, "to_area": b.id, "price": 500}, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/dispatch/driver/jobs/").status_code, 403)

    def test_admin_approval_needs_all_four_documents_and_opening_one_is_logged(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        from .admin import DriverProfileAdmin

        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        profile = DriverProfile.objects.get(user=self.user)
        staff = User.objects.create_superuser("boss@example.com", "pw12345!")
        admin = DriverProfileAdmin(DriverProfile, site)
        request = RequestFactory().post("/")
        request.user = staff
        request._messages = mock.MagicMock()

        admin.approve(request, DriverProfile.objects.filter(pk=profile.pk))
        profile.refresh_from_db()
        self.assertEqual(profile.status, "pending", "approval must be refused with missing documents")

        for kind in DriverDocument.REQUIRED:
            self.client.post("/api/v1/dispatch/driver/documents/", {"kind": kind.value, "file": upload(PNG if kind.value == "passport_photo" else JPEG)}, format="multipart")
        with self.captureOnCommitCallbacks(execute=True):
            admin.approve(request, DriverProfile.objects.filter(pk=profile.pk))
        profile.refresh_from_db()
        self.assertEqual(profile.status, "approved")
        self.assertEqual(profile.reviewed_by, staff)
        self.assertTrue(any("approved" in m.subject.lower() for m in mail.outbox))

        doc = profile.documents.first()
        c = APIClient()
        c.force_login(staff)
        r = c.get(f"/admin/dispatch/driverprofile/document/{doc.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-store", r["Cache-Control"])
        self.assertEqual(DocumentAccessLog.objects.filter(document=doc, staff=staff).count(), 1)

    def test_a_non_staff_user_cannot_open_documents(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        self.client.post("/api/v1/dispatch/driver/documents/", {"kind": "id_card", "file": upload(JPEG)}, format="multipart")
        doc = DriverDocument.objects.get()
        c = APIClient()
        c.force_login(self.user)
        self.assertIn(c.get(f"/admin/dispatch/driverprofile/document/{doc.pk}/").status_code, (302, 403, 404))
        self.assertEqual(DocumentAccessLog.objects.count(), 0)

    def test_replacing_an_id_after_approval_sends_the_driver_back_to_review(self):
        self.client.put("/api/v1/dispatch/driver/me/", self.body, format="json")
        DriverProfile.objects.update(status="approved")
        self.client.post("/api/v1/dispatch/driver/documents/", {"kind": "id_card", "file": upload(JPEG)}, format="multipart")
        self.assertEqual(DriverProfile.objects.get().status, "pending")


class AreaAndRouteTests(TestCase):
    def test_uyo_areas_are_seeded_and_users_can_add_more_without_duplicates(self):
        self.assertGreater(Area.objects.count(), 20)
        c = client_for(make_user("someone"))
        r = c.post("/api/v1/dispatch/areas/", {"name": "  Ikot   Ishie "}, format="json")
        self.assertEqual(r.status_code, 201)
        again = c.post("/api/v1/dispatch/areas/", {"name": "ikot ishie"}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["id"], r.json()["id"])
        self.assertEqual(APIClient().get("/api/v1/dispatch/areas/").status_code, 200)
        self.assertEqual(c.post("/api/v1/dispatch/areas/", {"name": "x"}, format="json").status_code, 400)

    def test_driver_publishes_and_removes_a_route(self):
        driver = make_driver("pricey")
        c = client_for(driver.user)
        a, b = Area.objects.all()[:2]
        r = c.post("/api/v1/dispatch/driver/routes/", {"from_area": a.id, "to_area": b.id, "price": "1500"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post("/api/v1/dispatch/driver/routes/", {"from_area": a.id, "to_area": a.id, "price": "1500"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/v1/dispatch/driver/routes/", {"from_area": a.id, "to_area": b.id, "price": "5"}, format="json").status_code, 400)
        self.assertEqual(c.delete(f"/api/v1/dispatch/driver/routes/{DriverRoute.objects.get().pk}/").status_code, 204)
        self.assertFalse(DriverRoute.objects.get().is_active)

    def test_browse_shows_prices_but_never_phone_numbers(self):
        driver = make_driver("shown")
        a, b = Area.objects.all()[:2]
        route(driver, a, b, "700")
        body = client_for(make_user("seller2")).get(f"/api/v1/dispatch/drivers/?from={a.id}&to={b.id}").content.decode()
        self.assertIn("700", body)
        self.assertNotIn("08012345678", body)
        self.assertNotIn("@example.com", body)


class FeeSplitTests(TestCase):
    def test_split_is_exactly_fifty_fifty(self):
        self.assertEqual(services.split_fee("1000", "split"), (Decimal("500.00"), Decimal("500.00")))
        buyer, seller = services.split_fee("1001.01", "split")
        self.assertEqual(buyer + seller, Decimal("1001.01"))
        self.assertEqual(services.split_fee("1000", "buyer"), (Decimal("1000.00"), Decimal("0.00")))
        self.assertEqual(services.split_fee("1000", "seller"), (Decimal("0.00"), Decimal("1000.00")))

    def test_driver_gets_the_fee_less_two_and_a_half_percent(self):
        self.assertEqual(services.driver_net("1000"), Decimal("975.00"))


class SellerSetupTests(DispatchBase):
    def test_only_the_owner_can_set_delivery(self):
        with self.assertRaises(services.DispatchError):
            services.set_listing_delivery(self.listing, self.buyer, True, "buyer", self.ewet, [self.d1.pk])

    def test_enabling_needs_at_least_one_approved_driver_who_serves_the_pickup_area(self):
        with self.assertRaises(services.DispatchError):
            services.set_listing_delivery(self.listing, self.seller, True, "buyer", self.ewet, [])
        pending = make_driver("pend", status="pending")
        route(pending, self.ewet, self.aka, "500")
        with self.assertRaises(services.DispatchError):
            services.set_listing_delivery(self.listing, self.seller, True, "buyer", self.ewet, [pending.pk])
        elsewhere = make_driver("far")
        route(elsewhere, self.aka, self.ewet, "500")
        with self.assertRaises(services.DispatchError):
            services.set_listing_delivery(self.listing, self.seller, True, "buyer", self.ewet, [elsewhere.pk])

    def test_buyer_sees_chosen_drivers_and_exact_prices_but_no_contacts(self):
        r = APIClient().get(f"/api/v1/dispatch/listings/{self.listing.pk}/delivery/?to={self.aka.pk}")
        body = r.json()
        self.assertTrue(body["enabled"])
        self.assertEqual(body["payer"], "split")
        prices = sorted(rt["price"] for d in body["drivers"] for rt in d["routes"])
        self.assertEqual(prices, ["1000.00", "800.00"])
        self.assertEqual(sorted(rt["you_pay"] for d in body["drivers"] for rt in d["routes"]), ["400.00", "500.00"])
        for secret in ("08012345678", "08031111111", "@example.com"):
            self.assertNotIn(secret, r.content.decode())

    def test_delivery_is_optional(self):
        other = Listing.objects.create(owner=self.seller, category=self.listing.category, title="Chair", price="5000.00")
        self.assertEqual(APIClient().get(f"/api/v1/dispatch/listings/{other.pk}/delivery/").json(), {"enabled": False})
        order = Order.objects.create(listing=other, buyer=self.buyer, seller=self.seller, price=other.price)
        with self.assertRaises(services.DispatchError):
            services.choose_delivery(order, self.buyer, self.aka, self.d1)

    def test_seller_endpoint_end_to_end(self):
        c = client_for(self.seller)
        r = c.put(f"/api/v1/dispatch/listings/{self.listing.pk}/delivery/",
                  {"enabled": True, "payer": "seller", "pickup_area": self.ewet.pk, "drivers": [self.d1.pk]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["payer"], "seller")
        self.assertEqual(len(r.json()["drivers"]), 1)
        self.assertEqual(client_for(self.buyer).put(f"/api/v1/dispatch/listings/{self.listing.pk}/delivery/",
                         {"enabled": True, "payer": "buyer", "pickup_area": self.ewet.pk, "drivers": [self.d1.pk]}, format="json").status_code, 403)


class CheckoutTests(DispatchBase):
    def test_total_is_item_price_plus_buyers_half_and_fee_is_locked(self):
        order, delivery = self.chosen(self.d1)
        self.assertEqual((delivery.fee, delivery.buyer_share, delivery.seller_share), (Decimal("1000.00"), Decimal("500.00"), Decimal("500.00")))
        payment = self.pay(order)
        self.assertEqual(payment.amount, Decimal("20500.00"))
        self.assertEqual(payment.status, Payment.Status.PAID_HELD)

    def test_changing_the_choice_reissues_the_unpaid_checkout(self):
        order, _ = self.chosen(self.d1)
        client = mock.MagicMock()
        client.initialize_transaction.return_value = {"authorization_url": "https://checkout.paystack.com/x"}
        from payments.services import initialize_payment

        with mock.patch("payments.services._paystack", return_value=client):
            first = initialize_payment(order)
        old_ref = first.reference
        services.choose_delivery(order, self.buyer, self.aka, self.d2)
        first.refresh_from_db()
        self.assertEqual(first.amount, Decimal("20400.00"))
        self.assertNotEqual(first.reference, old_ref)
        self.assertEqual(first.authorization_url, "")

    def test_dropping_delivery_before_paying_returns_the_price_to_the_item_price(self):
        order, _ = self.chosen(self.d1)
        from payments.services import initialize_payment

        client = mock.MagicMock()
        client.initialize_transaction.return_value = {"authorization_url": "https://checkout.paystack.com/x"}
        with mock.patch("payments.services._paystack", return_value=client):
            initialize_payment(order)
        services.clear_delivery(order, self.buyer)
        self.assertEqual(Payment.objects.get(order=order).amount, Decimal("20000.00"))
        self.assertFalse(OrderDelivery.objects.exists())

    def test_cannot_choose_a_driver_who_is_not_the_sellers_or_after_paying(self):
        stranger = make_driver("stranger")
        route(stranger, self.ewet, self.aka, "100")
        order = self.new_order()
        with self.assertRaises(services.DispatchError):
            services.choose_delivery(order, self.buyer, self.aka, stranger)
        order2, _ = self.chosen(self.d1)
        self.pay(order2)
        with self.assertRaises(services.DispatchError):
            services.choose_delivery(order2, self.buyer, self.aka, self.d1)

    def test_only_the_buyer_chooses(self):
        with self.assertRaises(services.DispatchError):
            services.choose_delivery(self.new_order(), self.seller, self.aka, self.d1)

    def test_a_fee_the_seller_could_never_cover_is_refused(self):
        cheap = Listing.objects.create(owner=self.seller, category=self.listing.category, title="Pen", price="300.00")
        ListingDelivery.objects.create(listing=cheap, enabled=True, payer="seller", pickup_area=self.ewet).drivers.set([self.d1])
        order = Order.objects.create(listing=cheap, buyer=self.buyer, seller=self.seller, price=cheap.price)
        with self.assertRaises(services.DispatchError):
            services.choose_delivery(order, self.buyer, self.aka, self.d1)


class OfferTests(DispatchBase):
    def test_nothing_happens_until_the_payment_lands(self):
        order, delivery = self.chosen()
        self.assertEqual(delivery.status, "awaiting_payment")
        self.assertEqual(DeliveryOffer.objects.count(), 0)
        self.assertEqual(delivery.handover_code, "")

    def test_every_selected_driver_is_alerted_and_the_buyer_gets_a_six_digit_code(self):
        order, delivery = self.chosen(self.d1)
        with self.captureOnCommitCallbacks(execute=True):
            self.pay(order)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "offered")
        self.assertRegex(delivery.handover_code, r"^\d{6}$")
        self.assertEqual(set(DeliveryOffer.objects.values_list("driver_id", flat=True)), {self.d1.pk, self.d2.pk})
        self.assertTrue(any("New delivery job" in m.subject for m in mail.outbox))

    def test_drivers_dearer_than_the_locked_fee_are_not_alerted(self):
        dear = make_driver("dear")
        route(dear, self.ewet, self.aka, "5000")
        self.options.drivers.add(dear)
        order, _ = self.chosen(self.d1)
        self.pay(order)
        self.assertFalse(DeliveryOffer.objects.filter(driver=dear).exists())

    def test_offline_and_suspended_drivers_are_not_alerted(self):
        DriverProfile.objects.filter(pk=self.d2.pk).update(available=False)
        order, _ = self.chosen(self.d1)
        self.pay(order)
        self.assertEqual(list(DeliveryOffer.objects.values_list("driver_id", flat=True)), [self.d1.pk])

    def test_a_job_alert_has_no_address_or_contacts(self):
        order, delivery = self.chosen(self.d1)
        self.pay(order)
        body = client_for(self.d1.user).get("/api/v1/dispatch/driver/jobs/").content.decode()
        self.assertIn("Aka Road", body)  # the area, yes
        for secret in ("Block 3", "08031111111", "08032222222", "seller@example.com", "buyer@example.com"):
            self.assertNotIn(secret, body)

    def test_seller_with_no_available_driver_is_told_to_add_one(self):
        DriverProfile.objects.update(available=False)
        mail.outbox.clear()
        order, _ = self.chosen(self.d1)
        with self.captureOnCommitCallbacks(execute=True):
            self.pay(order)
        self.assertTrue(any("add a driver" in m.subject.lower() for m in mail.outbox))


class FirstToAcceptTests(DispatchBase):
    def test_first_driver_wins_and_the_other_sees_already_accepted(self):
        order, delivery = self.chosen(self.d1)
        self.pay(order)
        r1 = client_for(self.d2.user).post(f"/api/v1/dispatch/driver/jobs/{delivery.pk}/accept/")
        self.assertEqual(r1.status_code, 200, r1.content)
        r2 = client_for(self.d1.user).post(f"/api/v1/dispatch/driver/jobs/{delivery.pk}/accept/")
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()["code"], "already_accepted")
        delivery.refresh_from_db()
        self.assertEqual(delivery.driver, self.d2)
        self.assertEqual(DeliveryOffer.objects.get(driver=self.d1).status, "taken")
        jobs = client_for(self.d1.user).get("/api/v1/dispatch/driver/jobs/").json()
        self.assertEqual(jobs["open"][0]["state"], "already_accepted")

    def test_a_driver_who_was_never_offered_cannot_accept(self):
        order, delivery = self.chosen(self.d1)
        self.pay(order)
        outsider = make_driver("outsider")
        self.assertEqual(client_for(outsider.user).post(f"/api/v1/dispatch/driver/jobs/{delivery.pk}/accept/").status_code, 404)

    def test_buyer_and_seller_learn_who_is_coming_only_after_acceptance(self):
        order, delivery = self.chosen(self.d1)
        self.pay(order)
        before = client_for(self.buyer).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/").json()
        self.assertIsNone(before["driver"])
        services.accept_job(delivery.pk, self.d1.user)
        after = client_for(self.buyer).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/").json()
        self.assertEqual(after["driver"]["phone"], "08012345678")
        self.assertRegex(after["handover_code"], r"^\d{6}$")
        seller_view = client_for(self.seller).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/").json()
        self.assertNotIn("handover_code", seller_view)  # only the buyer holds the code

    def test_only_the_assigned_driver_sees_buyer_contact_and_address(self):
        order, delivery = self.paid_and_accepted(self.d1)
        mine = client_for(self.d1.user).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/").json()
        self.assertEqual(mine["dropoff"]["note"], "Block 3, Aka Road")
        self.assertEqual(mine["dropoff"]["phone"], "08032222222")
        self.assertEqual(client_for(self.d2.user).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/").status_code, 404)
        self.assertNotIn("handover_code", mine)

    def test_decline_hides_the_job(self):
        order, delivery = self.chosen(self.d1)
        self.pay(order)
        self.assertEqual(client_for(self.d1.user).post(f"/api/v1/dispatch/driver/jobs/{delivery.pk}/decline/").status_code, 200)
        self.assertEqual(client_for(self.d1.user).get("/api/v1/dispatch/driver/jobs/").json()["open"], [])


class ReassignTests(DispatchBase):
    def test_seller_can_take_the_job_back_and_give_it_to_another_driver(self):
        order, delivery = self.paid_and_accepted(self.d1)
        r = client_for(self.seller).post(f"/api/v1/dispatch/orders/{order.pk}/delivery/reassign/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        delivery.refresh_from_db()
        self.assertIsNone(delivery.driver)
        self.assertEqual(delivery.status, "offered")
        self.assertEqual(DeliveryOffer.objects.get(driver=self.d1).status, "withdrawn")
        self.assertEqual(DeliveryOffer.objects.get(driver=self.d2).status, "pending")
        self.assertEqual(client_for(self.d1.user).post(f"/api/v1/dispatch/driver/jobs/{delivery.pk}/accept/").status_code, 404)
        self.assertEqual(client_for(self.d2.user).post(f"/api/v1/dispatch/driver/jobs/{delivery.pk}/accept/").status_code, 200)

    def test_seller_can_add_a_new_driver_while_reassigning(self):
        order, delivery = self.paid_and_accepted(self.d1)
        newbie = make_driver("newbie")
        route(newbie, self.ewet, self.aka, "900")
        client_for(self.seller).post(f"/api/v1/dispatch/orders/{order.pk}/delivery/reassign/", {"add_drivers": [newbie.pk]}, format="json")
        self.assertTrue(DeliveryOffer.objects.filter(driver=newbie, status="pending").exists())

    def test_nobody_else_can_reassign_and_it_is_too_late_after_pickup(self):
        order, delivery = self.paid_and_accepted(self.d1)
        self.assertEqual(client_for(self.buyer).post(f"/api/v1/dispatch/orders/{order.pk}/delivery/reassign/", {}, format="json").status_code, 403)
        services.mark_picked_up(delivery.pk, self.d1.user)
        self.assertEqual(client_for(self.seller).post(f"/api/v1/dispatch/orders/{order.pk}/delivery/reassign/", {}, format="json").status_code, 400)


class DeliveryAndPayoutTests(DispatchBase):
    def go_to_pickup(self):
        order, delivery = self.paid_and_accepted(self.d1)
        services.mark_picked_up(delivery.pk, self.d1.user)
        order.refresh_from_db()
        delivery.refresh_from_db()
        return order, delivery

    def test_pickup_moves_the_order_to_in_transit(self):
        order, _ = self.go_to_pickup()
        self.assertEqual(order.status, OrderStatus.IN_TRANSIT)

    def test_only_the_assigned_driver_can_pick_up(self):
        order, delivery = self.paid_and_accepted(self.d1)
        with self.assertRaises(services.DispatchError):
            services.mark_picked_up(delivery.pk, self.d2.user)

    def test_wrong_code_is_counted_and_locks_after_the_limit(self):
        _, delivery = self.go_to_pickup()
        for _ in range(5):
            with self.assertRaises(services.DispatchError) as ctx:
                services.complete_delivery(delivery.pk, self.d1.user, "000000" if delivery.handover_code != "000000" else "111111", JPEG, "image/jpeg")
            self.assertEqual(ctx.exception.code, "wrong_code")
        delivery.refresh_from_db()
        self.assertEqual(delivery.code_attempts, 5, "failed attempts must be remembered")
        with self.assertRaises(services.DispatchError) as ctx:
            services.complete_delivery(delivery.pk, self.d1.user, delivery.handover_code, JPEG, "image/jpeg")
        self.assertEqual(ctx.exception.code, "code_locked")

    def test_a_photo_is_required(self):
        _, delivery = self.go_to_pickup()
        with self.assertRaises(services.DispatchError):
            services.complete_delivery(delivery.pk, self.d1.user, delivery.handover_code, b"", "image/jpeg")

    def test_right_code_and_photo_completes_the_order_and_pays_everyone_correctly(self):
        order, delivery = self.go_to_pickup()
        seller_bank = PayoutAccount.objects.create(user=self.seller, bank_code="058", bank_name="GTBank", account_last4="1234", account_name="S", recipient_code="RCP_s")
        driver_bank = PayoutAccount.objects.create(user=self.d1.user, bank_code="058", bank_name="GTBank", account_last4="9999", account_name="D", recipient_code="RCP_d")
        r = client_for(self.d1.user).post(
            f"/api/v1/dispatch/driver/jobs/{delivery.pk}/deliver/",
            {"code": delivery.handover_code, "photo": upload(JPEG)}, format="multipart",
        )
        self.assertEqual(r.status_code, 200, r.content)
        order.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(delivery.status, "delivered")
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, Payment.Status.RELEASED)

        # buyer paid 20,000 + 500. The seller: 20,000 less 5% commission (1,000) less their 500 half of delivery.
        seller_payout = payment.payout
        self.assertEqual((seller_payout.gross_amount, seller_payout.commission_amount, seller_payout.delivery_deduction, seller_payout.net_amount),
                         (Decimal("20000.00"), Decimal("1000.00"), Decimal("500.00"), Decimal("18500.00")))
        # The driver: the whole 1,000 fee less 2.5% (25).
        driver_payout = payment.driver_payout
        self.assertEqual((driver_payout.gross_amount, driver_payout.commission_amount, driver_payout.net_amount),
                         (Decimal("1000.00"), Decimal("25.00"), Decimal("975.00")))
        self.assertEqual(driver_payout.seller, self.d1.user)
        # Every naira is accounted for: buyer's money = seller + driver + Choropia's two commissions.
        total_out = seller_payout.net_amount + driver_payout.net_amount + seller_payout.commission_amount + driver_payout.commission_amount
        self.assertEqual(total_out, payment.amount)

    def test_the_proof_photo_is_only_for_the_two_parties(self):
        order, delivery = self.go_to_pickup()
        services.complete_delivery(delivery.pk, self.d1.user, delivery.handover_code, JPEG, "image/jpeg")
        self.assertEqual(client_for(self.buyer).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/proof/").status_code, 200)
        self.assertEqual(client_for(make_user("nosy")).get(f"/api/v1/dispatch/orders/{order.pk}/delivery/proof/").status_code, 404)

    def test_buyer_who_disputes_blocks_the_driver_from_releasing_the_money(self):
        order, delivery = self.go_to_pickup()
        order.transition_to(OrderStatus.DISPUTED, actor=self.buyer, note="never came")
        with self.assertRaises(services.DispatchError) as ctx:
            services.complete_delivery(delivery.pk, self.d1.user, delivery.handover_code, JPEG, "image/jpeg")
        self.assertEqual(ctx.exception.code, "disputed")
        self.assertNotEqual(Payment.objects.get(order=order).status, Payment.Status.RELEASED)

    def test_seller_pays_all_when_chosen_and_buyer_pays_all_when_chosen(self):
        self.options.payer = "seller"
        self.options.save()
        order, delivery = self.chosen(self.d1)
        payment = self.pay(order)
        self.assertEqual(payment.amount, Decimal("20000.00"))
        services.accept_job(delivery.pk, self.d1.user)
        services.mark_picked_up(delivery.pk, self.d1.user)
        delivery.refresh_from_db()
        services.complete_delivery(delivery.pk, self.d1.user, delivery.handover_code, JPEG, "image/jpeg")
        payment.refresh_from_db()
        self.assertEqual(payment.payout.net_amount, Decimal("18000.00"))  # 20,000 - 1,000 commission - 1,000 delivery
        self.assertEqual(payment.driver_payout.net_amount, Decimal("975.00"))

    def test_a_driver_payout_waits_for_a_bank_account(self):
        order, delivery = self.go_to_pickup()
        services.complete_delivery(delivery.pk, self.d1.user, delivery.handover_code, JPEG, "image/jpeg")
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.driver_payout.status, Payout.Status.AWAITING_ACCOUNT)

    def test_non_delivery_orders_are_unchanged(self):
        plain = Listing.objects.create(owner=self.seller, category=self.listing.category, title="Book", price="2000.00")
        order = Order.objects.create(listing=plain, buyer=self.buyer, seller=self.seller, price=plain.price)
        payment = self.pay(order)
        self.assertEqual(payment.amount, Decimal("2000.00"))
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PAID_ESCROW)
        pay_services.release_escrow(order)
        self.assertIsNone(Payment.objects.get(order=order).driver_payout)
        self.assertEqual(Payment.objects.get(order=order).payout.delivery_deduction, Decimal("0"))


class OrderFlowGuardTests(DispatchBase):
    def test_buyer_cannot_confirm_while_no_driver_has_taken_the_job(self):
        order, _ = self.chosen(self.d1)
        self.pay(order)
        r = client_for(self.buyer).post(f"/api/v1/orders/{order.pk}/confirm_receipt/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("driver", r.content.decode().lower())

    def test_buyer_can_confirm_once_a_driver_is_assigned(self):
        order, _ = self.paid_and_accepted(self.d1)
        self.assertEqual(client_for(self.buyer).post(f"/api/v1/orders/{order.pk}/confirm_receipt/").status_code, 200)
        payment = Payment.objects.get(order=order)
        self.assertIsNotNone(payment.driver_payout)

    def test_an_order_nobody_delivers_is_refunded_in_full_and_the_jobs_vanish(self):
        from datetime import timedelta

        from payments.tasks import auto_refund_undispatched_task

        order, delivery = self.chosen(self.d1)
        payment = self.pay(order)
        Payment.objects.filter(pk=payment.pk).update(paid_at=timezone.now() - timedelta(days=8))
        client = mock.MagicMock()
        with mock.patch("payments.services._paystack", return_value=client):
            result = auto_refund_undispatched_task()
        self.assertEqual(result["refunded"], [order.pk])
        client.refund.assert_called_once_with(payment.reference)  # the whole payment, delivery fee included
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "cancelled")
        self.assertEqual(set(DeliveryOffer.objects.values_list("status", flat=True)), {"withdrawn"})

    def test_a_driver_on_the_job_stops_the_seven_day_auto_refund(self):
        from datetime import timedelta

        from payments.tasks import auto_refund_undispatched_task

        order, delivery = self.paid_and_accepted(self.d1)
        Payment.objects.filter(order=order).update(paid_at=timezone.now() - timedelta(days=8))
        with mock.patch("payments.services._paystack", return_value=mock.MagicMock()):
            self.assertEqual(auto_refund_undispatched_task()["refunded"], [])


class NudgeTests(DispatchBase):
    def test_seller_is_nudged_once_after_two_hours_without_a_taker(self):
        order, delivery = self.chosen(self.d1)
        self.pay(order)
        self.assertEqual(services.nudge_stale_offers(), [])
        later = timezone.now() + timezone.timedelta(hours=2, minutes=1)
        self.assertEqual(services.nudge_stale_offers(now=later), [delivery.pk])
        self.assertEqual(services.nudge_stale_offers(now=later), [])

    def test_no_nudge_when_a_driver_already_accepted(self):
        order, delivery = self.paid_and_accepted(self.d1)
        later = timezone.now() + timezone.timedelta(hours=5)
        self.assertEqual(services.nudge_stale_offers(now=later), [])


class LegalTests(TestCase):
    def test_pages_render_without_placeholders_or_template_errors(self):
        c = APIClient()
        for slug in ("terms", "privacy", "driver_terms"):
            html = c.get(f"/legal/{slug}/")
            self.assertEqual(html.status_code, 200, slug)
            text = html.content.decode()
            self.assertNotIn("{{", text)
            self.assertNotIn("{%", text)
            api = c.get(f"/api/v1/legal/{slug}/").json()
            self.assertEqual(api["slug"], slug)
        self.assertEqual(c.get("/legal/nope/").status_code, 404)

    def test_terms_state_the_real_fees(self):
        text = APIClient().get("/legal/terms/").content.decode()
        self.assertIn("6% for items under 10,000 naira", text)
        self.assertIn("2.5%", APIClient().get("/legal/driver_terms/").content.decode())

    def test_acceptance_is_recorded_once_per_version(self):
        user = make_user("signer")
        c = client_for(user)
        self.assertFalse(c.get("/api/v1/legal/accept/").json()["accepted"]["terms"])
        c.post("/api/v1/legal/accept/", {"documents": ["terms", "privacy"]}, format="json")
        c.post("/api/v1/legal/accept/", {"documents": ["terms", "privacy"]}, format="json")
        self.assertEqual(Acceptance.objects.filter(user=user).count(), 2)
        self.assertTrue(c.get("/api/v1/legal/accept/").json()["accepted"]["terms"])


class SignupConsentTests(TestCase):
    def test_signup_records_acceptance_when_sent(self):
        r = APIClient().post("/api/v1/auth/register/", {"email": "new@example.com", "password": "Str0ng-Pass-77!", "first_name": "New", "accept_terms": True}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(set(Acceptance.objects.filter(user=user).values_list("document", flat=True)), {"terms", "privacy"})


class NullBodiesAreJsonTests(TestCase):
    def test_no_profile_and_no_delivery_answer_with_a_json_null(self):
        user = make_user("nobody")
        c = client_for(user)
        r = c.get("/api/v1/dispatch/driver/me/")
        self.assertEqual((r.status_code, r.content), (200, b"null"))

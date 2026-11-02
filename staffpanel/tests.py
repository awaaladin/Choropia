"""The staff panel and manual payouts. Paystack is never contacted."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import TOTPDevice
from accounts.two_factor import generate_secret, totp_code
from dispatch import crypto
from dispatch.models import DocumentAccessLog, DriverDocument, DriverProfile
from listings.models import Category, Listing
from orders.models import Order
from orders.state_machine import OrderStatus
from payments import payouts
from payments.models import Payment, Payout, PayoutAccount

from .models import AuditLog

User = get_user_model()


def make_user(label, **extra):
    return User.objects.create_user(f"{label}@example.com", "pw12345!", first_name=label.title(), **extra)


class Base(TestCase):
    def setUp(self):
        cache.clear()  # the sign-in throttle lives in the cache
        self.boss = User.objects.create_superuser("boss@example.com", "pw12345!", first_name="Boss")
        self.staff = User.objects.create_user("staff@example.com", "pw12345!", first_name="Staff", is_staff=True)
        self.seller, self.buyer = make_user("seller"), make_user("buyer")
        cat = Category.objects.get_or_create(name="Electronics")[0]
        self.listing = Listing.objects.create(owner=self.seller, category=cat, title="Laptop", price="20000.00")
        self.order = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("20000.00"), status=OrderStatus.COMPLETED)
        self.payment = Payment.objects.create(order=self.order, reference="CHOROPIA-ORDER-20261102-ABCDEF123456", amount=Decimal("20000.00"),
                                              status=Payment.Status.RELEASED, paid_at=timezone.now(), released_at=timezone.now())
        self.payout = Payout.objects.create(payment=self.payment, seller=self.seller, gross_amount=Decimal("20000.00"), commission_rate=Decimal("5.00"),
                                            commission_amount=Decimal("1000.00"), net_amount=Decimal("19000.00"), status=Payout.Status.NEEDS_ATTENTION,
                                            failure_reason="Paystack refused the request (403)")
        self.account = PayoutAccount.objects.create(user=self.seller, bank_code="058", bank_name="GTBank", account_last4="1234", account_name="SELLER ONE", recipient_code="RCP_abc")

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c


class AccessTests(Base):
    def test_anonymous_goes_to_sign_in_and_members_are_refused(self):
        self.assertEqual(Client().get("/staff/").status_code, 302)
        self.assertIn("/staff/login/", Client().get("/staff/payouts/")["Location"])
        self.assertEqual(self.login(self.buyer).get("/staff/").status_code, 403)

    def test_every_page_opens_for_staff(self):
        c = self.login(self.staff)
        for url in ["/staff/", "/staff/payouts/", "/staff/payouts/?tab=paid", "/staff/payouts/?tab=waiting", f"/staff/payouts/{self.payout.pk}/", "/staff/money/",
                    "/staff/money/?range=7", "/staff/orders/", f"/staff/orders/{self.order.pk}/", "/staff/drivers/", "/staff/people/",
                    f"/staff/people/{self.seller.pk}/", "/staff/listings/", "/staff/audit/", "/staff/money/payouts.csv"]:
            self.assertEqual(c.get(url).status_code, 200, url)

    def test_staff_who_are_not_superusers_cannot_move_money(self):
        c = self.login(self.staff)
        self.assertEqual(c.post(f"/staff/payouts/{self.payout.pk}/mark-paid/", {"reference": "X"}).status_code, 403)
        self.assertEqual(c.post(f"/staff/payouts/{self.payout.pk}/reveal/").status_code, 403)
        self.assertEqual(c.post(f"/staff/orders/{self.order.pk}/resolve/", {"resolution": "refund"}).status_code, 403)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.NEEDS_ATTENTION)

    def test_sign_in_needs_a_staff_account_and_the_right_password(self):
        c = Client()
        self.assertContains(c.post("/staff/login/", {"email": "buyer@example.com", "password": "pw12345!"}), "do not match a staff account")
        self.assertContains(c.post("/staff/login/", {"email": "boss@example.com", "password": "wrong"}), "do not match a staff account")
        self.assertEqual(c.post("/staff/login/", {"email": "boss@example.com", "password": "pw12345!"}).status_code, 302)
        self.assertEqual(c.get("/staff/").status_code, 200)

    def test_two_step_staff_must_enter_their_code(self):
        secret = generate_secret()
        TOTPDevice.objects.create(user=self.boss, secret=secret, confirmed=True)
        c = Client()
        r = c.post("/staff/login/", {"email": "boss@example.com", "password": "pw12345!"})
        self.assertEqual(r["Location"], "/staff/login/code/")
        self.assertEqual(c.get("/staff/").status_code, 302, "a password alone must not be enough")
        self.assertContains(c.post("/staff/login/code/", {"code": "000000"}), "not right")
        self.assertEqual(c.post("/staff/login/code/", {"code": totp_code(secret)}).status_code, 302)
        self.assertEqual(c.get("/staff/").status_code, 200)

    def test_repeated_wrong_passwords_are_throttled(self):
        c = Client()
        for _ in range(10):
            c.post("/staff/login/", {"email": "boss@example.com", "password": "wrong"})
        self.assertContains(c.post("/staff/login/", {"email": "boss@example.com", "password": "pw12345!"}), "Too many attempts")


class ManualPayoutTests(Base):
    def test_mark_paid_records_who_when_and_how_and_tells_the_seller(self):
        c = self.login(self.boss)
        with self.captureOnCommitCallbacks(execute=True):
            r = c.post(f"/staff/payouts/{self.payout.pk}/mark-paid/", {"reference": "GTB-998877", "note": "paid from the office account"})
        self.assertEqual(r.status_code, 302)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.SUCCESS)
        self.assertEqual((self.payout.manual_reference, self.payout.manual_paid_by), ("GTB-998877", self.boss))
        self.assertIsNotNone(self.payout.manual_paid_at)
        self.assertEqual(self.payout.failure_reason, "")
        self.assertTrue(AuditLog.objects.filter(action="payout.mark_paid_by_hand", staff=self.boss).exists())
        self.assertTrue(any("on its way" in m.subject for m in mail.outbox), [m.subject for m in mail.outbox])

    def test_it_cannot_be_done_twice_or_without_a_reference(self):
        payouts.mark_paid_manually(self.payout.pk, self.boss, "REF-1")
        again = payouts.mark_paid_manually(self.payout.pk, self.boss, "REF-2")
        self.assertEqual(again.manual_reference, "REF-1", "a paid payout is returned untouched")
        other = Payout.objects.create(payment=Payment.objects.create(order=Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("5.00")),
                                      reference="CHOROPIA-ORDER-20261102-000000000001", amount=Decimal("5.00"), status=Payment.Status.RELEASED),
                                      seller=self.seller, gross_amount=Decimal("5.00"), commission_rate=Decimal("5"), commission_amount=Decimal("0.25"),
                                      net_amount=Decimal("4.75"), status=Payout.Status.PENDING)
        with self.assertRaises(payouts.ManualPayoutError):
            payouts.mark_paid_manually(other.pk, self.boss, "   ")

    def test_a_transfer_already_in_flight_blocks_paying_by_hand(self):
        Payout.objects.filter(pk=self.payout.pk).update(status=Payout.Status.PROCESSING)
        with self.assertRaises(payouts.ManualPayoutError) as ctx:
            payouts.mark_paid_manually(self.payout.pk, self.boss, "REF")
        self.assertIn("in progress", str(ctx.exception))

    def test_money_not_released_cannot_be_paid(self):
        Payment.objects.filter(pk=self.payment.pk).update(status=Payment.Status.PAID_HELD)
        with self.assertRaises(payouts.ManualPayoutError):
            payouts.mark_paid_manually(self.payout.pk, self.boss, "REF")

    def test_automatic_sending_never_touches_a_payout_paid_by_hand(self):
        payouts.mark_paid_manually(self.payout.pk, self.boss, "REF")
        with mock.patch("payments.payouts._paystack") as client, override_settings(PAYOUTS_ENABLED=True):
            payouts.process_payout(self.payout.pk)
        client.assert_not_called()

    def test_showing_the_bank_details_asks_paystack_and_is_logged(self):
        fake = mock.MagicMock()
        fake.fetch_recipient.return_value = {"details": {"bank_name": "GTBank", "account_number": "0123456789", "account_name": "SELLER ONE"}}
        with mock.patch("payments.payouts._paystack", return_value=fake):
            r = self.login(self.boss).post(f"/staff/payouts/{self.payout.pk}/reveal/")
        self.assertContains(r, "0123456789")
        fake.fetch_recipient.assert_called_once_with("RCP_abc")
        self.assertTrue(AuditLog.objects.filter(action="payout.reveal_bank_details").exists())
        self.assertNotContains(self.login(self.boss).get(f"/staff/payouts/{self.payout.pk}/"), "0123456789")

    def test_a_driver_payout_paid_by_hand_notifies_the_driver_in_app(self):
        driver = make_user("driver")
        payout = Payout.objects.create(payment=self.payment, kind=Payout.Kind.DRIVER, seller=driver, gross_amount=Decimal("1000"), commission_rate=Decimal("2.5"),
                                       commission_amount=Decimal("25"), net_amount=Decimal("975"), status=Payout.Status.AWAITING_ACCOUNT)
        payouts.mark_paid_manually(payout.pk, self.boss, "REF-D")
        self.assertTrue(driver.notifications.filter(verb__contains="was paid").exists())

    def test_retry_puts_a_stuck_payout_back_in_the_queue(self):
        with override_settings(PAYOUTS_ENABLED=False):
            self.login(self.boss).post(f"/staff/payouts/{self.payout.pk}/retry/")
        self.payout.refresh_from_db()
        self.assertEqual((self.payout.status, self.payout.attempts), (Payout.Status.PENDING, 0))

    def test_money_page_counts_a_payout_paid_by_hand(self):
        payouts.mark_paid_manually(self.payout.pk, self.boss, "REF")
        page = self.login(self.boss).get("/staff/money/?range=all")
        self.assertContains(page, "₦19,000.00")
        self.assertContains(page, "₦1,000.00")
        csv_text = self.login(self.boss).get("/staff/money/payouts.csv").content.decode()
        self.assertIn("REF", csv_text)


class DisputeAndPeopleTests(Base):
    def test_a_dispute_can_be_settled_for_the_buyer_with_a_real_refund(self):
        Payment.objects.filter(pk=self.payment.pk).update(status=Payment.Status.PAID_HELD)
        Order.objects.filter(pk=self.order.pk).update(status=OrderStatus.DISPUTED, dispute_reason="It never came")
        with mock.patch("payments.services._paystack") as paystack:
            r = self.login(self.boss).post(f"/staff/orders/{self.order.pk}/resolve/", {"resolution": "refund", "note": "no proof of delivery"})
        self.assertEqual(r.status_code, 302)
        paystack.return_value.refund.assert_called_once_with(self.payment.reference)
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual((self.order.status, self.payment.status), (OrderStatus.REFUNDED, Payment.Status.REFUNDED))
        self.assertTrue(AuditLog.objects.filter(action="order.resolve_dispute").exists())

    def test_only_disputed_orders_can_be_settled(self):
        self.login(self.boss).post(f"/staff/orders/{self.order.pk}/resolve/", {"resolution": "refund"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)

    def test_suspending_a_person_blocks_them_but_never_yourself_or_a_superuser(self):
        c = self.login(self.boss)
        c.post(f"/staff/people/{self.buyer.pk}/toggle/")
        self.buyer.refresh_from_db()
        self.assertFalse(self.buyer.is_active)
        c.post(f"/staff/people/{self.buyer.pk}/toggle/")
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.is_active)
        c.post(f"/staff/people/{self.boss.pk}/toggle/")
        self.boss.refresh_from_db()
        self.assertTrue(self.boss.is_active)

    def test_a_listing_can_be_taken_down_and_restored_but_not_a_sold_one(self):
        c = self.login(self.staff)
        c.post(f"/staff/listings/{self.listing.pk}/toggle/")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.REMOVED)
        c.post(f"/staff/listings/{self.listing.pk}/toggle/")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.ACTIVE)
        Listing.objects.filter(pk=self.listing.pk).update(status=Listing.Status.SOLD)
        c.post(f"/staff/listings/{self.listing.pk}/toggle/")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, Listing.Status.SOLD)


class DriverReviewTests(Base):
    def setUp(self):
        super().setUp()
        self.driver_user = make_user("driver")
        self.driver = DriverProfile.objects.create(user=self.driver_user, full_name="Ada Okon", phone="08011111111", whatsapp="08011111111",
                                                   vehicle_type="bike", guarantor_name="Mr G", guarantor_phone="08022222222")

    def _add_documents(self):
        for kind in DriverDocument.REQUIRED:
            DriverDocument.objects.create(driver=self.driver, kind=kind.value, content_type="image/jpeg", size_bytes=4, encrypted_data=crypto.encrypt(b"\xff\xd8\xff\xe0"))

    def test_approval_needs_all_four_documents(self):
        c = self.login(self.staff)
        c.post(f"/staff/drivers/{self.driver.pk}/decide/", {"decision": "approve"})
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.status, DriverProfile.Status.PENDING)
        self._add_documents()
        with self.captureOnCommitCallbacks(execute=True):
            c.post(f"/staff/drivers/{self.driver.pk}/decide/", {"decision": "approve"})
        self.driver.refresh_from_db()
        self.assertEqual((self.driver.status, self.driver.reviewed_by), (DriverProfile.Status.APPROVED, self.staff))
        self.assertTrue(any("approved" in m.subject.lower() for m in mail.outbox))

    def test_rejection_tells_the_driver_why(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.login(self.staff).post(f"/staff/drivers/{self.driver.pk}/decide/", {"decision": "reject", "note": "The ID photo is blurred."})
        self.driver.refresh_from_db()
        self.assertEqual((self.driver.status, self.driver.review_note), (DriverProfile.Status.REJECTED, "The ID photo is blurred."))
        self.assertTrue(any("blurred" in m.body for m in mail.outbox))

    def test_opening_a_document_decrypts_it_and_is_logged_twice(self):
        self._add_documents()
        doc = self.driver.documents.first()
        r = self.login(self.staff).get(f"/staff/documents/{doc.pk}/")
        self.assertEqual((r.status_code, r.content), (200, b"\xff\xd8\xff\xe0"))
        self.assertIn("no-store", r["Cache-Control"])
        self.assertEqual(DocumentAccessLog.objects.filter(document=doc, staff=self.staff).count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="driver.document_view").exists())
        self.assertEqual(Client().get(f"/staff/documents/{doc.pk}/").status_code, 302)
        self.assertEqual(self.login(self.buyer).get(f"/staff/documents/{doc.pk}/").status_code, 403)


class DealsBoardTests(Base):
    def test_a_released_deal_with_an_unpaid_payout_needs_you_and_names_both_sides(self):
        User.objects.filter(pk=self.seller.pk).update(phone_number="08031112222")
        User.objects.filter(pk=self.buyer.pk).update(phone_number="08033334444")
        Payout.objects.filter(pk=self.payout.pk).update(status=Payout.Status.PENDING)
        page = self.login(self.staff).get("/staff/deals/?tab=needs")
        self.assertContains(page, "Pay the seller")
        self.assertContains(page, "19000.00")
        self.assertContains(page, "FROM (seller)")
        self.assertContains(page, "08031112222")
        self.assertContains(page, "08033334444")

    def test_each_stage_has_a_plain_next_step(self):
        from .views import describe_deal

        expected = {
            OrderStatus.PENDING_PAYMENT: "Waiting for the buyer to pay",
            OrderStatus.PAID_ESCROW: "waiting for the seller to send",
            OrderStatus.IN_TRANSIT: "On its way",
            OrderStatus.DELIVERED: "Waiting for the buyer to confirm",
            OrderStatus.DISPUTED: "decide who gets the money",
        }
        for status, text in expected.items():
            order = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("10.00"), status=status)
            step, needs = describe_deal(order)
            self.assertIn(text.lower(), step.lower(), status)
            self.assertEqual(needs, status == OrderStatus.DISPUTED)

    def test_tabs_split_in_progress_waiting_and_finished(self):
        c = self.login(self.staff)
        paid = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("10.00"), status=OrderStatus.IN_TRANSIT)
        unpaid = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("11.00"), status=OrderStatus.PENDING_PAYMENT)
        self.assertContains(c.get("/staff/deals/?tab=progress"), f"Order #{paid.pk}")
        self.assertNotContains(c.get("/staff/deals/?tab=progress"), f"Order #{unpaid.pk}")
        self.assertContains(c.get("/staff/deals/?tab=unpaid"), f"Order #{unpaid.pk}")


class InviteOnlySellingTests(Base):
    def _create(self, user):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(user)
        return c.post("/api/v1/listings/", {"title": "Phone", "description": "x", "price": "100.00", "condition": "used", "category": self.listing.category_id}, format="json")

    def test_off_by_default_so_anyone_can_sell(self):
        self.assertEqual(self._create(self.buyer).status_code, 201)

    def test_when_on_only_approved_sellers_and_staff_can_post(self):
        c = self.login(self.boss)
        c.post("/staff/sellers/add/", {"email": "seller@example.com", "focus": "Gadgets"})
        c.post("/staff/sellers/setting/", {"on": "1"})
        self.assertEqual(self._create(self.buyer).status_code, 403)
        self.assertIn("invite-only", str(self._create(self.buyer).json()))
        self.assertEqual(self._create(self.seller).status_code, 201)
        self.assertEqual(self._create(self.staff).status_code, 201)

    def test_browsing_and_buying_are_unaffected(self):
        self.login(self.boss).post("/staff/sellers/setting/", {"on": "1"})
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get("/api/v1/listings/").status_code, 200)

    def test_removing_a_seller_stops_new_posts_and_turning_it_off_reopens_selling(self):
        c = self.login(self.boss)
        c.post("/staff/sellers/add/", {"email": "buyer@example.com", "focus": "Fashion"})
        c.post("/staff/sellers/setting/", {"on": "1"})
        self.assertEqual(self._create(self.buyer).status_code, 201)
        from .models import ApprovedSeller

        c.post(f"/staff/sellers/{ApprovedSeller.objects.get(user=self.buyer).pk}/remove/")
        self.assertEqual(self._create(self.buyer).status_code, 403)
        c.post("/staff/sellers/setting/", {"on": "0"})
        self.assertEqual(self._create(self.buyer).status_code, 201)

    def test_only_superusers_change_it_and_unknown_emails_are_refused(self):
        self.assertEqual(self.login(self.staff).post("/staff/sellers/setting/", {"on": "1"}).status_code, 403)
        page = self.login(self.boss).post("/staff/sellers/add/", {"email": "nobody@example.com"}, follow=True)
        self.assertContains(page, "No account has that email")
        self.assertEqual(self.login(self.staff).get("/staff/sellers/").status_code, 200)

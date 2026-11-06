"""Emails to the admin when something needs a person."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from dispatch.models import DriverDocument, DriverProfile
from notifications import staff_alerts
from orders.models import Order
from orders.state_machine import OrderStatus
from payments import payouts, services
from payments.models import Payment, Payout
from payments.tests.test_paystack import charge

from .digest import send_daily_digest
from .models import AuditLog
from .tests import Base, make_user

ADMIN = "hiexecontact@gmail.com"


def subjects():
    return [m.subject for m in mail.outbox if m.to == [ADMIN]]


@override_settings(STAFF_ALERTS_ENABLED=True, STAFF_ALERT_EMAILS=[ADMIN], CHOROPIA_SITE_URL="https://choropia.test")
class StaffAlertTests(Base):
    def test_a_paid_order_and_a_dispute_email_the_admin_with_a_link(self):
        order = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("20000.00"))
        payment = Payment.objects.create(order=order, reference="CHOROPIA-ORDER-20261102-AAAAAAAAAAAA", amount=Decimal("20000.00"))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.confirm_paystack_payment(payment.reference, charge(payment.reference, amount_kobo=2_000_000))
        self.assertTrue(any("New paid order" in s for s in subjects()), subjects())
        paid = next(m for m in mail.outbox if m.to == [ADMIN] and "New paid order" in m.subject)
        self.assertIn("Seller", paid.body)
        self.assertIn("https://choropia.test/staff/deals/", paid.body)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            order.refresh_from_db()
            order.dispute_reason = "It never came"
            order.save()
            order.transition_to(OrderStatus.COURIER_ASSIGNED, actor=self.seller)
            order.transition_to(OrderStatus.DISPUTED, actor=self.buyer, note="It never came")
        self.assertTrue(any("Dispute on order" in s for s in subjects()), subjects())

    def test_a_driver_application_and_complete_documents_each_email_the_admin(self):
        from rest_framework.test import APIClient

        user = make_user("newrider")
        c = APIClient()
        c.force_authenticate(user)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = c.put("/api/v1/dispatch/driver/me/", {"full_name": "Emem Udo", "phone": "08012345678", "whatsapp": "08012345678", "vehicle_type": "bike",
                                                       "plate_number": "", "guarantor_name": "Mr Etim", "guarantor_phone": "08055555555", "accept_terms": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([s for s in subjects() if "New driver application" in s], ["[Choropia admin] New driver application"])
        import io

        from PIL import Image

        def png():
            buf = io.BytesIO()
            Image.new("RGB", (40, 40), (1, 2, 3)).save(buf, "PNG")
            buf.seek(0)
            buf.name = "x.png"
            return buf

        mail.outbox.clear()
        for index, kind in enumerate(DriverDocument.REQUIRED):
            with self.captureOnCommitCallbacks(execute=True):
                c.post("/api/v1/dispatch/driver/documents/", {"kind": kind.value, "file": png()}, format="multipart")
            ready = [s for s in subjects() if "Driver documents ready" in s]
            self.assertEqual(len(ready), 1 if index >= 1 else 0, f"after document {index + 1}")  # any two documents are enough, and it is announced once

    def test_payouts_to_hand_over_and_stuck_payouts_email_the_admin(self):
        order = Order.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller, price=Decimal("20000.00"), status=OrderStatus.COMPLETED)
        payment = Payment.objects.create(order=order, reference="CHOROPIA-ORDER-20261102-BBBBBBBBBBBB", amount=Decimal("20000.00"), status=Payment.Status.RELEASED)
        mail.outbox.clear()
        with override_settings(PAYOUTS_ENABLED=False), self.captureOnCommitCallbacks(execute=True):
            payouts.release_hook(payment)
        self.assertTrue(any("Pay out order" in s for s in subjects()), subjects())
        payout = Payout.objects.get(payment=payment)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            payouts._attention(payout, "Paystack refused the request (403)")
        self.assertTrue(any("needs you" in s for s in subjects()), subjects())

    def test_a_failing_mail_server_never_breaks_the_thing_that_triggered_the_alert(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")), self.captureOnCommitCallbacks(execute=True):
            staff_alerts.alert("x", "y", ["z"])  # must not raise

    @override_settings(STAFF_ALERTS_ENABLED=False)
    def test_alerts_can_be_switched_off(self):
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            staff_alerts.alert("x", "y", ["z"])
        self.assertEqual(subjects(), [])


@override_settings(STAFF_ALERTS_ENABLED=True, STAFF_ALERT_EMAILS=[ADMIN, "second@example.com"])
class DailyDigestTests(Base):
    def test_nothing_waiting_means_no_email(self):
        Payout.objects.all().delete()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(send_daily_digest()["sent"], False)
        self.assertEqual(mail.outbox, [])

    def test_waiting_work_is_listed_once_a_day_to_every_admin_address(self):
        driver = DriverProfile.objects.create(user=make_user("pend"), full_name="Pat Pending", phone="1", whatsapp="1", vehicle_type="bike", guarantor_name="G", guarantor_phone="2")
        DriverDocument.objects.create(driver=driver, kind="id_card", content_type="image/png", size_bytes=1, encrypted_data=b"x")
        Order.objects.filter(pk=self.order.pk).update(status=OrderStatus.DISPUTED)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            first = send_daily_digest()
        self.assertTrue(first["sent"])
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([ADMIN, "second@example.com"]))
        body = mail.outbox[0].body
        self.assertIn("driver application", body)
        self.assertIn("open dispute", body)
        self.assertIn("payout", body)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(send_daily_digest()["sent"], False)
        self.assertEqual(mail.outbox, [])
        AuditLog.objects.filter(action="digest.sent").update(at=timezone.now() - timedelta(hours=25))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(send_daily_digest()["sent"])

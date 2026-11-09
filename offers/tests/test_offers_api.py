from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts import pin as pin_service
from accounts.models import User
from chat.models import Conversation, Message
from listings.models import Category, Listing
from offers import services
from offers.models import Offer, OfferEvent

PIN = "2580"


def offers_url(conversation):
    return f"/api/v1/conversations/{conversation.pk}/offers/"


class OfferFixture(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        self.outsider = User.objects.create_user("outsider@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Phones")
        self.listing = Listing.objects.create(owner=self.seller, category=category, title="iPhone 13", price="200000.00")
        self.conversation = Conversation.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller)
        pin_service.set_pin(self.seller, PIN)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def make(self, user=None, **overrides):
        body = {
            "listing_id": self.listing.pk,
            "amount_kobo": 18_500_000,
            "allowed_delivery_methods": ["meetup", "seller_delivers"],
            "note": "Last price",
            "pin": PIN,
            **overrides,
        }
        return self.client_for(user or self.seller).post(offers_url(self.conversation), body, format="json")


class CreateOfferTests(OfferFixture):
    def test_seller_makes_an_offer_with_the_right_pin(self):
        r = self.make()
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual((body["amount_kobo"], body["fee_kobo"], body["seller_net_kobo"]), (18_500_000, 772_500, 17_727_500))
        self.assertEqual((body["status"], body["viewer_role"], body["listing_price_kobo"]), ("pending", "seller", 20_000_000))
        self.assertNotIn("pin", body)
        offer = Offer.objects.get()
        self.assertFalse(offer.seller_verified_snapshot)
        self.assertAlmostEqual((offer.expires_at - offer.created_at).total_seconds(), 24 * 3600, delta=5)
        # The card is posted into the chat, pointing at the live offer, with a text fallback for older apps.
        message = Message.objects.get(conversation=self.conversation)
        self.assertEqual((message.message_type, message.offer_id, message.sender_id), ("offer", offer.pk, self.seller.pk))
        self.assertIn("₦185,000", message.body)
        self.assertEqual(list(offer.events.values_list("to_status", flat=True)), ["pending"])

    def test_verified_status_and_fee_are_snapshotted(self):
        self.seller.profile.seller_verified = True
        self.seller.profile.save()
        offer_id = self.make().json()["id"]
        self.seller.profile.seller_verified = False
        self.seller.profile.save()
        self.listing.price = "100.00"
        self.listing.save()
        offer = Offer.objects.get(pk=offer_id)
        self.assertEqual((offer.fee_kobo, offer.seller_verified_snapshot, offer.amount_kobo), (655_000, True, 18_500_000))

    def test_wrong_pin_is_refused_and_counted(self):
        r = self.make(pin="1357")
        self.assertEqual(r.status_code, 403)
        self.assertEqual((r.json()["code"], r.json()["attempts_left"]), ("pin_invalid", 4))
        self.assertFalse(Offer.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_no_pin_looks_exactly_like_a_wrong_pin(self):
        self.seller.transaction_pin.delete()
        r = self.make()
        self.assertEqual((r.status_code, r.json()["code"], r.json()["detail"]), (403, "pin_invalid", pin_service.GENERIC_MESSAGE))

    def test_five_wrong_pins_lock_offers_for_fifteen_minutes(self):
        for _ in range(4):
            self.assertEqual(self.make(pin="1357").status_code, 403)
        r = self.make(pin="1357")
        self.assertEqual((r.status_code, r.json()["code"]), (423, "pin_locked"))
        self.assertGreaterEqual(r.json()["retry_after"], 15 * 60)
        r = self.make()  # even the right PIN
        self.assertEqual(r.status_code, 423)
        self.assertFalse(Offer.objects.exists())

    def test_price_above_the_listing_is_refused(self):
        r = self.make(amount_kobo=20_000_001)
        self.assertEqual((r.status_code, r.json()["code"], r.json()["max_amount_kobo"]), (400, "amount_above_listing", 20_000_000))
        self.assertEqual(self.make(amount_kobo=20_000_000).status_code, 201)  # the full price is fine

    @override_settings(OFFER_MAX_PERCENT_OF_LISTING=90)
    def test_the_ceiling_is_a_setting(self):
        self.assertEqual(self.make(amount_kobo=18_000_001).status_code, 400)
        self.assertEqual(self.make(amount_kobo=18_000_000).status_code, 201)

    def test_zero_negative_and_fractional_amounts_are_refused(self):
        for bad in (0, -100, 1.5, "abc"):
            self.assertEqual(self.make(amount_kobo=bad).status_code, 400, bad)

    def test_bad_validation_does_not_burn_a_pin_attempt(self):
        self.make(amount_kobo=0, pin="1357")
        self.assertEqual(self.seller.transaction_pin.failed_attempts, 0)

    def test_the_buyer_cannot_make_an_offer(self):
        pin_service.set_pin(self.buyer, PIN)
        r = self.make(user=self.buyer)
        self.assertEqual((r.status_code, r.json()["code"]), (403, "forbidden"))

    def test_an_outsider_cannot_see_or_use_the_conversation(self):
        pin_service.set_pin(self.outsider, PIN)
        self.assertEqual(self.make(user=self.outsider).status_code, 404)
        self.assertEqual(self.client_for(self.outsider).get(offers_url(self.conversation)).status_code, 404)

    def test_someone_elses_listing_is_refused(self):
        other = Listing.objects.create(owner=self.outsider, category=self.listing.category, title="X", price="5000")
        self.assertEqual(self.make(listing_id=other.pk).json()["code"], "listing")

    def test_a_sold_listing_is_refused(self):
        self.listing.status = Listing.Status.SOLD
        self.listing.save()
        self.assertEqual(self.make().json()["code"], "listing_unavailable")

    def test_rider_needs_delivery_set_up_on_the_listing(self):
        r = self.make(allowed_delivery_methods=["rider"])
        self.assertEqual((r.status_code, r.json()["code"]), (400, "delivery_methods"))
        self.assertEqual(self.make(allowed_delivery_methods=[]).status_code, 400)
        self.assertEqual(self.make(allowed_delivery_methods=["teleport"]).status_code, 400)


class SupersedeTests(OfferFixture):
    def test_a_new_offer_supersedes_the_old_one(self):
        first = self.make().json()["id"]
        second = self.make(amount_kobo=18_000_000).json()["id"]
        self.assertEqual(Offer.objects.get(pk=first).status, "superseded")
        self.assertEqual(Offer.objects.get(pk=second).status, "pending")
        self.assertEqual(Offer.objects.filter(status__in=Offer.ACTIVE_STATUSES).count(), 1)
        self.assertEqual(list(Offer.objects.get(pk=first).events.values_list("to_status", flat=True)), ["pending", "superseded"])

    def test_cannot_replace_an_offer_the_buyer_is_paying_for(self):
        offer = Offer.objects.get(pk=self.make().json()["id"])
        Offer.objects.filter(pk=offer.pk).update(status=Offer.Status.PAYMENT_PROCESSING)
        r = self.make(amount_kobo=1_000_000)
        self.assertEqual((r.status_code, r.json()["code"]), (409, "payment_in_progress"))

    def test_the_database_refuses_two_live_offers(self):
        offer = Offer.objects.get(pk=self.make().json()["id"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Offer.objects.create(
                conversation=self.conversation, listing=self.listing, seller=self.seller, buyer=self.buyer,
                amount_kobo=100, listing_price_kobo=100, fee_kobo=100, seller_net_kobo=0, seller_verified_snapshot=False,
                expires_at=offer.expires_at,
            )


class CancelDeclineTests(OfferFixture):
    def setUp(self):
        super().setUp()
        self.offer_id = self.make().json()["id"]

    def post(self, user, action):
        return self.client_for(user).post(f"/api/v1/offers/{self.offer_id}/{action}/")

    def test_seller_cancels_buyer_cannot(self):
        self.assertEqual(self.post(self.buyer, "cancel").status_code, 403)
        r = self.post(self.seller, "cancel")
        self.assertEqual((r.status_code, r.json()["status"]), (200, "cancelled"))
        self.assertEqual(self.post(self.seller, "cancel").status_code, 409)  # only once

    def test_buyer_declines_seller_cannot(self):
        self.assertEqual(self.post(self.seller, "decline").status_code, 403)
        self.assertEqual(self.post(self.buyer, "decline").json()["status"], "declined")
        self.assertEqual(self.post(self.seller, "cancel").status_code, 409)

    def test_outsiders_get_not_found_never_forbidden(self):
        for action in ("cancel", "decline"):
            self.assertEqual(self.post(self.outsider, action).status_code, 404)
        self.assertEqual(self.client_for(self.outsider).get(f"/api/v1/offers/{self.offer_id}/").status_code, 404)
        self.assertEqual(self.client_for(self.seller).get("/api/v1/offers/00000000-0000-4000-8000-000000000000/").status_code, 404)

    def test_every_change_is_audited_with_the_actor(self):
        self.post(self.buyer, "decline")
        event = OfferEvent.objects.filter(offer_id=self.offer_id).last()
        self.assertEqual((event.from_status, event.to_status, event.actor_id), ("pending", "declined", self.buyer.pk))
        with self.assertRaises(ValueError):
            event.save()  # append-only


class BuyerNeverSeesTheFeeTests(OfferFixture):
    def test_offer_and_message_payloads_hide_the_fee_from_the_buyer(self):
        offer_id = self.make().json()["id"]
        buyer = self.client_for(self.buyer)
        detail = buyer.get(f"/api/v1/offers/{offer_id}/").json()
        self.assertEqual(detail["viewer_role"], "buyer")
        for field in ("fee_kobo", "seller_net_kobo", "seller_verified_snapshot"):
            self.assertNotIn(field, detail)
        messages = buyer.get(f"/api/v1/messages/?conversation={self.conversation.pk}").json()
        rows = messages["results"] if isinstance(messages, dict) else messages
        card = next(m for m in rows if m["type"] == "offer")
        self.assertEqual(card["offer"]["amount_kobo"], 18_500_000)
        self.assertNotIn("fee_kobo", card["offer"])
        seller_rows = self.client_for(self.seller).get(f"/api/v1/messages/?conversation={self.conversation.pk}").json()
        seller_rows = seller_rows["results"] if isinstance(seller_rows, dict) else seller_rows
        self.assertEqual(next(m for m in seller_rows if m["type"] == "offer")["offer"]["seller_net_kobo"], 17_727_500)

    def test_clients_cannot_post_an_offer_message_themselves(self):
        r = self.client_for(self.buyer).post(
            "/api/v1/messages/", {"conversation": self.conversation.pk, "body": "hi", "type": "offer"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["type"], "text")


class ExpiryTests(OfferFixture):
    def test_the_job_expires_due_offers_only(self):
        due = Offer.objects.get(pk=self.make().json()["id"])
        Offer.objects.filter(pk=due.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        call_command("expire_offers", stdout=mock.MagicMock())
        self.assertEqual(Offer.objects.get(pk=due.pk).status, "expired")
        self.assertEqual(services.expire_due_offers(), {"expired": 0})  # idempotent

    def test_an_overdue_offer_reads_as_expired_before_the_job_runs_and_cannot_be_acted_on(self):
        offer_id = self.make().json()["id"]
        Offer.objects.filter(pk=offer_id).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client_for(self.buyer).get(f"/api/v1/offers/{offer_id}/").json()["status"], "expired")
        r = self.client_for(self.buyer).post(f"/api/v1/offers/{offer_id}/decline/")
        self.assertEqual(r.json()["status"], "expired")  # expired for real, not declined
        self.assertEqual(Offer.objects.get(pk=offer_id).status, "expired")

    @override_settings(OFFER_TTL_HOURS=2)
    def test_ttl_is_a_setting(self):
        offer = Offer.objects.get(pk=self.make().json()["id"])
        self.assertAlmostEqual((offer.expires_at - offer.created_at).total_seconds(), 2 * 3600, delta=5)

    def test_scheduled_jobs_endpoint_runs_expiry(self):
        with override_settings(CRON_SECRET="s3cret"):
            r = APIClient().post("/api/v1/internal/jobs/run/", HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertIn("chat_offers_expiry", r.json())


class BroadcastTests(OfferFixture):
    def test_each_change_is_sent_to_the_conversation_group_after_commit(self):
        layer = mock.Mock()
        with mock.patch("offers.services._group_send", layer.group_send):
            with self.captureOnCommitCallbacks(execute=True):
                offer_id = self.make().json()["id"]
            with self.captureOnCommitCallbacks(execute=True):
                self.client_for(self.seller).post(f"/api/v1/offers/{offer_id}/cancel/")
        groups = {c.args[0] for c in layer.group_send.call_args_list}
        events = [c.args[1] for c in layer.group_send.call_args_list]
        self.assertEqual(groups, {f"conversation_{self.conversation.pk}"})
        self.assertEqual([e["type"] for e in events], ["offer.updated", "offer.updated"])
        self.assertTrue(all(e["offer_id"] == offer_id for e in events))
        self.assertNotIn("fee_kobo", str(events))  # each connection serializes for its own user

    def test_a_broken_channel_layer_never_fails_the_offer(self):
        with mock.patch("offers.services._group_send", side_effect=RuntimeError("redis down")):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.make().status_code, 201)

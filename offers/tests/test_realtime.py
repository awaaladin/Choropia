"""End to end through the real chat consumer: an offer change reaches both people, each serialized for its own viewer."""
import asyncio

from asgiref.sync import async_to_sync, sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

import chat.routing
from accounts import pin as pin_service
from accounts.models import User
from chat.models import Conversation
from listings.models import Category, Listing
from offers import services


class OfferRealtimeTests(TransactionTestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Phones")
        self.listing = Listing.objects.create(owner=self.seller, category=category, title="Phone", price="50000.00")
        self.conversation = Conversation.objects.create(listing=self.listing, buyer=self.buyer, seller=self.seller)
        pin_service.set_pin(self.seller, "2580")

    async def _connect(self, user):
        app = URLRouter(chat.routing.websocket_urlpatterns)
        communicator = WebsocketCommunicator(app, f"/ws/chat/{self.conversation.pk}/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        return communicator

    def test_both_people_get_the_change_and_only_the_seller_sees_the_fee(self):
        async def scenario():
            seller_ws = await self._connect(self.seller)
            buyer_ws = await self._connect(self.buyer)
            offer = await sync_to_async(services.create_offer)(
                user=self.seller, conversation=self.conversation, listing_id=self.listing.pk, amount_kobo=4_000_000,
                allowed_delivery_methods=["meetup"], pin="2580",
            )
            seller_frame = await seller_ws.receive_json_from(timeout=3)
            buyer_frame = await buyer_ws.receive_json_from(timeout=3)
            for frame in (seller_frame, buyer_frame):
                self.assertEqual((frame["event"], frame["type"], frame["offer"]["id"]), ("offer.updated", "offer", str(offer.pk)))
                self.assertEqual(frame["offer"]["status"], "pending")
            self.assertEqual(seller_frame["offer"]["fee_kobo"], 240_000)
            self.assertNotIn("fee_kobo", buyer_frame["offer"])
            self.assertEqual(buyer_frame["offer"]["viewer_role"], "buyer")

            await sync_to_async(services.decline_offer)(user=self.buyer, offer_id=offer.pk)
            again = await seller_ws.receive_json_from(timeout=3)
            # Same message id: the card is replaced in place, not appended.
            self.assertEqual((again["id"], again["offer"]["status"]), (seller_frame["id"], "declined"))
            await seller_ws.disconnect()
            await buyer_ws.disconnect()

        async_to_sync(scenario)()

    def test_an_outsider_cannot_listen(self):
        outsider = User.objects.create_user("x@example.com", "pw-12345-pw")

        async def scenario():
            app = URLRouter(chat.routing.websocket_urlpatterns)
            communicator = WebsocketCommunicator(app, f"/ws/chat/{self.conversation.pk}/")
            communicator.scope["user"] = outsider
            connected, _ = await communicator.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()

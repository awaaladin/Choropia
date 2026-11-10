import logging

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.models import Conversation

from . import services
from .models import Offer
from .serializers import CreateOfferSerializer, OfferCheckoutSerializer, OfferSerializer

logger = logging.getLogger(__name__)


def error_response(exc: services.OfferError):
    return Response(exc.as_response_data(), status=exc.status)


class ConversationOffersView(APIView):
    """GET: the offers in a conversation (newest first). POST (seller only): make an offer, approved with your PIN."""

    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        self.throttle_scope = "offers" if self.request.method == "POST" else None
        return super().get_throttles()

    def _conversation(self, request, conversation_id):
        return (
            Conversation.objects.filter(
                Q(user_low=request.user) | Q(user_high=request.user), pk=conversation_id
            )
            .select_related("listing")
            .first()
        )

    @extend_schema(responses=OfferSerializer(many=True))
    def get(self, request, conversation_id):
        conversation = self._conversation(request, conversation_id)
        if conversation is None:
            return Response({"detail": "Conversation not found."}, status=404)
        offers = Offer.objects.filter(conversation=conversation).select_related("listing").prefetch_related("listing__photos")
        return Response(OfferSerializer(offers, many=True, context={"request": request}).data)

    @extend_schema(request=CreateOfferSerializer, responses={201: OfferSerializer})
    def post(self, request, conversation_id):
        conversation = self._conversation(request, conversation_id)
        if conversation is None:
            return Response({"detail": "Conversation not found."}, status=404)
        body = CreateOfferSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            offer = services.create_offer(
                user=request.user,
                conversation=conversation,
                listing_id=data["listing_id"],
                amount_kobo=data["amount_kobo"],
                allowed_delivery_methods=data["allowed_delivery_methods"],
                note=data.get("note", ""),
                pin=data["pin"],
            )
        except services.OfferError as exc:
            return error_response(exc)
        return Response(OfferSerializer(offer, context={"request": request}).data, status=201)


class OfferDetailView(APIView):
    """One offer, for its buyer or seller. Clients refetch this after a realtime reconnect."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=OfferSerializer)
    def get(self, request, offer_id):
        try:
            offer = services.get_for_participant(offer_id, request.user)
        except services.OfferError as exc:
            return error_response(exc)
        return Response(OfferSerializer(offer, context={"request": request}).data)


class _OfferActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "offers"
    perform = None

    @extend_schema(request=None, responses=OfferSerializer)
    def post(self, request, offer_id):
        try:
            offer = self.perform(user=request.user, offer_id=offer_id)
        except services.OfferError as exc:
            return error_response(exc)
        return Response(OfferSerializer(offer, context={"request": request}).data)


class CancelOfferView(_OfferActionView):
    """Seller: withdraw a pending offer."""

    perform = staticmethod(services.cancel_offer)


class DeclineOfferView(_OfferActionView):
    """Buyer: say no to a pending offer."""

    perform = staticmethod(services.decline_offer)


class OfferCheckoutView(APIView):
    """Buyer: open escrow checkout at the chat offer's locked price."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "orders"

    def post(self, request, offer_id):
        body = OfferCheckoutSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            order = services.create_offer_checkout(
                user=request.user,
                offer_id=offer_id,
                delivery_method=data["delivery_method"],
            )
        except services.OfferError as exc:
            return error_response(exc)

        if data["delivery_method"] == Offer.Delivery.RIDER:
            return Response({"order_id": order.pk, "authorization_url": None})

        from payments.gaxtron import GaxtronError
        from payments.paystack import PaystackError
        from payments.services import initialize_payment

        try:
            payment = initialize_payment(order, return_to_app=data["source"] == "app")
        except (PaystackError, GaxtronError):
            logger.exception("Could not initialize payment for offer %s", offer_id)
            return Response({"detail": "Payment checkout could not be opened. Please try again."}, status=502)
        if not payment.authorization_url:
            return Response({"detail": "The payment provider did not return a checkout URL."}, status=502)
        return Response({"order_id": order.pk, "authorization_url": payment.authorization_url})


class VerifyOfferPaymentView(APIView):
    """Buyer, back from Paystack: settles the payment now (escrow, or the offer opens again if it failed)."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "offers"

    @extend_schema(request=None, responses=OfferSerializer)
    def post(self, request, offer_id):
        from .settlement import verify_offer_payment

        try:
            offer = verify_offer_payment(user=request.user, offer_id=offer_id)
        except services.OfferError as exc:
            return error_response(exc)
        return Response(OfferSerializer(offer, context={"request": request}).data)


class HandoverCodeView(APIView):
    """Buyer only: your 6-digit handover code. Tell it to the seller (or the rider) once you hold the item."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "handover-code"

    def get(self, request, order_id):
        from .settlement import handover_code_for_buyer

        try:
            return Response(handover_code_for_buyer(user=request.user, order_id=order_id))
        except services.OfferError as exc:
            return error_response(exc)


class ConfirmHandoverView(APIView):
    """Seller: enter the buyer's code after handing the item over (meet-up / seller delivers). Releases escrow."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "handover-code"

    def post(self, request, order_id):
        from orders.serializers import OrderSerializer

        from .settlement import confirm_handover

        try:
            order = confirm_handover(user=request.user, order_id=order_id, code=request.data.get("code"))
        except services.OfferError as exc:
            return error_response(exc)
        return Response(OrderSerializer(order, context={"request": request}).data)

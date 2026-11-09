from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.models import Conversation

from . import services
from .models import Offer
from .serializers import CreateOfferSerializer, OfferSerializer


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

from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from listings.models import Listing
from orders.models import Order

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(Q(buyer=user) | Q(seller=user)).select_related(
            "listing", "buyer", "buyer__profile", "seller", "seller__profile"
        )

    def get_object(self):
        obj = super().get_object()
        if self.request.user.id not in (obj.buyer_id, obj.seller_id):
            raise PermissionDenied()
        return obj

    @action(detail=True, methods=["post"], url_path="create-order")
    def create_order(self, request, pk=None):
        conversation = self.get_object()

        if conversation.order_id:
            raise ValidationError("This conversation already has an order.")
        if request.user.id != conversation.buyer_id:
            raise PermissionDenied("Only the buyer can turn this conversation into an order.")

        listing = conversation.listing
        if listing.status != Listing.Status.ACTIVE:
            raise ValidationError("This listing is no longer active.")

        order = Order.objects.create(
            listing=listing, buyer=conversation.buyer, seller=conversation.seller, price=listing.price
        )
        conversation.order = order
        conversation.save(update_fields=["order"])

        from orders.serializers import OrderSerializer

        return Response(OrderSerializer(order).data, status=201)


class MessageViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Message.objects.filter(
            Q(conversation__buyer=user) | Q(conversation__seller=user)
        ).select_related("sender")
        conversation_id = self.request.query_params.get("conversation")
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        return qs

    def perform_create(self, serializer):
        conversation = serializer.validated_data["conversation"]
        if self.request.user.id not in (conversation.buyer_id, conversation.seller_id):
            raise PermissionDenied()
        message = serializer.save()

        from .realtime import broadcast_message

        broadcast_message(message)

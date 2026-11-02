from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from listings.models import Listing
from orders.models import Order

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

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

    def list(self, request, *args, **kwargs):
        """Opening a conversation (fetching its messages) means you have seen them: the other person's messages are marked
        read and the 'new message' notifications for this conversation disappear, so the unread badge only counts what you
        have not opened."""
        conversation_id = request.query_params.get("conversation")
        if conversation_id and str(conversation_id).isdigit():
            mark_conversation_seen(request.user, int(conversation_id))
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        conversation = serializer.validated_data["conversation"]
        if self.request.user.id not in (conversation.buyer_id, conversation.seller_id):
            raise PermissionDenied()
        message = serializer.save()

        from .realtime import broadcast_message

        broadcast_message(message)


def mark_conversation_seen(user, conversation_id: int) -> None:
    """Marks the other person's messages in this conversation as read, and clears its message notifications for `user`.
    Does nothing for a conversation `user` is not part of."""
    from notifications.models import Notification

    conversation = Conversation.objects.filter(pk=conversation_id).filter(Q(buyer=user) | Q(seller=user)).first()
    if conversation is None:
        return
    Message.objects.filter(conversation=conversation, read_at__isnull=True).exclude(sender=user).update(read_at=timezone.now())
    Notification.objects.filter(
        recipient=user,
        notification_type=Notification.Type.MESSAGE,
        target_content_type=ContentType.objects.get_for_model(Conversation),
        target_object_id=conversation.pk,
        is_read=False,
    ).update(is_read=True)

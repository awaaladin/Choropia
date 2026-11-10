import logging

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.demo import is_demo_user
from common.throttling import ScopedWritesMixin
from listings.models import Listing
from orders.models import Order

from .models import Conversation, Message
from .listing_references import append_listing_reference
from .serializers import ConversationSerializer, MessageSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversationViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(Q(user_low=user) | Q(user_high=user)).select_related(
            "listing", "buyer", "buyer__profile", "seller", "seller__profile",
            "user_low", "user_low__profile", "user_high", "user_high__profile",
        )

    def get_object(self):
        obj = super().get_object()
        if self.request.user.id not in (obj.user_low_id, obj.user_high_id):
            raise PermissionDenied()
        return obj

    @action(detail=False, methods=["post"], url_path="open")
    def open(self, request):
        other_user_id = request.data.get("other_user_id")
        listing_id = request.data.get("listing_id")
        if not other_user_id:
            raise ValidationError({"other_user_id": "This field is required."})

        try:
            other_user = User.objects.get(pk=other_user_id, is_active=True)
        except (User.DoesNotExist, TypeError, ValueError):
            raise ValidationError({"other_user_id": "User not found."})

        if other_user.pk == request.user.pk:
            raise ValidationError("You cannot start a conversation with yourself.")
        if is_demo_user(other_user):
            raise ValidationError("This seller is not available for messages.")

        listing = None
        if listing_id is not None:
            listing = Listing.objects.filter(pk=listing_id).first()
            if listing is None:
                raise ValidationError({"listing_id": "Listing not found."})
            if listing.owner_id != other_user.pk:
                raise ValidationError({"listing_id": "The listing must belong to the other participant."})
            if is_demo_user(listing.owner):
                raise ValidationError("This seller is not available for messages.")

        conversation, created = Conversation.get_or_create_direct_thread(request.user, other_user, listing=listing)
        if listing is not None:
            message, ref_created = append_listing_reference(conversation.pk, listing, request.user, request)
            if ref_created:
                from .realtime import broadcast_message

                broadcast_message(message)
        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=201 if created else 200)

    @action(detail=True, methods=["post"], url_path="create-order")
    def create_order(self, request, pk=None):
        conversation = self.get_object()
        listing_id = request.data.get("listing_id") or conversation.listing_id
        if listing_id is None:
            raise ValidationError({"listing_id": "Choose a listing from this conversation."})
        listing = Listing.objects.filter(pk=listing_id, owner_id=conversation.other_participant(request.user).pk).first()
        if listing is None:
            raise ValidationError({"listing_id": "This listing is not available in this conversation."})
        if listing.status != Listing.Status.ACTIVE or listing.quantity < 1:
            raise ValidationError("This listing is no longer active.")

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(
                listing=listing,
                buyer=request.user,
                status=Order.Status.PENDING_PAYMENT,
            ).first()
            created = order is None
            if created:
                order = Order.objects.create(
                    listing=listing, buyer=request.user, seller=listing.owner, price=listing.price
                )
            conversation.orders.add(order)
            if conversation.order_id is None:
                conversation.order = order
                conversation.save(update_fields=["order"])

        from orders.serializers import OrderSerializer

        return Response(OrderSerializer(order).data, status=201 if created else 200)


class MessageViewSet(
    ScopedWritesMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    write_throttle_scope = "chat-send"
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Message.objects.filter(
            Q(conversation__user_low=user) | Q(conversation__user_high=user)
        ).select_related("sender", "offer__listing", "referenced_listing").prefetch_related(
            "offer__listing__photos", "referenced_listing__photos"
        )
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
        if self.request.user.id not in (conversation.user_low_id, conversation.user_high_id):
            raise PermissionDenied()
        message = serializer.save()

        from .realtime import broadcast_message

        broadcast_message(message)

    def perform_destroy(self, message):
        if message.sender_id != self.request.user.id:
            raise PermissionDenied("You can only delete your own messages.")
        if message.message_type != Message.MessageType.TEXT:
            raise ValidationError("Offers and listing references cannot be deleted.")
        if message.deleted_at is not None:
            return

        with transaction.atomic():
            message = Message.objects.select_for_update().get(pk=message.pk)
            if message.sender_id != self.request.user.id:
                raise PermissionDenied("You can only delete your own messages.")
            if message.deleted_at is None:
                attachment_name = message.attachment.name if message.attachment else None
                attachment_storage = message.attachment.storage if message.attachment else None
                message.body = ""
                message.attachment = None
                message.attachment_type = ""
                message.duration_seconds = None
                message.deleted_at = timezone.now()
                message.save(
                    update_fields=("body", "attachment", "attachment_type", "duration_seconds", "deleted_at")
                )
                if attachment_name:
                    transaction.on_commit(
                        lambda: self._delete_attachment(attachment_storage, attachment_name)
                    )

        from .realtime import broadcast_message

        broadcast_message(message)

    @staticmethod
    def _delete_attachment(storage, name):
        try:
            storage.delete(name)
        except Exception:
            logger.exception("Could not remove deleted chat attachment %s", name)


def mark_conversation_seen(user, conversation_id: int) -> None:
    """Marks the other person's messages in this conversation as read, and clears its message notifications for `user`.
    Does nothing for a conversation `user` is not part of."""
    from notifications.models import Notification

    conversation = Conversation.objects.filter(pk=conversation_id).filter(
        Q(user_low=user) | Q(user_high=user)
    ).first()
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

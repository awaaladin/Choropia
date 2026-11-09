from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Conversation, Message


def build_listing_snapshot(listing, request=None):
    photo = listing.photos.first()
    thumbnail = photo.image.url if photo else None
    if thumbnail and request is not None:
        thumbnail = request.build_absolute_uri(thumbnail)
    return {
        "title": listing.title,
        "thumbnail": thumbnail,
        "price_kobo": int(Decimal(listing.price) * 100),
        "status": listing.status,
    }


@transaction.atomic
def append_listing_reference(conversation_id, listing, sender, request=None):
    conversation = Conversation.objects.select_for_update().get(pk=conversation_id)
    now = timezone.now()
    last_message = conversation.messages.order_by("-created_at", "-pk").first()
    if (
        last_message is not None
        and last_message.message_type == Message.MessageType.LISTING_REF
        and last_message.referenced_listing_id == listing.pk
        and last_message.created_at >= now - timedelta(hours=6)
    ):
        return last_message, False

    snapshot = build_listing_snapshot(listing, request)
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        message_type=Message.MessageType.LISTING_REF,
        referenced_listing=listing,
        listing_snapshot=snapshot,
    )
    return message, True

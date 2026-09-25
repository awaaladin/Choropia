import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .serializers import MessageSerializer

logger = logging.getLogger(__name__)


def group_name_for(conversation_id):
    return f"conversation_{conversation_id}"


def broadcast_message(message):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    # The message row is already saved; a Redis outage must not fail the request that sent it.
    try:
        async_to_sync(channel_layer.group_send)(
            group_name_for(message.conversation_id),
            {"type": "chat.message", "message": MessageSerializer(message).data},
        )
    except Exception:
        logger.warning("Realtime broadcast failed for message %s", message.id, exc_info=True)

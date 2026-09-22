from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .serializers import MessageSerializer


def group_name_for(conversation_id):
    return f"conversation_{conversation_id}"


def broadcast_message(message):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group_name_for(message.conversation_id),
        {"type": "chat.message", "message": MessageSerializer(message).data},
    )

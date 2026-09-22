from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.models import Q

from .models import Conversation, Message
from .realtime import group_name_for
from .serializers import MessageSerializer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        user = self.scope["user"]

        if not user.is_authenticated or not await self._is_participant(user, self.conversation_id):
            await self.close(code=4403)
            return

        self.group_name = group_name_for(self.conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        body = (content or {}).get("body", "").strip()
        if not body:
            return

        message = await self._create_message(self.scope["user"], self.conversation_id, body)
        await self.channel_layer.group_send(
            self.group_name, {"type": "chat.message", "message": MessageSerializer(message).data}
        )

    async def chat_message(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def _is_participant(self, user, conversation_id):
        return Conversation.objects.filter(Q(buyer=user) | Q(seller=user), id=conversation_id).exists()

    @database_sync_to_async
    def _create_message(self, user, conversation_id, body):
        return Message.objects.create(conversation_id=conversation_id, sender=user, body=body)

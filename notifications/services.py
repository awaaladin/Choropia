from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.contenttypes.models import ContentType

from .models import Notification


def group_name_for(user_id):
    return f"user_{user_id}_notifications"


def create_notification(recipient, notification_type, verb, actor=None, target=None):
    if recipient is None or (actor is not None and actor.id == recipient.id):
        return None  # never notify a user about their own action

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        verb=verb,
        target_content_type=ContentType.objects.get_for_model(target) if target else None,
        target_object_id=target.pk if target else None,
    )
    _push_realtime(notification)
    return notification


def _push_realtime(notification):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        group_name_for(notification.recipient_id),
        {
            "type": "notification.new",
            "notification": {
                "id": notification.id,
                "notification_type": notification.notification_type,
                "verb": notification.verb,
                "actor_id": notification.actor_id,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            },
        },
    )

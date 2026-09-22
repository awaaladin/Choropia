from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import create_notification
from .models import Notification


@receiver(post_save, sender="social.Follow")
def notify_on_follow(sender, instance, created, **kwargs):
    if not created:
        return

    target = instance.target
    if target is None:
        return

    from accounts.models import User
    from merchants.models import Merchant

    if isinstance(target, User):
        recipient = target
    elif isinstance(target, Merchant):
        recipient = target.user
    else:
        return

    create_notification(
        recipient=recipient,
        actor=instance.follower,
        notification_type=Notification.Type.FOLLOW,
        verb=f"{instance.follower.get_full_name()} started following you",
        target=target,
    )


@receiver(post_save, sender="chat.Message")
def notify_on_message(sender, instance, created, **kwargs):
    if not created:
        return

    conversation = instance.conversation
    recipient = conversation.other_participant(instance.sender)

    create_notification(
        recipient=recipient,
        actor=instance.sender,
        notification_type=Notification.Type.MESSAGE,
        verb=f"New message from {instance.sender.get_full_name()}",
        target=conversation,
    )


@receiver(post_save, sender="orders.OrderStatusHistory")
def notify_on_order_status_change(sender, instance, created, **kwargs):
    if not created:
        return

    order = instance.order
    notification_type = (
        Notification.Type.DISPUTE if instance.to_status == "disputed" else Notification.Type.ORDER_STATUS
    )

    for participant in (order.buyer, order.seller):
        if instance.actor_id and participant.id == instance.actor_id:
            continue  # don't notify the person who caused the change
        create_notification(
            recipient=participant,
            actor=instance.actor,
            notification_type=notification_type,
            verb=f"Order #{order.id} status changed to '{instance.to_status}'",
            target=order,
        )

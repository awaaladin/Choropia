from django.db.models.signals import post_save
from django.dispatch import receiver

import logging

from . import emails
from .services import create_notification
from .models import Notification

logger = logging.getLogger(__name__)


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

    if (instance.note or "").startswith("[auto]"):
        return  # a stage skipped because the buyer confirmed in person; the final status says enough

    order = instance.order
    _alert_staff_about_order(order, instance)
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
            verb=_order_verb(order, instance.to_status, is_seller=participant.id == order.seller_id),
            target=order,
        )
        try:
            emails.send_order_update(order, instance.to_status, participant, actor=instance.actor)
        except Exception:  # noqa: BLE001 - email must never break an order transition
            logger.exception("Order email could not be prepared for order %s", order.id)


ORDER_WORDING = {
    # status: (to the seller, to the buyer); {item} is the listing title
    "paid_escrow": ("Someone ordered '{item}'. It is paid and held safely: please dispatch it.", "Your payment for '{item}' is held safely until it arrives."),
    "courier_assigned": ("A driver has been assigned to '{item}'.", "A driver has been assigned to '{item}'."),
    "in_transit": ("'{item}' is on its way to the buyer.", "'{item}' is on its way to you."),
    "delivered": ("'{item}' was marked delivered.", "'{item}' was marked delivered. Please confirm you received it."),
    "confirmed": ("The buyer confirmed '{item}'. Your payout is being prepared.", "You confirmed '{item}'."),
    "completed": ("Order for '{item}' is complete.", "Order for '{item}' is complete."),
    "refunded": ("The order for '{item}' was refunded to the buyer.", "Your payment for '{item}' was refunded."),
    "cancelled": ("The order for '{item}' was cancelled.", "The order for '{item}' was cancelled."),
    "disputed": ("A dispute was opened on '{item}'.", "A dispute was opened on '{item}'."),
}


def _order_verb(order, status, is_seller):
    wording = ORDER_WORDING.get(status)
    if wording is None:
        return f"Order #{order.id} status changed to '{status}'"
    return wording[0 if is_seller else 1].format(item=order.listing.title)


@receiver(post_save, sender="listings.Listing")
def notify_followers_of_new_listing(sender, instance, created, **kwargs):
    """People who follow the seller (or their storefront) hear about a new listing."""
    if not created or instance.status != "active":
        return
    from django.contrib.contenttypes.models import ContentType

    from social.models import Follow

    owner = instance.owner
    targets = [(ContentType.objects.get_for_model(owner), owner.pk)]
    if instance.merchant_id:
        targets.append((ContentType.objects.get_for_model(instance.merchant), instance.merchant_id))
    seen = set()
    for content_type, object_id in targets:
        followers = Follow.objects.filter(content_type=content_type, object_id=object_id).select_related("follower")[:300]
        for follow in followers:
            if follow.follower_id in seen:
                continue
            seen.add(follow.follower_id)
            create_notification(
                recipient=follow.follower,
                actor=owner,
                notification_type=Notification.Type.NEW_LISTING,
                verb=f"{owner.get_full_name() or 'Someone you follow'} posted '{instance.title}'",
                target=instance,
            )


def _alert_staff_about_order(order, history):
    """The system moves money and goods by itself where it can; these are the moments a person should know about."""
    from . import staff_alerts

    item = f"Order #{order.id}: {order.listing.title}"
    who = f"Seller {order.seller.get_full_name()} ({order.seller.email}) to buyer {order.buyer.get_full_name()} ({order.buyer.email})."
    if history.to_status == "paid_escrow":
        staff_alerts.alert(
            f"New paid order #{order.id}", "A buyer has paid",
            [item, f"Amount: {staff_alerts.money(order.price)} (held until delivery is confirmed).", who], "/staff/deals/?tab=progress",
        )
    elif history.to_status == "disputed":
        staff_alerts.alert(
            f"Dispute on order #{order.id}", "A dispute was opened",
            [item, who, f"Reason: {order.dispute_reason or 'none written'}", "The money stays held until you decide."], f"/staff/orders/{order.id}/",
        )
    elif history.to_status == "refunded" and (history.note or "").startswith("Cancelled by"):
        staff_alerts.alert(
            f"Order #{order.id} cancelled and refunded", "A paid order was cancelled", [item, who, history.note], f"/staff/orders/{order.id}/"
        )
    elif history.to_status == "confirmed":
        staff_alerts.alert(
            f"Order #{order.id} confirmed: money is ready to release", "The buyer confirmed receipt",
            [item, who, "The seller will be paid. Check Payouts if automatic transfers are off."], "/staff/payouts/?tab=waiting",
        )

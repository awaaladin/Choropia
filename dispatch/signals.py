from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order
from orders.state_machine import OrderStatus


@receiver(post_save, sender=Order)
def end_delivery_with_order(sender, instance, **kwargs):
    """A refunded or cancelled order has nothing left to deliver."""
    if instance.status in (OrderStatus.REFUNDED, OrderStatus.CANCELLED):
        from . import services

        services.cancel_for_order(instance)

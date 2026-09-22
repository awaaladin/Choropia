from django.conf import settings
from django.utils.module_loading import import_string

from orders.state_machine import OrderStatus

from .models import Delivery
from .providers.base import DeliveryStatus


def get_provider():
    provider_class = import_string(settings.DELIVERY_PROVIDER)
    return provider_class()


def create_shipment_for_order(order):
    provider = get_provider()
    result = provider.create_shipment(order)
    return Delivery.objects.create(
        order=order,
        provider_name=provider.__class__.__name__,
        tracking_id=result.tracking_id,
        status=result.status,
    )


# Maps a courier status update to the Order transition it should trigger. Anything not listed
# here (e.g. a duplicate PENDING update) is treated as a no-op rather than an error.
_STATUS_TO_ORDER_TRANSITION = {
    DeliveryStatus.PICKED_UP: OrderStatus.IN_TRANSIT,
    DeliveryStatus.IN_TRANSIT: OrderStatus.IN_TRANSIT,
    DeliveryStatus.DELIVERED: OrderStatus.DELIVERED,
}


def apply_courier_status_update(delivery, new_status):
    delivery.status = new_status
    delivery.save(update_fields=["status"])

    target_order_status = _STATUS_TO_ORDER_TRANSITION.get(new_status)
    if target_order_status and delivery.order.status != target_order_status:
        delivery.order.transition_to(target_order_status, note=f"Courier status: {new_status}")
    return delivery

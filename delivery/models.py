from django.db import models

from common.models import TimeStampedModel
from orders.models import Order

from .providers.base import DeliveryStatus


class Delivery(TimeStampedModel):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")
    provider_name = models.CharField(max_length=100)
    tracking_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=[
            (DeliveryStatus.PENDING, "Pending"),
            (DeliveryStatus.PICKED_UP, "Picked up"),
            (DeliveryStatus.IN_TRANSIT, "In transit"),
            (DeliveryStatus.DELIVERED, "Delivered"),
            (DeliveryStatus.FAILED, "Failed"),
        ],
        default=DeliveryStatus.PENDING,
    )

    def __str__(self):
        return f"Delivery<{self.tracking_id}> for order {self.order_id}"

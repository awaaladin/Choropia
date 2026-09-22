from django.db import models

from common.models import TimeStampedModel
from orders.models import Order


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        INITIALIZED = "initialized", "Initialized"
        PAID_HELD = "paid_held", "Paid — held in escrow"
        RELEASED = "released", "Released to seller"
        REFUNDED = "refunded", "Refunded to buyer"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment")
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIALIZED)

    authorization_url = models.URLField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    auto_released = models.BooleanField(default=False)

    transfer_reference = models.CharField(max_length=100, blank=True)
    raw_webhook_payload = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Payment<{self.reference}> {self.status}"

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
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # order price, in NGN
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIALIZED)

    authorization_url = models.URLField(blank=True)  # gaxtron's hosted checkout page
    paid_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    auto_released = models.BooleanField(default=False)

    # Gaxtron settles in crypto (ETH-only as of this integration), converted from `amount` (NGN)
    # at checkout time — see payments/gaxtron.py.
    gaxtron_payment_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    crypto_amount = models.DecimalField(max_digits=36, decimal_places=18, null=True, blank=True)
    crypto_currency = models.CharField(max_length=10, blank=True, default="ETH")
    wallet_address = models.CharField(max_length=64, blank=True)
    tx_hash = models.CharField(max_length=100, blank=True)

    transfer_reference = models.CharField(max_length=100, blank=True)
    raw_webhook_payload = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Payment<{self.reference}> {self.status}"

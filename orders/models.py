from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from common.models import TimeStampedModel
from listings.models import Listing

from .state_machine import OrderStatus, validate_transition


class Order(TimeStampedModel):
    Status = OrderStatus

    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="orders")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")

    price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=OrderStatus.CHOICES, default=OrderStatus.PENDING_PAYMENT)

    delivered_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    dispute_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"Order<{self.id}> {self.status}"

    @transaction.atomic
    def transition_to(self, target_status, actor=None, note=""):
        """The only sanctioned way to change `status`. Validates against the state machine,
        stamps the relevant timestamp, and writes an audit row — all inside one transaction so
        a crash mid-way never leaves the order status and its history out of sync."""
        validate_transition(self.status, target_status)

        previous_status = self.status
        self.status = target_status

        now = timezone.now()
        if target_status == OrderStatus.DELIVERED:
            self.delivered_at = now
        elif target_status == OrderStatus.CONFIRMED:
            self.confirmed_at = now
        elif target_status == OrderStatus.COMPLETED:
            self.completed_at = now

        self.save()

        OrderStatusHistory.objects.create(
            order=self,
            from_status=previous_status,
            to_status=target_status,
            actor=actor,
            note=note,
        )
        return self


class OrderStatusHistory(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.from_status} -> {self.to_status} (order {self.order_id})"

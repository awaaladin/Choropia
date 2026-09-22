from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from common.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        FOLLOW = "follow", "New follower"
        MESSAGE = "message", "New message"
        ORDER_STATUS = "order_status", "Order status changed"
        DISPUTE = "dispute", "Dispute opened"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    verb = models.CharField(max_length=255)

    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    target_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"Notification<{self.notification_type}> to {self.recipient_id}"

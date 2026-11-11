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
        DISPATCH = "dispatch", "Delivery update"
        NEW_LISTING = "new_listing", "New listing"

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


class DeviceToken(TimeStampedModel):
    """A phone that signed in to Choropia and can receive push notifications (a Firebase registration token)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens")
    token = models.CharField(max_length=300, unique=True)
    platform = models.CharField(max_length=10, default="android")

    def __str__(self):
        return f"DeviceToken<{self.platform}> of user {self.user_id}"


class EmailSendLog(models.Model):
    """One row per email actually sent, so we can tell how many went out in the last 24 hours."""

    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)


class HeldEmail(models.Model):
    """An email waiting for room under the daily sending limit. Saved in full, sent in order once the limit opens."""

    to = models.EmailField()
    subject = models.CharField(max_length=300)
    template = models.CharField(max_length=80)
    context = models.JSONField(default=dict, blank=True)
    urgent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"HeldEmail<{self.template}> {'sent' if self.sent_at else 'held'}"

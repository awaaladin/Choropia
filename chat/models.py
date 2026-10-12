from django.conf import settings
from django.db import models

from common.models import TimeStampedModel
from listings.models import Listing


class Conversation(TimeStampedModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="conversations")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_buyer"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_seller"
    )
    order = models.OneToOneField(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversation"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["listing", "buyer"], name="unique_conversation_per_buyer_listing")
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation<{self.id}> on listing {self.listing_id}"

    def other_participant(self, user):
        return self.seller if user.id == self.buyer_id else self.buyer


class Message(TimeStampedModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(blank=True)  # may be empty when the message is only an attachment
    read_at = models.DateTimeField(null=True, blank=True)

    class AttachmentType(models.TextChoices):
        IMAGE = "image", "Image"
        AUDIO = "audio", "Voice note / audio"
        FILE = "file", "Document"

    attachment = models.FileField(upload_to="chat/", null=True, blank=True)
    attachment_type = models.CharField(max_length=10, choices=AttachmentType.choices, blank=True)
    duration_seconds = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Voice notes only.")

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message<{self.id}> in conversation {self.conversation_id}"

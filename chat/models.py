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
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message<{self.id}> in conversation {self.conversation_id}"

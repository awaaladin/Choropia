from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from common.models import TimeStampedModel
from common.public_ids import new_public_id
from listings.models import Listing

from .fields import EncryptedTextField


class Conversation(TimeStampedModel):
    listing = models.ForeignKey(
        Listing, on_delete=models.SET_NULL, related_name="conversations", null=True, blank=True
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_buyer"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_seller"
    )
    order = models.OneToOneField(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversation"
    )
    orders = models.ManyToManyField("orders.Order", blank=True, related_name="chat_conversations")
    # Random code used in links instead of the sequential id (see common/public_ids.py).
    public_id = models.CharField(max_length=10, unique=True, default=new_public_id, editable=False)
    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="direct_threads_low"
    )
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="direct_threads_high"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="unique_direct_thread_pair"),
            models.CheckConstraint(check=~Q(user_low=models.F("user_high")), name="direct_thread_distinct_users"),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation<{self.id}> between {self.user_low_id} and {self.user_high_id}"

    def save(self, *args, **kwargs):
        if self.buyer_id and self.seller_id:
            low, high = sorted((self.buyer_id, self.seller_id))
            self.user_low_id = low
            self.user_high_id = high
        super().save(*args, **kwargs)

    @classmethod
    @transaction.atomic
    def get_or_create_direct_thread(cls, user_a, user_b, listing=None, **kwargs):
        if user_a.id == user_b.id:
            raise ValueError("A conversation requires two different people.")

        low, high = sorted((user_a, user_b), key=lambda user: user.pk)
        if listing is not None:
            if listing.owner_id == user_a.id:
                buyer, seller = user_b, user_a
            elif listing.owner_id == user_b.id:
                buyer, seller = user_a, user_b
            else:
                raise ValueError("The listing owner must be a participant in the conversation.")
        else:
            buyer, seller = low, high

        defaults = {
            "listing": listing,
            "buyer": buyer,
            "seller": seller,
            **kwargs,
        }
        return cls.objects.get_or_create(user_low=low, user_high=high, defaults=defaults)

    def other_participant(self, user):
        if user.id == self.user_low_id:
            return self.user_high
        if user.id == self.user_high_id:
            return self.user_low
        raise ValueError("User is not a participant in this conversation.")


class Message(TimeStampedModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = EncryptedTextField(blank=True)  # may be empty when the message is only an attachment
    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class AttachmentType(models.TextChoices):
        IMAGE = "image", "Image"
        AUDIO = "audio", "Voice note / audio"
        FILE = "file", "Document"

    attachment = models.FileField(upload_to="chat/", null=True, blank=True)
    attachment_type = models.CharField(max_length=10, choices=AttachmentType.choices, blank=True)
    duration_seconds = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Voice notes only.")

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        OFFER = "offer", "Escrow offer"
        LISTING_REF = "listing_ref", "Listing reference"

    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    offer = models.ForeignKey("offers.Offer", on_delete=models.PROTECT, null=True, blank=True, related_name="messages")
    referenced_listing = models.ForeignKey(
        Listing, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_references"
    )
    listing_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message<{self.id}> in conversation {self.conversation_id}"

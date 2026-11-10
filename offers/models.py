"""
Escrow offers in chat.

A seller, inside a conversation, offers a listing at a price no higher than the listed price. The price, the fee and
the seller's verified status are locked on the offer when it is made (approved with the seller's transaction PIN), so
nothing that changes later (the listing price, the fee bands, verification) can alter it. The buyer pays from the
offer card; the payment goes into escrow as a normal Order/Payment (see services.py), and the card follows that order
through to release.

All money here is integer kobo.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from payments.naming import make_reference


def make_offer_reference():
    return make_reference("OFFER")


class Offer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the buyer"
        PAYMENT_PROCESSING = "payment_processing", "Payment in progress"
        PAID = "paid", "Paid into escrow"
        DECLINED = "declined", "Declined by the buyer"
        CANCELLED = "cancelled", "Cancelled by the seller"
        EXPIRED = "expired", "Expired"
        SUPERSEDED = "superseded", "Replaced by a newer offer"

    class Delivery(models.TextChoices):
        RIDER = "rider", "Choropia rider"
        SELLER_DELIVERS = "seller_delivers", "Seller delivers"
        MEETUP = "meetup", "Meet up"

    ACTIVE_STATUSES = (Status.PENDING, Status.PAYMENT_PROCESSING)
    TERMINAL_STATUSES = (Status.PAID, Status.DECLINED, Status.CANCELLED, Status.EXPIRED, Status.SUPERSEDED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Public, unique. The Paystack reference of the checkout opened from this offer starts out as this value.
    reference = models.CharField(max_length=60, unique=True, default=make_offer_reference, editable=False)

    conversation = models.ForeignKey("chat.Conversation", on_delete=models.PROTECT, related_name="offers")
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="offers")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="offers_made")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="offers_received")

    # Locked at creation.
    amount_kobo = models.PositiveBigIntegerField()
    listing_price_kobo = models.PositiveBigIntegerField(help_text="The listed price when the offer was made.")
    fee_kobo = models.PositiveBigIntegerField()
    seller_net_kobo = models.PositiveBigIntegerField()
    seller_verified_snapshot = models.BooleanField()
    allowed_delivery_methods = models.JSONField(default=list)
    note = models.CharField(max_length=300, blank=True)

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    # Chosen by the buyer at payment.
    delivery_method = models.CharField(max_length=20, choices=Delivery.choices, blank=True)
    delivery_fee_kobo = models.PositiveBigIntegerField(default=0)
    # The escrow order opened when the buyer started paying. related_name lets a Payout find the locked fee.
    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, null=True, blank=True, related_name="source_offer"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One live offer per (conversation, listing); a new one supersedes the old in the same transaction.
            models.UniqueConstraint(
                fields=["conversation", "listing"],
                condition=Q(status__in=["pending", "payment_processing"]),
                name="one_active_offer_per_conversation_listing",
            ),
            models.CheckConstraint(check=Q(amount_kobo__gt=0), name="offer_amount_positive"),
            models.CheckConstraint(
                check=Q(fee_kobo__lte=models.F("amount_kobo")), name="offer_fee_not_above_amount"
            ),
        ]
        indexes = [models.Index(fields=["status", "expires_at"])]

    def __str__(self):
        return f"Offer<{self.reference}> {self.status} {self.amount_kobo}k"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def total_kobo(self):
        """What the buyer is charged: the offer amount plus the rider fee if they chose one."""
        return self.amount_kobo + (self.delivery_fee_kobo or 0)


# Allow-list of offer status changes. Anything else is refused (see services.transition()).
TRANSITIONS = {
    Offer.Status.PENDING: {
        Offer.Status.PAYMENT_PROCESSING,
        Offer.Status.DECLINED,
        Offer.Status.CANCELLED,
        Offer.Status.EXPIRED,
        Offer.Status.SUPERSEDED,
    },
    # Back to PENDING when a checkout fails or is abandoned, so the buyer can try again. If money arrives after the
    # offer was closed from here it is not lost: the order is flagged for a refund (see services.py).
    Offer.Status.PAYMENT_PROCESSING: {
        Offer.Status.PAID,
        Offer.Status.PENDING,
        Offer.Status.CANCELLED,
        Offer.Status.EXPIRED,
        Offer.Status.SUPERSEDED,
    },
    Offer.Status.PAID: set(),
    Offer.Status.DECLINED: set(),
    Offer.Status.CANCELLED: set(),
    Offer.Status.EXPIRED: set(),
    Offer.Status.SUPERSEDED: set(),
}


class OfferEvent(models.Model):
    """Append-only audit trail: every status change of every offer, who did it and why."""

    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name="events")
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.offer_id}: {self.from_status or '-'} -> {self.to_status}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Offer events are append-only.")
        super().save(*args, **kwargs)


class HandoverCode(models.Model):
    """The buyer's 6-digit code for an offer order handed over without a rider (meet-up, or the seller delivers).
    The buyer tells the seller the code once they hold the item; the seller enters it and escrow is released.
    Stored hashed for checking, plus an encrypted copy (dispatch/crypto.py key) so the buyer can see it again.
    Rider orders use the dispatch app's code instead, which the rider enters."""

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="offer_handover")
    code_hash = models.CharField(max_length=128)
    code_encrypted = models.BinaryField(null=True, blank=True, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"HandoverCode<order {self.order_id}>"

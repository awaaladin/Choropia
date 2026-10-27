"""Dispatch: independent delivery drivers.

The flow, end to end:
  driver applies + uploads documents (encrypted) -> staff approve -> driver publishes route prices
  ("from area A to area B = N naira") -> seller turns delivery on for a listing and picks one or more
  drivers -> buyer picks a destination and a price at checkout and pays once, on Choropia ->
  every selected driver is told; the first to accept gets the job -> pickup -> delivery, confirmed
  with a photo and the buyer's handover code -> escrow is released to the seller and the driver.
"""
from django.conf import settings
from django.db import models
from django.utils.text import slugify

from common.models import TimeStampedModel


class Area(TimeStampedModel):
    """A neighbourhood drivers serve. Seeded with common Uyo areas; anyone can add a missing one."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    is_active = models.BooleanField(default=True, help_text="Untick to hide a duplicate or inappropriate area.")
    is_seed = models.BooleanField(default=False)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class DriverProfile(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    class Vehicle(models.TextChoices):
        BIKE = "bike", "Motorbike"
        TRICYCLE = "tricycle", "Tricycle (keke)"
        CAR = "car", "Car"
        VAN = "van", "Van / bus"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="driver_profile")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    whatsapp = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=12, choices=Vehicle.choices)
    plate_number = models.CharField(max_length=20, blank=True)
    guarantor_name = models.CharField(max_length=150)
    guarantor_phone = models.CharField(max_length=20)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    review_note = models.CharField(max_length=500, blank=True, help_text="Shown to the driver if rejected or suspended.")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    available = models.BooleanField(default=True, help_text="The driver can switch off to stop getting new job alerts.")
    terms_accepted_version = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def public_name(self):
        first, *rest = self.full_name.split() or ["Driver"]
        return f"{first} {rest[-1][0]}." if rest else first


class DriverDocument(TimeStampedModel):
    class Kind(models.TextChoices):
        PASSPORT_PHOTO = "passport_photo", "Passport photograph"
        ID_CARD = "id_card", "Driver licence or national ID"
        GUARANTOR = "guarantor", "Guarantor form / ID"
        VEHICLE_PAPERS = "vehicle_papers", "Vehicle papers"

    REQUIRED = (Kind.PASSPORT_PHOTO, Kind.ID_CARD, Kind.GUARANTOR, Kind.VEHICLE_PAPERS)

    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    content_type = models.CharField(max_length=40)
    size_bytes = models.PositiveIntegerField()
    # Only ever the encrypted bytes (see dispatch/crypto.py); never plain file content.
    encrypted_data = models.BinaryField(editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["driver", "kind"], name="one_document_per_kind")]

    def __str__(self):
        return f"{self.get_kind_display()} of driver {self.driver_id}"


class DocumentAccessLog(models.Model):
    """Who opened which identity document, and when. Kept for accountability under data-protection law."""

    document = models.ForeignKey(DriverDocument, on_delete=models.CASCADE, related_name="access_log")
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]


class DriverRoute(TimeStampedModel):
    """A fixed price: this driver takes a parcel from one area to another for this amount."""

    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name="routes")
    from_area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="routes_from")
    to_area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="routes_to")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["driver", "from_area", "to_area"], name="one_price_per_route")]
        ordering = ["from_area__name", "to_area__name"]

    def __str__(self):
        return f"{self.from_area} -> {self.to_area}: {self.price}"


class ListingDelivery(TimeStampedModel):
    """How a listing can be delivered. Delivery is optional: without this (or with enabled=False) the buyer
    and seller arrange handover themselves, exactly as before."""

    class Payer(models.TextChoices):
        BUYER = "buyer", "Buyer pays delivery"
        SELLER = "seller", "I pay delivery"
        SPLIT = "split", "Split 50/50"

    listing = models.OneToOneField("listings.Listing", on_delete=models.CASCADE, related_name="delivery_options")
    enabled = models.BooleanField(default=True)
    payer = models.CharField(max_length=10, choices=Payer.choices, default=Payer.BUYER)
    pickup_area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="+")
    drivers = models.ManyToManyField(DriverProfile, related_name="chosen_for_listings", blank=True)

    def __str__(self):
        return f"Delivery options for listing {self.listing_id}"


class OrderDelivery(TimeStampedModel):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Waiting for payment"
        OFFERED = "offered", "Waiting for a driver"
        ACCEPTED = "accepted", "Driver assigned"
        PICKED_UP = "picked_up", "On its way"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="dispatch_delivery")
    pickup_area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="+")
    dropoff_area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="+")
    # The exact address: shown only to the assigned driver (and the buyer who wrote it).
    dropoff_note = models.CharField(max_length=300, blank=True)

    payer = models.CharField(max_length=10, choices=ListingDelivery.Payer.choices)
    fee = models.DecimalField(max_digits=10, decimal_places=2)  # the whole delivery fee, fixed at checkout
    buyer_share = models.DecimalField(max_digits=10, decimal_places=2)
    seller_share = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT, db_index=True)
    driver = models.ForeignKey(DriverProfile, null=True, blank=True, on_delete=models.PROTECT, related_name="deliveries")

    # The buyer tells the driver this code in person; delivery cannot be confirmed without it.
    handover_code = models.CharField(max_length=6, blank=True)
    code_attempts = models.PositiveSmallIntegerField(default=0)

    offered_at = models.DateTimeField(null=True, blank=True)
    nudged_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    proof_photo = models.BinaryField(null=True, blank=True, editable=False)
    proof_content_type = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f"Delivery for order {self.order_id} ({self.status})"


class DeliveryOffer(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        ACCEPTED = "accepted", "Accepted"
        TAKEN = "taken", "Already accepted by another driver"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn by the seller"

    delivery = models.ForeignKey(OrderDelivery, on_delete=models.CASCADE, related_name="offers")
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name="offers")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["delivery", "driver"], name="one_offer_per_driver")]

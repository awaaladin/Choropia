from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from common.models import TimeStampedModel


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="subcategories"
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Listing(TimeStampedModel):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        USED = "used", "Used"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SOLD = "sold", "Sold"
        REMOVED = "removed", "Removed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listings",
        help_text="Set when this listing is posted under a storefront rather than a personal profile.",
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings")

    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.USED)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    sold_at = models.DateTimeField(null=True, blank=True)
    market_visible_until = models.DateTimeField(null=True, blank=True)

    location = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # "uniuyo" puts the listing on the UniUyo campus market, a tab of the marketplace for students selling to students.
    campus = models.CharField(max_length=20, blank=True, default="", db_index=True)

    views_count = models.PositiveIntegerField(default=0)
    # How many the seller has. Each paid order takes one; at zero the listing is marked sold. A refund or cancellation
    # after payment puts one back.
    quantity = models.PositiveIntegerField(default=1)
    # Set only when the seller changed the price and chose to show it: buyers then see the old price crossed out.
    previous_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status", "market_visible_until"], name="listing_market_visible"),
        ]

    def __str__(self):
        return self.title

    @classmethod
    def public_visibility_filter(cls, now=None):
        now = now or timezone.now()
        return models.Q(status=cls.Status.ACTIVE) | models.Q(
            status=cls.Status.SOLD, market_visible_until__gt=now
        )

    @property
    def seller(self):
        """Whoever the buyer is actually transacting with — the storefront if listed under one,
        otherwise the individual owner."""
        return self.merchant or self.owner


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listings/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo<{self.listing_id}:{self.order}>"

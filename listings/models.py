from django.conf import settings
from django.db import models
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

    location = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.title

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

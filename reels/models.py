from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from common.models import TimeStampedModel
from listings.models import Listing
from merchants.models import Merchant


class Reel(TimeStampedModel):
    """A short vertical video post. Optionally tied to a Listing, which makes it "shoppable" —
    the listing's price/escrow-checkout flow is reused as-is rather than reinvented here."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reels")
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reels",
        help_text="Set when this reel is posted under a storefront rather than a personal profile.",
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reels",
        help_text="If set, this reel is shoppable — it shows the listing's price and a buy button.",
    )

    video = models.FileField(
        upload_to="reels/",
        validators=[FileExtensionValidator(["mp4", "mov", "webm"])],
    )
    caption = models.CharField(max_length=500, blank=True)

    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reel<{self.id}> by {self.owner_id}"

    @property
    def creator(self):
        return self.merchant or self.owner


class ReelLike(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reel_likes")
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="likes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "reel"], name="unique_reel_like")]

    def __str__(self):
        return f"{self.user} likes reel {self.reel_id}"


class ReelComment(TimeStampedModel):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reel_comments")
    body = models.CharField(max_length=500)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"ReelComment<{self.id}> on {self.reel_id}"

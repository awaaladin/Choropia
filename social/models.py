from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from common.models import TimeStampedModel
from listings.models import Listing


class Follow(TimeStampedModel):
    """A follower relationship where the target is either a User or a Merchant storefront."""

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "content_type", "object_id"], name="unique_follow_target"
            )
        ]

    def clean(self):
        from accounts.models import User

        if self.content_type.model_class() is User and self.object_id == self.follower_id:
            raise ValidationError("You cannot follow yourself.")

    def __str__(self):
        return f"{self.follower} -> {self.content_type.model}:{self.object_id}"


class Like(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="likes")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "listing"], name="unique_listing_like")
        ]

    def __str__(self):
        return f"{self.user} likes {self.listing_id}"


class Comment(TimeStampedModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.CharField(max_length=500)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment<{self.id}> on {self.listing_id}"

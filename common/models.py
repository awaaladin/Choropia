import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base adding created_at/updated_at to every model that needs them."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """Abstract base for models that should use UUID primary keys (e.g. public-facing records)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

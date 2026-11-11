from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from common.models import TimeStampedModel


class ContactMessage(TimeStampedModel):
    """A message sent through the Contact page. Saved first so nothing is lost even if the email to staff fails."""

    class Topic(models.TextChoices):
        QUESTION = "question", "A question"
        PROBLEM = "problem", "A problem or complaint"
        REPORT = "report", "Reporting someone or something"
        OTHER = "other", "Something else"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    topic = models.CharField(max_length=10, choices=Topic.choices, default=Topic.QUESTION)
    message = models.TextField(max_length=3000)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    handled = models.BooleanField(default=False)
    # Our answer, sent from the staff Inbox by email.
    reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_topic_display()} from {self.email}"


class Report(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        REVIEWED = "reviewed", "Reviewed"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_filed"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report<{self.content_type.model}:{self.object_id}> {self.status}"

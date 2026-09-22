from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class MerchantApplication(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="merchant_applications"
    )
    business_name = models.CharField(max_length=150)
    business_description = models.TextField(blank=True)
    business_phone = models.CharField(max_length=20)
    business_address = models.CharField(max_length=255)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_merchant_applications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.business_name} ({self.status})"

    def approve(self, reviewer):
        from django.utils import timezone

        if self.status == self.Status.APPROVED:
            return self.merchant

        self.status = self.Status.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        merchant, _ = Merchant.objects.get_or_create(
            user=self.applicant,
            defaults={
                "application": self,
                "business_name": self.business_name,
                "description": self.business_description,
                "location": self.business_address,
            },
        )
        return merchant

    def reject(self, reviewer, reason=""):
        from django.utils import timezone

        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])


class Merchant(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="merchant"
    )
    application = models.OneToOneField(
        MerchantApplication, on_delete=models.SET_NULL, null=True, blank=True, related_name="merchant"
    )
    business_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="merchant_logos/", null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return self.business_name

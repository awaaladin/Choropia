from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Everything staff do that touches money or private data, in one place: who, what, when, to what.
    Written by the staff panel; never edited or deleted from it."""

    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=80, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.action} {self.target}"


class SiteSettings(models.Model):
    """One row of switches the owner can flip from the staff panel."""

    seller_approval_required = models.BooleanField(
        default=False,
        help_text="When on, only approved sellers (and staff) can post listings. Everyone can still browse and buy.",
    )

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ApprovedSeller(models.Model):
    """A seller the owner has let in during the pilot, with what they sell (for example Gadgets or Fashion)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="approved_seller")
    focus = models.CharField(max_length=40, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_id} ({self.focus})"


def may_sell(user) -> bool:
    """False only when the pilot is invite-only and this person has not been approved."""
    if not SiteSettings.load().seller_approval_required:
        return True
    return bool(user.is_authenticated and (user.is_staff or ApprovedSeller.objects.filter(user=user).exists()))


class KeyBackup(models.Model):
    """The driver-document encryption key, locked with a second passphrase (see staffpanel/keybackup.py). Without this, losing
    the DOCUMENT_ENCRYPTION_KEY setting would make every stored identity document unreadable for good."""

    salt = models.BinaryField()
    iterations = models.PositiveIntegerField()
    wrapped_key = models.BinaryField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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

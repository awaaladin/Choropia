from django.conf import settings
from django.db import models


class Acceptance(models.Model):
    """Proof that a person agreed to a version of a legal document, and when. Kept so we can show consent."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="legal_acceptances")
    document = models.CharField(max_length=30)  # terms | privacy | driver_terms
    version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-accepted_at"]
        indexes = [models.Index(fields=["user", "document"])]

    def __str__(self):
        return f"{self.user_id} accepted {self.document} {self.version}"

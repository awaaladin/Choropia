from django.conf import settings

from .models import Acceptance

DOCUMENTS = {
    "terms": "Terms and Conditions",
    "privacy": "Privacy Policy",
    "driver_terms": "Driver Terms",
}


def _client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None)


def record_acceptance(user, documents, request=None):
    """Stores that `user` accepted the current version of each document (once per version)."""
    ip = _client_ip(request)
    for document in documents:
        if document not in DOCUMENTS:
            continue
        Acceptance.objects.get_or_create(
            user=user, document=document, version=settings.LEGAL_VERSION, defaults={"ip_address": ip}
        )


def has_accepted_current(user, document):
    return Acceptance.objects.filter(user=user, document=document, version=settings.LEGAL_VERSION).exists()

from django.conf import settings


def choropia_settings(request):
    """Exposes the API base URLs to every template, so page JS knows where to call."""
    return {
        "CHOROPIA_API_BASE_URL": settings.CHOROPIA_API_BASE_URL,
        "CHOROPIA_WS_BASE_URL": settings.CHOROPIA_WS_BASE_URL,
    }

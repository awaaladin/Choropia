"""Who is online: every authenticated API call records "last seen", at most once every 30 seconds per person."""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication

ONLINE_WINDOW = timedelta(seconds=90)


def is_online(last_seen):
    return bool(last_seen and timezone.now() - last_seen <= ONLINE_WINDOW)


class PresenceJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user = result[0]
            key = f"seen-{user.pk}"
            if cache.add(key, 1, 30):
                try:
                    from accounts.models import Profile

                    Profile.objects.filter(user_id=user.pk).update(last_seen_at=timezone.now())
                except Exception:  # noqa: BLE001 - presence must never break a request
                    pass
        return result

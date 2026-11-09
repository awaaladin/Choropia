from .base import *  # noqa: F401,F403
from .base import env, env_bool, env_int, env_list

DEBUG = False

# Always allow the stable production domain. Add custom domains or a specific
# preview URL through DJANGO_ALLOWED_HOSTS without replacing the stable host.
ALLOWED_HOSTS = ["choropia.vercel.app", *env_list("DJANGO_ALLOWED_HOSTS")]

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY or "insecure" in SECRET_KEY.lower():
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production to a long random value")
if len(SECRET_KEY) < 50:
    # Not fatal (that would take the site down), but a short key is a real weakness: replace it with `python -c "import secrets;print(secrets.token_urlsafe(64))"`.
    import logging

    logging.getLogger("django.security").warning("DJANGO_SECRET_KEY is shorter than 50 characters; rotate it.")

if not CHAT_MESSAGE_ENCRYPTION_KEYS:
    raise RuntimeError("CHAT_MESSAGE_ENCRYPTION_KEYS must be set before production chat can start.")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")

# Rate limiting (DRF throttles) lives in the cache. base.py defaults REDIS_URL to
# redis://localhost, which doesn't exist on serverless hosts, so every throttled endpoint
# (login, register, password reset) would 500. Only use Redis when it is actually configured.
if not env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    # Same reason for the Channels layer: chat/notification pushes go through it. In-memory means
    # nothing reaches WebSocket clients held by another process — set REDIS_URL (shared with the
    # Docker realtime host) for cross-process delivery.
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# TLS is terminated by the host's proxy (Vercel, Caddy in docker-compose.prod.yml); without this
# SECURE_SSL_REDIRECT sees every proxied request as plain http and redirects forever.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
# Follows the environment (base.py already decided): STARTTLS on 587, or implicit SSL on 465, never both.
# This used to be a hard-coded True, which clashed with EMAIL_USE_SSL=true and made every send fail.
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True) and not EMAIL_USE_SSL
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

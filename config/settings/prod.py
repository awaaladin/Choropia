from .base import *  # noqa: F401,F403
from .base import env, env_bool, env_int, env_list

DEBUG = False

# Always allow the stable production domain. Add custom domains or a specific
# preview URL through DJANGO_ALLOWED_HOSTS without replacing the stable host.
ALLOWED_HOSTS = ["choropia.vercel.app", *env_list("DJANGO_ALLOWED_HOSTS")]

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")

# Rate limiting (DRF throttles) lives in the cache. base.py defaults REDIS_URL to
# redis://localhost, which doesn't exist on serverless hosts, so every throttled endpoint
# (login, register, password reset) would 500. Only use Redis when it is actually configured.
if not env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

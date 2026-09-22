from .base import *  # noqa: F401,F403
from .base import env, env_bool, env_list

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# If REDIS_URL isn't explicitly set (e.g. running `manage.py runserver` directly on a machine
# with no Redis, rather than via docker-compose), fall back to in-process backends so the API
# and admin still work. Chat/notification WebSocket fan-out and Celery task dispatch still need
# a real Redis — see README "Local setup (without Docker)".
if not env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CELERY_TASK_ALWAYS_EAGER = True

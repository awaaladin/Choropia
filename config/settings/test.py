"""
Settings used by the test runner: fast SQLite DB, synchronous Celery,
in-memory channel layer. Keeps `manage.py test` runnable with no
docker services up.
"""
from .base import *  # noqa: F401,F403

SECRET_KEY = "test-only-key-not-used-anywhere-else-0123456789abcdef0123456789abcdef"
DEBUG = False
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CELERY_ALWAYS_EAGER = True
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Rate limits exist to slow abuse in production; in the test suite they only cause order-dependent
# failures (every test that logs in shares one in-memory counter). Production settings are untouched.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {name: "10000/min" for name in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]},  # noqa: F405
}

# A throwaway key so encrypted-document tests run; real keys only ever come from the environment.
DOCUMENT_ENCRYPTION_KEYS = "0g4yZ3m0c0nF0c1c8Jr3Oq8o2m3m3VbYQb0xv4b2xGc="
CHAT_MESSAGE_ENCRYPTION_KEYS = DOCUMENT_ENCRYPTION_KEYS

# Staff alert emails are tested on purpose (staffpanel/tests_alerts.py); elsewhere they would only add noise to email counts.
STAFF_ALERTS_ENABLED = False

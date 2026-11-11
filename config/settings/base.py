"""
Base settings shared by every environment. Nothing environment-specific
(debug flags, allowed hosts, secret values) lives here — see dev.py / prod.py.
"""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    """Return an environment setting, treating blank deployment values as unset."""
    value = os.environ.get(key)
    return default if value is None or not value.strip() else value


def env_bool(key, default=False):
    val = env(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def env_int(key, default):
    """Read an integer setting, treating an empty deployment variable as unset."""
    value = env(key)
    return default if value is None else int(value)


def env_list(key, default=""):
    val = env(key, default)
    return [item.strip() for item in val.split(",") if item.strip()]


# No fallback value on purpose: dev.py and test.py make a throwaway key, prod.py refuses to start without a strong one.
SECRET_KEY = env("DJANGO_SECRET_KEY", "")

AUTH_USER_MODEL = "accounts.User"

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "channels",
    "storages",
]

LOCAL_APPS = [
    "common",
    "core",
    "accounts",
    "social",
    "listings",
    "merchants",
    "reels",
    "chat",
    "orders",
    "payments",
    "offers",
    "delivery",
    "reviews",
    "notifications",
    "moderation",
    "dispatch",
    "legal",
    "staffpanel",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "common.web_session.WebSessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database ---------------------------------------------------------
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", "sqlite:///" + str(BASE_DIR / "db.sqlite3")),
        conn_max_age=600,
    )
}

# --- Password validation ------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N ---------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# --- Static / media -------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Serves static files (Django admin's CSS/JS, drf-spectacular's Swagger UI) straight from each
# app's static/ dir, with no collectstatic build step required — needed because Vercel's Python
# builder only runs `pip install`, not `npm run build` + `collectstatic` the way Docker does.
WHITENOISE_USE_FINDERS = True
# Serves the built React app (frontend/dist/*) at the URL root — e.g. /assets/index-xxx.js,
# /favicon-32.png — exactly matching how Vite's build references them. Paths that don't match a
# real file here (actual app routes like /marketplace) fall through to core.views.SPAView,
# which returns index.html so React Router can take over client-side. Requires `npm run build`
# to have been run in frontend/ — see core/views.py.
_frontend_dist = BASE_DIR / "frontend" / "dist"
if _frontend_dist.is_dir():
    WHITENOISE_ROOT = _frontend_dist

USE_S3 = env_bool("USE_S3", False)

# Vercel Blob: `vercel blob create-store` connects a store to the project and sets this token.
# BLOB_PUBLIC_BASE_URL is the store's public host, e.g. https://<store-id>.public.blob.vercel-storage.com
BLOB_READ_WRITE_TOKEN = env("BLOB_READ_WRITE_TOKEN", "")
BLOB_PUBLIC_BASE_URL = env("BLOB_PUBLIC_BASE_URL", "")

if USE_S3:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "eu-west-1")
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", None)
    # Supabase Storage and Cloudflare R2 reject per-object ACLs and need path-style URLs: for those
    # set AWS_DEFAULT_ACL=none and make the bucket public instead. Plain AWS keeps "public-read".
    _acl = env("AWS_DEFAULT_ACL", "public-read")
    AWS_DEFAULT_ACL = None if _acl.lower() in ("none", "private-bucket") else _acl
    AWS_S3_ADDRESSING_STYLE = env("AWS_S3_ADDRESSING_STYLE", "auto")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    MEDIA_URL = env("MEDIA_URL", f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/")
elif BLOB_READ_WRITE_TOKEN:
    STORAGES = {
        "default": {"BACKEND": "common.blob_storage.VercelBlobStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    MEDIA_URL = (BLOB_PUBLIC_BASE_URL.rstrip("/") + "/") if BLOB_PUBLIC_BASE_URL else "media/"
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    MEDIA_URL = "media/"
    MEDIA_ROOT = BASE_DIR / "mediafiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sign in with Google: the OAuth *web* client id the app/web request ID tokens for. Blank = the
# /auth/google/ endpoint answers 503 and the clients hide the button.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", "")
SOLD_LISTING_DURATIONS = (1, 3, 7, 14, 30)
SOLD_LISTING_DEFAULT_DAYS = env_int("SOLD_LISTING_DEFAULT_DAYS", 3)

# --- DRF ------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Everything is limited per caller; the scopes below tighten the actions that are easiest to abuse.
        "anon": "120/min",
        "user": "400/min",
        "chat-send": "60/min",
        "comments": "30/min",
        "social": "120/hour",
        "guest-likes": "30/hour",
        "guest-like-token": "20/hour",
        "orders": "30/hour",
        "reviews": "30/hour",
        "contact": "5/hour",
        "reports": "20/hour",
        "merchant-apply": "5/day",
        "auth": "10/min",
        "listing-create": "20/hour",
        "payout-account": "20/hour",
        "otp": "20/hour",
        "dispatch-write": "60/hour",
        "avatar": "30/hour",
        "dispatch-documents": "20/hour",
        "handover-code": "30/hour",
        "pin": "20/hour",
        "offers": "60/hour",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 14)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Choropia API",
    "DESCRIPTION": (
        "Social buy-and-sell marketplace API for Choropia (Uyo pilot). "
        "Serves the Kotlin Android app and the web frontend over token auth."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1/",
}

# --- CORS -------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
# Logins use Bearer tokens (or a same-site cookie on choropia.vercel.app itself), never cross-site cookies.
CORS_ALLOW_CREDENTIALS = False

# --- Channels -----------------------------------------------------------
REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# --- Celery -------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# --- Cache (Redis) --------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# --- Payments ----------------------------------------------------------------
# Which provider new checkouts use: "paystack" or "gaxtron". Defaults to Paystack once its key
# is set, so a deployment without one keeps working on Gaxtron. The Paystack account is shared
# with other apps; see payments/naming.py for how Choropia's payments are labelled on it.
# PAYSTACK_API is accepted as an alias: the shared account's key is stored under that name in the
# repo owner's local .env, and the webhook router calls it PAYSTACK_SECRET_KEY.
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY", "") or env("PAYSTACK_API", "")
PAYSTACK_BASE_URL = env("PAYSTACK_BASE_URL", "https://api.paystack.co")
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", "paystack" if PAYSTACK_SECRET_KEY else "gaxtron")
# Public web origin Paystack sends the buyer back to (to /orders/<id>) after checkout.
CHOROPIA_SITE_URL = env("CHOROPIA_SITE_URL", "http://localhost:5173")

# --- Seller payouts ----------------------------------------------------------
# When an order's escrow is released the seller is paid by bank transfer (Paystack Transfers) and
# Choropia keeps this commission. See payments/payouts.py.
#
# The fee is banded per slice of the price, lower for sellers staff have verified; the bands live in
# payments/fees.py (one module, unit-tested). Only the minimum is a setting. Integer kobo.
MIN_FEE_KOBO = env_int("MIN_FEE_KOBO", 20_000)  # ₦200

# --- Escrow offers in chat (see the offers app) -------------------------------------------------
OFFER_TTL_HOURS = env_int("OFFER_TTL_HOURS", 24)
# A checkout opened from an offer that hasn't been paid after this long frees the offer again (the seller can then
# cancel or replace it). Paying the old link later still works if the offer is open, or is refunded if it isn't.
OFFER_CHECKOUT_TIMEOUT_MINUTES = env_int("OFFER_CHECKOUT_TIMEOUT_MINUTES", 30)
# An offer may be at most this percent of the listing price (100 = a seller can lower a price, never raise it).
OFFER_MAX_PERCENT_OF_LISTING = env_int("OFFER_MAX_PERCENT_OF_LISTING", 100)
# Transaction PIN: digits, and a lock after too many wrong tries.
TRANSACTION_PIN_LENGTH = 4
PIN_MAX_ATTEMPTS = env_int("PIN_MAX_ATTEMPTS", 5)
PIN_LOCK_MINUTES = env_int("PIN_LOCK_MINUTES", 15)
# Which PayoutService pays sellers and drivers (payments/payout_service.py). Off (the default) = ManualPayoutService:
# releases create payout records in the staff panel queue and staff pay them by hand. On = Paystack Transfers, only
# once Paystack has enabled Transfers on the account (Registered Business / KYC).
PAYOUTS_ENABLED = env_bool("PAYOUTS_ENABLED", False)
# A single payout above this (NGN, after commission) is held for a person to approve.
PAYOUT_MAX_NGN = Decimal(env("PAYOUT_MAX_NGN", "2000000"))

ADMIN_URL = env("ADMIN_URL", "admin/").lstrip("/").rstrip("/") + "/"

# --- Dispatch (delivery by independent drivers) ----------------------------------------------
# Choropia keeps this percent of the delivery fee (the driver is paid the rest).
DRIVER_COMMISSION_PERCENT = Decimal(env("DRIVER_COMMISSION_PERCENT", "2.5"))
# If no driver has accepted a paid delivery after this long, the seller is nudged to add more drivers.
DISPATCH_NUDGE_HOURS = env_int("DISPATCH_NUDGE_HOURS", 2)
# Drivers' identity documents are encrypted with this key before they are stored (Fernet key; make one with
# `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). Keep a backup:
# without it the documents cannot be read again. Multiple keys (comma separated) allow rotation: the first
# encrypts, all can decrypt.
DOCUMENT_ENCRYPTION_KEYS = env("DOCUMENT_ENCRYPTION_KEY", "")
CHAT_MESSAGE_ENCRYPTION_KEYS = env("CHAT_MESSAGE_ENCRYPTION_KEYS", "")
CHAT_MESSAGE_ENCRYPTION_KEYS_ADDITIONAL = env("CHAT_MESSAGE_ENCRYPTION_KEYS_ADDITIONAL", "")
DOCUMENT_MAX_BYTES = env_int("DOCUMENT_MAX_BYTES", 3 * 1024 * 1024)
PROOF_PHOTO_MAX_BYTES = env_int("PROOF_PHOTO_MAX_BYTES", 3 * 1024 * 1024)
HANDOVER_MAX_ATTEMPTS = env_int("HANDOVER_MAX_ATTEMPTS", 5)
# Identity documents of drivers who were rejected are deleted this many days after the decision (data-protection retention).
REJECTED_DOCUMENT_RETENTION_DAYS = env_int("REJECTED_DOCUMENT_RETENTION_DAYS", 30)
# The current version of the Terms and Privacy Policy (see the legal app); bump when the text changes.
LEGAL_VERSION = env("LEGAL_VERSION", "2026-10-27")
LEGAL_COMPANY_NAME = env("LEGAL_COMPANY_NAME", "Choropia")
LEGAL_CONTACT_EMAIL = env("LEGAL_CONTACT_EMAIL", "")  # shown in the legal pages when set
# After this many failed transfer attempts a payout is flagged for a person instead of retried.
PAYOUT_MAX_ATTEMPTS = int(env("PAYOUT_MAX_ATTEMPTS", "5"))
# Shared secret for the scheduled-jobs endpoint (Vercel Cron sends it as a Bearer token).
CRON_SECRET = env("CRON_SECRET", "")

# --- Gaxtron (crypto escrow payments, the alternative to Paystack) --------
# See payments/gaxtron.py for the full integration notes (currency conversion, the SSRF
# constraint on webhook callbacks, and the escrow/payout gap this inherits from Paystack).
GAXTRON_API_KEY = env("GAXTRON_API_KEY", "")
GAXTRON_BASE_URL = env("GAXTRON_BASE_URL", "http://127.0.0.1:9000")
GAXTRON_WEBHOOK_SECRET = env("GAXTRON_WEBHOOK_SECRET", "")
# Gaxtron settles in ETH only; Choropia lists prices in NGN. There's no live forex feed wired
# in, so this hand-set NGN-per-USD rate combines with gaxtron's own /markets/prices (ETH/USD)
# to convert an order's price at checkout time — treat it as an approximation.
GAXTRON_NGN_PER_USD = Decimal(env("GAXTRON_NGN_PER_USD", "1600"))
# Where gaxtron POSTs payment-confirmed events. Gaxtron's own SSRF guard rejects
# localhost/private hosts, so this must resolve publicly even in dev — Choropia doesn't
# depend on it arriving either way (payments.tasks.poll_gaxtron_payments_task polls gaxtron
# directly), so the dev default is a harmless public echo endpoint, not a real receiver.
GAXTRON_CALLBACK_URL = env("GAXTRON_CALLBACK_URL", "https://httpbin.org/post")

# --- Choropia business rules ------------------------------------------
ESCROW_AUTO_RELEASE_DAYS = env_int("ESCROW_AUTO_RELEASE_DAYS", 3)
# A paid order the seller has not dispatched within this many days is refunded to the buyer automatically.
ESCROW_DISPATCH_DEADLINE_DAYS = env_int("ESCROW_DISPATCH_DEADLINE_DAYS", 7)
PLATFORM_PILOT_CITY = env("PLATFORM_PILOT_CITY", "Uyo")

DELIVERY_PROVIDER = env("DELIVERY_PROVIDER", "delivery.providers.mock.MockDeliveryProvider")

# --- Email (password reset) -------------------------------------------------
# Dev and test override the backend (console / locmem); production sets real SMTP via env.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
# Resend: smtp.resend.com on 465 with EMAIL_USE_SSL=true (and EMAIL_USE_TLS=false), user "resend",
# password = the Resend API key. Some networks block 587; 465 is the dependable one.
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
# Django refuses to start a connection if both are true; implicit SSL (port 465) wins, so a stale
# EMAIL_USE_TLS=true left in the environment can never break email.
EMAIL_USE_TLS = EMAIL_USE_TLS and not EMAIL_USE_SSL
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)  # Vercel stops a function at 10 s; never hang on SMTP
# Must be on a domain verified with the email provider, or it will refuse to send.
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Choropia <no-reply@choropia.local>")
# Who is emailed when something needs a person (new driver, dispute, money to hand over). Comma separated.
# A seller can be reviewed only after posting at least this many listings (so one-off posters are not rated).
REVIEW_MIN_LISTINGS = env_int("REVIEW_MIN_LISTINGS", 2)
STAFF_ALERT_EMAILS = [e.strip() for e in env("STAFF_ALERT_EMAILS", "hiexecontact@gmail.com").split(",") if e.strip()]
STAFF_ALERTS_ENABLED = env_bool("STAFF_ALERTS_ENABLED", True)
SUPPORT_EMAIL = env("SUPPORT_EMAIL", "") or DEFAULT_FROM_EMAIL.rpartition("<")[2].rstrip(">").strip()

# Email one-time codes (accounts/otp.py)
# Gmail allows about 500 a day; everyday emails pause at 85% of this and wait in HeldEmail until there is room.
EMAIL_DAILY_LIMIT = env_int("EMAIL_DAILY_LIMIT", 400)
EMAIL_OTP_MINUTES = env_int("EMAIL_OTP_MINUTES", 10)
EMAIL_OTP_MAX_ATTEMPTS = env_int("EMAIL_OTP_MAX_ATTEMPTS", 5)
EMAIL_OTP_RESEND_SECONDS = env_int("EMAIL_OTP_RESEND_SECONDS", 60)
# When true, a seller must have a verified email before saving a payout bank account.
REQUIRE_VERIFIED_EMAIL_FOR_PAYOUT = env_bool("REQUIRE_VERIFIED_EMAIL_FOR_PAYOUT", False)
# Where the emailed link points; the web page reads ?uid=&token= and posts them to the API.
PASSWORD_RESET_URL_BASE = env("PASSWORD_RESET_URL_BASE", "http://localhost:8000/reset-password/")

# --- Web frontend (the `core` app) -----------------------------------------
# Relative by default: the web pages and the API are now served from the same origin, so the
# page JS can just call fetch("/api/v1/...") without needing an absolute host. Override with a
# full URL only if the web pages are ever served from a different origin than the API.
CHOROPIA_API_BASE_URL = env("CHOROPIA_API_BASE_URL", "/api/v1")
CHOROPIA_WS_BASE_URL = env("CHOROPIA_WS_BASE_URL", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}

# Public SHA-256 fingerprint(s) of the app signing certificate: lets Android open choropia.vercel.app links in the app.
# Firebase service-account key (one line of JSON) for phone push notifications. Empty = push is off.
FIREBASE_SERVICE_ACCOUNT_JSON = env("FIREBASE_SERVICE_ACCOUNT_JSON", "")
ANDROID_MIN_VERSION_CODE = env_int("ANDROID_MIN_VERSION_CODE", 0)
ANDROID_CERT_FINGERPRINTS = ["D0:81:99:31:3A:FB:F5:58:1B:61:B8:27:1B:FE:BB:5C:2F:DC:4C:D5:17:A0:64:B2:69:E8:10:E7:41:DA:DE:84"]

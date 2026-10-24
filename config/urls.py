from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import accounts.urls
import chat.urls
import core.urls
import delivery.urls
import listings.urls
import merchants.urls
import moderation.urls
import notifications.urls
import orders.urls
import payments.urls
import reels.urls
import reviews.urls
import social.urls
from common import app_download
from payments.webhook_router import PaystackRouterView

api_v1_patterns = (
    accounts.urls.urlpatterns
    + social.urls.urlpatterns
    + listings.urls.urlpatterns
    + merchants.urls.urlpatterns
    + reels.urls.urlpatterns
    + chat.urls.urlpatterns
    + orders.urls.urlpatterns
    + payments.urls.urlpatterns
    + delivery.urls.urlpatterns
    + reviews.urls.urlpatterns
    + notifications.urls.urlpatterns
    + moderation.urls.urlpatterns
)

urlpatterns = [

    path("api/v1/", include(api_v1_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # The Android app lives in object storage; this path (linked from the landing page) redirects to it.
    # Must come before core.urls, whose catch-all would otherwise answer with the SPA shell.
    path("downloads/choropia.apk", app_download.apk_redirect, name="android-apk"),
    path("api/v1/app/android/", app_download.AndroidAppInfoView.as_view(), name="android-app-info"),
    # The shared Paystack account's single webhook: handles Choropia's events and forwards the other
    # products' (see payments/webhook_router.py). Point the Paystack dashboard webhook URL here.
    re_path(r"^api/paystack-webhook/?$", PaystackRouterView.as_view(), name="paystack-router"),
    path("", include(core.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

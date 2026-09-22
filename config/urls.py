from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
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
import reviews.urls
import social.urls

api_v1_patterns = (
    accounts.urls.urlpatterns
    + social.urls.urlpatterns
    + listings.urls.urlpatterns
    + merchants.urls.urlpatterns
    + chat.urls.urlpatterns
    + orders.urls.urlpatterns
    + payments.urls.urlpatterns
    + delivery.urls.urlpatterns
    + reviews.urls.urlpatterns
    + notifications.urls.urlpatterns
    + moderation.urls.urlpatterns
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include(core.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

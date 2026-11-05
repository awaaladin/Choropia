from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import DeviceTokenView, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [path("notifications/devices/", DeviceTokenView.as_view(), name="notification-devices"), *router.urls]

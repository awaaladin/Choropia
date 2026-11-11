from rest_framework.routers import DefaultRouter

from django.urls import path

from .contact import ContactView
from .views import ReportViewSet

router = DefaultRouter()
router.register("reports", ReportViewSet, basename="report")

urlpatterns = [path("contact/", ContactView.as_view(), name="contact"), *router.urls]

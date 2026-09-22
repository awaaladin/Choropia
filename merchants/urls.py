from rest_framework.routers import DefaultRouter

from .views import MerchantApplicationViewSet, MerchantViewSet

router = DefaultRouter()
router.register("merchant-applications", MerchantApplicationViewSet, basename="merchant-application")
router.register("merchants", MerchantViewSet, basename="merchant")

urlpatterns = router.urls

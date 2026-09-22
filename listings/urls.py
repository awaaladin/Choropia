from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ListingViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .views import ReelCommentViewSet, ReelLikeViewSet, ReelViewSet

router = DefaultRouter()
router.register("reels", ReelViewSet, basename="reel")
router.register("reel-likes", ReelLikeViewSet, basename="reel-like")
router.register("reel-comments", ReelCommentViewSet, basename="reel-comment")

urlpatterns = router.urls

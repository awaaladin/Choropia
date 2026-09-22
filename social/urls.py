from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CommentViewSet, FeedView, FollowViewSet, LikeViewSet

router = DefaultRouter()
router.register("follows", FollowViewSet, basename="follow")
router.register("comments", CommentViewSet, basename="comment")
router.register("likes", LikeViewSet, basename="like")

urlpatterns = [
    path("feed/", FeedView.as_view(), name="feed"),
] + router.urls

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CommentViewSet,
    FeedView,
    FollowViewSet,
    GuestLikeTokenView,
    GuestLikeView,
    LikeViewSet,
)

router = DefaultRouter()
router.register("follows", FollowViewSet, basename="follow")
router.register("comments", CommentViewSet, basename="comment")
router.register("likes", LikeViewSet, basename="like")

urlpatterns = [
    path("feed/", FeedView.as_view(), name="feed"),
    path("likes/guest-token/", GuestLikeTokenView.as_view(), name="guest-like-token"),
    path("likes/guest/", GuestLikeView.as_view(), name="guest-like"),
] + router.urls

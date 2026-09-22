from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from listings.models import Listing
from listings.serializers import ListingListSerializer
from merchants.models import Merchant

from .models import Comment, Follow, Like
from .serializers import CommentSerializer, FollowSerializer, LikeSerializer


class FollowViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Follow.objects.filter(follower=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError("Already following this target.")


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Comment.objects.select_related("author")
        listing_id = self.request.query_params.get("listing")
        if listing_id:
            qs = qs.filter(listing_id=listing_id)
        return qs


class LikeViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Like.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError("Already liked.")


class FeedView(ListAPIView):
    """Reverse-chronological mix of listings from followed accounts/storefronts plus nearby activity
    in the user's own pilot-city location."""

    serializer_class = ListingListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        followed_user_ids = Follow.objects.filter(
            follower=user, content_type=ContentType.objects.get_for_model(user.__class__)
        ).values_list("object_id", flat=True)
        followed_merchant_ids = Follow.objects.filter(
            follower=user, content_type=ContentType.objects.get_for_model(Merchant)
        ).values_list("object_id", flat=True)

        location = getattr(getattr(user, "profile", None), "location", "") or ""

        nearby_q = Q(location=location) if location else Q()

        return (
            Listing.objects.filter(status=Listing.Status.ACTIVE)
            .filter(
                Q(owner_id__in=followed_user_ids) | Q(merchant_id__in=followed_merchant_ids) | nearby_q
            )
            .exclude(owner=user)
            .select_related("owner", "owner__profile", "merchant", "category")
            .prefetch_related("photos")
            .distinct()
            .order_by("-created_at")
        )

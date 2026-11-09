from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from listings.models import Listing
from listings.serializers import ListingListSerializer
from merchants.models import Merchant

from .guest_likes import guest_id_from_token, issue_guest_like_token
from .models import Comment, Follow, GuestLike, Like
from .serializers import CommentSerializer, FollowSerializer, LikeSerializer
from common.throttling import ScopedWritesMixin


class GuestLikeTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "guest-like-token"

    def post(self, request):
        if request.user.is_authenticated:
            raise ValidationError("Sign out before requesting a guest identity.")
        return Response({"token": issue_guest_like_token()})


class GuestLikeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "guest-likes"

    def _identity(self, request):
        if request.user.is_authenticated:
            raise ValidationError("Use the authenticated likes endpoint.")
        try:
            return guest_id_from_token(request.META.get("HTTP_X_GUEST_LIKE_TOKEN"))
        except ValueError as exc:
            raise ValidationError({"guest_token": str(exc)}) from exc

    def _listing(self, request):
        try:
            listing_id = int(request.data.get("listing"))
        except (TypeError, ValueError):
            raise ValidationError({"listing": "A valid listing ID is required."})
        return get_object_or_404(Listing, pk=listing_id)

    def post(self, request):
        guest_id = self._identity(request)
        listing = self._listing(request)
        GuestLike.objects.get_or_create(guest_id=guest_id, listing=listing)
        return Response({"listing": listing.pk, "liked": True})

    def delete(self, request):
        guest_id = self._identity(request)
        listing = self._listing(request)
        GuestLike.objects.filter(guest_id=guest_id, listing=listing).delete()
        return Response({"listing": listing.pk, "liked": False})


class FollowViewSet(ScopedWritesMixin, 
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    write_throttle_scope = "social"
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Follow.objects.filter(follower=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError("Already following this target.")


class CommentViewSet(ScopedWritesMixin, viewsets.ModelViewSet):
    write_throttle_scope = "comments"
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Comment.objects.select_related("author", "author__profile")
        listing_id = self.request.query_params.get("listing")
        if listing_id:
            qs = qs.filter(listing_id=listing_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def handle_exception(self, exc):
        if self.request.method not in permissions.SAFE_METHODS and not self.request.user.is_authenticated:
            return Response(
                {"code": "AUTH_REQUIRED", "detail": "Sign in to post a comment."},
                status=401,
            )
        return super().handle_exception(exc)


class LikeViewSet(ScopedWritesMixin, 
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    write_throttle_scope = "social"
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
    """Every active listing, newest first, with listings from accounts and storefronts you follow listed ahead of the rest.
    Your own listings are included, so something you just posted is still there after a refresh."""

    serializer_class = ListingListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Case, IntegerField, Value, When

        user = self.request.user
        followed_user_ids = Follow.objects.filter(
            follower=user, content_type=ContentType.objects.get_for_model(user.__class__)
        ).values_list("object_id", flat=True)
        followed_merchant_ids = Follow.objects.filter(
            follower=user, content_type=ContentType.objects.get_for_model(Merchant)
        ).values_list("object_id", flat=True)

        return (
            Listing.objects.filter(Listing.public_visibility_filter())
            .annotate(
                followed_first=Case(
                    When(Q(owner_id__in=followed_user_ids) | Q(merchant_id__in=followed_merchant_ids), then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .select_related("owner", "owner__profile", "merchant", "category")
            .prefetch_related("photos")
            .order_by("followed_first", "-created_at")
        )

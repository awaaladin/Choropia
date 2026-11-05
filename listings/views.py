from django.db.models import F
from rest_framework.exceptions import PermissionDenied
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.geo import haversine_km
from common.permissions import IsOwnerOrReadOnly

from .filters import ListingFilter
from .models import Category, Listing, ListingPhoto
from .serializers import CategorySerializer, ListingListSerializer, ListingSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class ListingViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_class = ListingFilter
    search_fields = ("title", "description", "location")
    ordering_fields = ("price", "created_at", "views_count")

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "listing-create"
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        from staffpanel.models import may_sell

        if not may_sell(request.user):
            raise PermissionDenied(
                "Selling on Choropia is invite-only during the pilot. You can browse and buy as normal; message us if you would like to sell."
            )
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        qs = Listing.objects.select_related(
            "owner", "owner__profile", "merchant", "category"
        ).prefetch_related("photos")
        if self.action == "list":
            wants_mine = self.request.query_params.get("mine", "").lower() in ("1", "true", "yes")
            if wants_mine and self.request.user.is_authenticated:
                # Owners see their own sold listings too (just not ones they removed).
                qs = qs.exclude(status=Listing.Status.REMOVED)
            else:
                qs = qs.filter(status=Listing.Status.ACTIVE)
        else:
            qs = qs.exclude(status=Listing.Status.REMOVED)  # taken down by the owner: gone for everyone
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ListingListSerializer
        return ListingSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radius_km = request.query_params.get("radius_km")
        if lat and lng and radius_km:
            lat, lng, radius_km = float(lat), float(lng), float(radius_km)
            nearby_ids = [
                listing.id
                for listing in queryset.exclude(latitude=None, longitude=None)
                if haversine_km(lat, lng, float(listing.latitude), float(listing.longitude)) <= radius_km
            ]
            queryset = queryset.filter(id__in=nearby_ids)

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Listing.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        instance.refresh_from_db(fields=["views_count"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Takes the listing down for good. It disappears from the feed and search, and "My listings", and stays only as a record
        behind any past orders. Refused while a buyer has paid and is waiting for the item."""
        from orders.models import listing_has_paid_order

        listing = self.get_object()
        if listing_has_paid_order(listing):
            raise PermissionDenied("A buyer has paid for this item and is waiting for it. Finish or cancel that order first.")
        listing.status = Listing.Status.REMOVED
        listing.save(update_fields=["status"])
        return Response(status=204)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"photos/(?P<photo_id>\d+)",
        permission_classes=[permissions.IsAuthenticated, IsOwnerOrReadOnly],
    )
    def remove_photo(self, request, pk=None, photo_id=None):
        listing = self.get_object()
        photo = ListingPhoto.objects.filter(listing=listing, pk=photo_id).first()
        if photo is None:
            return Response(status=404)
        photo.delete()
        return Response(ListingSerializer(listing, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsOwnerOrReadOnly])
    def mark_sold(self, request, pk=None):
        listing = self.get_object()
        listing.status = Listing.Status.SOLD
        listing.quantity = 0  # the seller is saying there are none left
        listing.save(update_fields=["status", "quantity"])
        return Response(ListingSerializer(listing, context={"request": request}).data)

from django.db.models import F
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.geo import haversine_km
from common.permissions import IsOwnerOrReadOnly

from .filters import ListingFilter
from .models import Category, Listing
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

    def get_queryset(self):
        qs = Listing.objects.select_related(
            "owner", "owner__profile", "merchant", "category"
        ).prefetch_related("photos")
        if self.action == "list":
            qs = qs.filter(status=Listing.Status.ACTIVE)
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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsOwnerOrReadOnly])
    def mark_sold(self, request, pk=None):
        listing = self.get_object()
        listing.status = Listing.Status.SOLD
        listing.save(update_fields=["status"])
        return Response(ListingSerializer(listing, context={"request": request}).data)

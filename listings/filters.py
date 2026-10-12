import django_filters as filters

from .models import Listing


class ListingFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = filters.CharFilter(field_name="category__slug")
    owner = filters.NumberFilter(field_name="owner_id")
    mine = filters.BooleanFilter(method="filter_mine")

    def filter_mine(self, queryset, name, value):
        """?mine=true -> only the signed-in user's own listings (nothing if signed out)."""
        if not value:
            return queryset
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return queryset.none()
        return queryset.filter(owner=user)

    class Meta:
        model = Listing
        fields = ["category", "condition", "status", "min_price", "max_price", "merchant"]

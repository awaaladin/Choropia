import django_filters as filters

from .models import Listing


class ListingFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = filters.CharFilter(field_name="category__slug")

    class Meta:
        model = Listing
        fields = ["category", "condition", "status", "min_price", "max_price", "merchant"]

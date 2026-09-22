from rest_framework import serializers

from listings.models import Listing
from merchants.models import Merchant

from .models import Order, OrderStatusHistory


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ("from_status", "to_status", "actor", "note", "created_at")


class OrderSerializer(serializers.ModelSerializer):
    history = OrderStatusHistorySerializer(many=True, read_only=True)
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    listing_cover_photo = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "listing",
            "listing_title",
            "listing_cover_photo",
            "buyer",
            "seller",
            "price",
            "status",
            "delivered_at",
            "confirmed_at",
            "completed_at",
            "dispute_reason",
            "history",
            "created_at",
        )
        read_only_fields = (
            "id",
            "buyer",
            "seller",
            "price",
            "status",
            "delivered_at",
            "confirmed_at",
            "completed_at",
            "created_at",
        )

    def get_listing_cover_photo(self, obj):
        photo = obj.listing.photos.first()
        if not photo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(photo.image.url) if request else photo.image.url


class OrderCreateSerializer(serializers.Serializer):
    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.filter(status=Listing.Status.ACTIVE))

    def validate_listing(self, listing):
        request = self.context["request"]
        if listing.owner_id == request.user.id:
            raise serializers.ValidationError("You cannot buy your own listing.")
        return listing

    def create(self, validated_data):
        listing = validated_data["listing"]
        buyer = self.context["request"].user
        seller_entity = listing.seller
        seller = seller_entity.user if isinstance(seller_entity, Merchant) else seller_entity

        order = Order.objects.create(
            listing=listing,
            buyer=buyer,
            seller=seller,
            price=listing.price,
        )
        return order


class DisputeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class DisputeResolutionSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=("refund", "release"))

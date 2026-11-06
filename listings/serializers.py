from django.db import transaction
from rest_framework import serializers

from .models import Category, Listing, ListingPhoto


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent")


class ListingPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingPhoto
        fields = ("id", "image", "order")


class ListingEngagementMixin:
    """Seller identity + like/comment counts, shared by the detail and list serializers so a
    card or a detail page can render a real post (name, avatar, likes/comments) without an extra
    request per listing."""

    def _absolute(self, url):
        if not url:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_seller_id(self, obj):
        return obj.merchant_id or obj.owner_id

    def get_seller_name(self, obj):
        if obj.merchant:
            return obj.merchant.business_name
        return obj.owner.get_full_name() or obj.owner.email

    def get_seller_avatar(self, obj):
        if obj.merchant:
            return self._absolute(obj.merchant.logo.url) if obj.merchant.logo else None
        profile = getattr(obj.owner, "profile", None)
        return self._absolute(profile.avatar.url) if profile and profile.avatar else None

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return obj.likes.filter(user=user).exists()


class ListingSerializer(ListingEngagementMixin, serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    photos = ListingPhotoSerializer(many=True, read_only=True)
    uploaded_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    seller_id = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    seller_avatar = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    # Edit only: tick it to show buyers that the price changed (the old price is shown crossed out). Left off, the new price
    # simply replaces the old one with no trace.
    show_price_change = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Listing
        fields = (
            "id",
            "owner",
            "owner_id",
            "merchant",
            "category",
            "title",
            "description",
            "price",
            "previous_price",
            "show_price_change",
            "quantity",
            "campus",
            "condition",
            "status",
            "location",
            "latitude",
            "longitude",
            "views_count",
            "seller_id",
            "seller_name",
            "seller_avatar",
            "likes_count",
            "comments_count",
            "is_liked",
            "photos",
            "uploaded_photos",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "previous_price", "views_count", "created_at", "updated_at")

    def validate_uploaded_photos(self, photos):
        if len(photos) > 10:
            raise serializers.ValidationError("You can add up to 10 photos.")
        for photo in photos:
            if photo.size > 8 * 1024 * 1024:
                raise serializers.ValidationError("Each photo must be under 8 MB.")
        return photos

    def validate_campus(self, value):
        if value not in ("", "uniuyo"):
            raise serializers.ValidationError("Choose a valid campus market.")
        return value

    def validate_quantity(self, value):
        if value < 1 or value > 999:
            raise serializers.ValidationError("Enter how many you have, from 1 to 999.")
        return value

    def validate_merchant(self, merchant):
        if merchant is None:
            return merchant
        request = self.context["request"]
        if merchant.user_id != request.user.id:
            raise serializers.ValidationError("You may only post listings under your own storefront.")
        return merchant

    def create(self, validated_data):
        validated_data.pop("show_price_change", None)
        photos = validated_data.pop("uploaded_photos", [])
        # Atomic: if saving a photo fails (storage outage), the listing row is rolled back too,
        # instead of leaving a photo-less listing behind.
        with transaction.atomic():
            listing = Listing.objects.create(**validated_data)
            for index, image in enumerate(photos):
                ListingPhoto.objects.create(listing=listing, image=image, order=index)
        return listing

    def update(self, instance, validated_data):
        photos = validated_data.pop("uploaded_photos", [])
        show_change = validated_data.pop("show_price_change", False)
        new_price = validated_data.get("price")
        if new_price is not None and new_price != instance.price:
            instance.previous_price = instance.price if show_change else None
        if validated_data.get("quantity", 0) > 0 and instance.status == Listing.Status.SOLD and instance.quantity == 0:
            instance.status = Listing.Status.ACTIVE  # restocked: back on sale
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        for index, image in enumerate(photos):
            ListingPhoto.objects.create(
                listing=instance, image=image, order=instance.photos.count() + index
            )
        return instance


class ListingListSerializer(ListingEngagementMixin, serializers.ModelSerializer):
    """Lighter-weight serializer for feed/list endpoints."""

    cover_photo = serializers.SerializerMethodField()
    merchant_id = serializers.IntegerField(source="merchant.id", read_only=True, default=None)
    seller_id = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    seller_avatar = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            "id",
            "title",
            "price",
            "previous_price",
            "quantity",
            "campus",
            "condition",
            "status",
            "location",
            "category",
            "merchant_id",
            "seller_id",
            "seller_name",
            "seller_avatar",
            "likes_count",
            "comments_count",
            "is_liked",
            "cover_photo",
            "created_at",
        )

    def get_cover_photo(self, obj):
        first = obj.photos.first()
        return self._absolute(first.image.url) if first else None

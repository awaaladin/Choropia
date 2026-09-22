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
        read_only_fields = ("id", "views_count", "created_at", "updated_at")

    def validate_merchant(self, merchant):
        if merchant is None:
            return merchant
        request = self.context["request"]
        if merchant.user_id != request.user.id:
            raise serializers.ValidationError("You may only post listings under your own storefront.")
        return merchant

    def create(self, validated_data):
        photos = validated_data.pop("uploaded_photos", [])
        listing = Listing.objects.create(**validated_data)
        for index, image in enumerate(photos):
            ListingPhoto.objects.create(listing=listing, image=image, order=index)
        return listing

    def update(self, instance, validated_data):
        photos = validated_data.pop("uploaded_photos", [])
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

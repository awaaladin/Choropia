from rest_framework import serializers

from .models import Reel, ReelComment, ReelLike


class ReelEngagementMixin:
    """Creator identity + like/comment counts — same pattern as listings.ListingEngagementMixin,
    so a reel card can render without an extra request per reel."""

    def _absolute(self, url):
        if not url:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_creator_id(self, obj):
        return obj.merchant_id or obj.owner_id

    def get_creator_name(self, obj):
        if obj.merchant:
            return obj.merchant.business_name
        return obj.owner.get_full_name() or obj.owner.email

    def get_creator_avatar(self, obj):
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

    def get_listing_title(self, obj):
        return obj.listing.title if obj.listing else None

    def get_listing_price(self, obj):
        return str(obj.listing.price) if obj.listing else None


class ReelSerializer(ReelEngagementMixin, serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    creator_id = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()
    creator_avatar = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    listing_title = serializers.SerializerMethodField()
    listing_price = serializers.SerializerMethodField()

    class Meta:
        model = Reel
        fields = (
            "id",
            "owner",
            "merchant",
            "listing",
            "listing_title",
            "listing_price",
            "video",
            "caption",
            "views_count",
            "creator_id",
            "creator_name",
            "creator_avatar",
            "likes_count",
            "comments_count",
            "is_liked",
            "created_at",
        )
        read_only_fields = ("id", "views_count", "created_at")

    def validate_merchant(self, merchant):
        if merchant is None:
            return merchant
        request = self.context["request"]
        if merchant.user_id != request.user.id:
            raise serializers.ValidationError("You may only post reels under your own storefront.")
        return merchant

    def validate_listing(self, listing):
        if listing is None:
            return listing
        request = self.context["request"]
        seller_id = listing.merchant.user_id if listing.merchant_id else listing.owner_id
        if seller_id != request.user.id:
            raise serializers.ValidationError("You may only tag your own listings on a reel.")
        return listing


class ReelLikeSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = ReelLike
        fields = ("id", "reel", "user", "created_at")
        read_only_fields = ("id", "created_at")


class ReelCommentSerializer(serializers.ModelSerializer):
    author = serializers.HiddenField(default=serializers.CurrentUserDefault())
    author_id = serializers.IntegerField(source="author.id", read_only=True)
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ReelComment
        fields = ("id", "reel", "author", "author_id", "author_name", "body", "created_at")
        read_only_fields = ("id", "created_at")

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email

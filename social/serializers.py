from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from accounts.models import User
from merchants.models import Merchant

from .models import Comment, Follow, Like

TARGET_MODELS = {"user": User, "merchant": Merchant}


class FollowSerializer(serializers.ModelSerializer):
    follower = serializers.HiddenField(default=serializers.CurrentUserDefault())
    target_type = serializers.ChoiceField(choices=tuple(TARGET_MODELS.keys()), write_only=True)
    target_id = serializers.IntegerField(write_only=True)
    target_type_display = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = ("id", "follower", "target_type", "target_id", "target_type_display", "object_id", "created_at")
        read_only_fields = ("id", "object_id", "created_at")

    def get_target_type_display(self, obj):
        return obj.content_type.model

    def validate(self, attrs):
        model = TARGET_MODELS[attrs["target_type"]]
        if not model.objects.filter(pk=attrs["target_id"]).exists():
            raise serializers.ValidationError("Target does not exist.")
        attrs["content_type"] = ContentType.objects.get_for_model(model)
        attrs["object_id"] = attrs.pop("target_id")
        attrs.pop("target_type")
        return attrs

    def create(self, validated_data):
        follow, _ = Follow.objects.get_or_create(
            follower=validated_data["follower"],
            content_type=validated_data["content_type"],
            object_id=validated_data["object_id"],
        )
        return follow


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    author_id = serializers.IntegerField(source="author.id", read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "listing", "author", "author_id", "parent", "body", "created_at")
        read_only_fields = ("id", "author", "author_id", "created_at")

    def get_author(self, comment):
        user = comment.author
        profile = getattr(user, "profile", None)
        name = f"{user.first_name} {user.last_name}".strip()
        if not user.is_active:
            name = "Deleted user"
        elif not name:
            name = "Choropia member"
        avatar = profile.avatar.url if profile and profile.avatar else None
        request = self.context.get("request")
        if avatar and request is not None:
            avatar = request.build_absolute_uri(avatar)
        return {
            "id": user.pk,
            "display_name": name,
            "username": f"user-{user.pk}",
            "avatar_url": avatar,
            "verified": bool(profile and profile.seller_verified),
        }


class LikeSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Like
        fields = ("id", "listing", "user", "created_at")
        read_only_fields = ("id", "created_at")

from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.HiddenField(default=serializers.CurrentUserDefault())
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)

    class Meta:
        model = Message
        fields = ("id", "conversation", "sender", "sender_id", "body", "read_at", "created_at")
        read_only_fields = ("id", "read_at", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    buyer = serializers.HiddenField(default=serializers.CurrentUserDefault())
    last_message = serializers.SerializerMethodField()
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    other_party_name = serializers.SerializerMethodField()
    other_party_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            "id",
            "listing",
            "listing_title",
            "buyer",
            "seller",
            "other_party_name",
            "other_party_avatar",
            "order",
            "last_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "seller", "order", "created_at", "updated_at")

    def get_last_message(self, obj):
        message = obj.messages.last()
        return MessageSerializer(message).data if message else None

    def _other_party(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user:
            return None
        return obj.seller if user.id == obj.buyer_id else obj.buyer

    def get_other_party_name(self, obj):
        other = self._other_party(obj)
        return (other.get_full_name() or other.email) if other else None

    def get_other_party_avatar(self, obj):
        other = self._other_party(obj)
        profile = getattr(other, "profile", None) if other else None
        if not profile or not profile.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(profile.avatar.url) if request else profile.avatar.url

    def validate(self, attrs):
        listing = attrs["listing"]
        request = self.context["request"]
        if listing.owner_id == request.user.id:
            raise serializers.ValidationError("You cannot start a conversation on your own listing.")
        attrs["seller"] = listing.owner
        return attrs

    def create(self, validated_data):
        conversation, _ = Conversation.objects.get_or_create(
            listing=validated_data["listing"],
            buyer=validated_data["buyer"],
            defaults={"seller": validated_data["seller"]},
        )
        return conversation


class ConversationToOrderSerializer(serializers.Serializer):
    """No input fields — creating an Order from a conversation is derived entirely from the
    conversation's own listing/buyer/seller, so there's nothing for the client to supply."""

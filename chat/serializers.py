from pathlib import PurePath

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.demo import DEMO_LISTING_MESSAGE, is_demo_user
from offers.serializers import OfferSerializer

from .models import Conversation, Message
from .listing_references import append_listing_reference

# Files go through the API as multipart. Vercel rejects request bodies over ~4.5 MB, so keep a
# comfortable margin under that.
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024
MAX_VOICE_SECONDS = 600
ATTACHMENT_EXTENSIONS = {
    Message.AttachmentType.IMAGE: {"jpg", "jpeg", "png", "webp", "gif"},
    Message.AttachmentType.AUDIO: {"m4a", "aac", "mp3", "ogg", "oga", "wav", "webm", "3gp", "amr"},
    Message.AttachmentType.FILE: {"pdf"},
}


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.HiddenField(default=serializers.CurrentUserDefault())
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    # "text" or "offer". An offer message carries the live offer (as the viewer may see it), not a copy.
    type = serializers.CharField(source="message_type", read_only=True)
    offer = serializers.SerializerMethodField()
    listing = serializers.IntegerField(source="referenced_listing_id", read_only=True, allow_null=True)
    listing_snapshot = serializers.JSONField(read_only=True)
    listing_status = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "sender",
            "sender_id",
            "type",
            "offer",
            "listing",
            "listing_snapshot",
            "listing_status",
            "body",
            "attachment",
            "attachment_type",
            "duration_seconds",
            "read_at",
            "created_at",
        )
        read_only_fields = ("id", "attachment_type", "read_at", "created_at")

    @extend_schema_field(OfferSerializer(allow_null=True))
    def get_offer(self, message):
        if not message.offer_id:
            return None
        return OfferSerializer(message.offer, context=self.context).data

    def get_listing_status(self, message):
        if message.referenced_listing_id:
            return message.referenced_listing.status
        return "removed"

    def validate_duration_seconds(self, value):
        if value is not None and value > MAX_VOICE_SECONDS:
            raise serializers.ValidationError("Voice notes can be at most 10 minutes.")
        return value

    def validate(self, attrs):
        attachment = attrs.get("attachment")
        body = (attrs.get("body") or "").strip()
        attrs["body"] = body

        if not attachment and not body:
            raise serializers.ValidationError("Send a message or an attachment.")

        if attachment:
            extension = PurePath(attachment.name).suffix.lower().lstrip(".")
            kind = next((k for k, exts in ATTACHMENT_EXTENSIONS.items() if extension in exts), None)
            if kind is None:
                raise serializers.ValidationError({"attachment": "That file type isn't supported."})
            if attachment.size > MAX_ATTACHMENT_BYTES:
                raise serializers.ValidationError({"attachment": "Attachments can be at most 3 MB."})
            attrs["attachment_type"] = kind
            if kind != Message.AttachmentType.AUDIO:
                attrs.pop("duration_seconds", None)
        else:
            attrs.pop("duration_seconds", None)
        return attrs


class ConversationSerializer(serializers.ModelSerializer):
    buyer = serializers.HiddenField(default=serializers.CurrentUserDefault())
    last_message = serializers.SerializerMethodField()
    listing_title = serializers.CharField(source="listing.title", read_only=True, allow_null=True)
    other_party_name = serializers.SerializerMethodField()
    other_party_id = serializers.SerializerMethodField()
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
            "other_party_id",
            "other_party_avatar",
            "order",
            "orders",
            "last_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "seller", "order", "orders", "created_at", "updated_at")

    def get_last_message(self, obj):
        message = obj.messages.last()
        return MessageSerializer(message, context=self.context).data if message else None

    def _other_party(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user:
            return None
        if user.id not in (obj.user_low_id, obj.user_high_id):
            return None
        return obj.other_participant(user)

    def get_other_party_name(self, obj):
        other = self._other_party(obj)
        if other is None:
            return None
        if not other.is_active:
            return "Deleted user"
        return f"{other.first_name} {other.last_name}".strip() or "Choropia member"

    def get_other_party_id(self, obj):
        other = self._other_party(obj)
        return other.pk if other else None

    def get_other_party_avatar(self, obj):
        other = self._other_party(obj)
        profile = getattr(other, "profile", None) if other else None
        if not profile or not profile.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(profile.avatar.url) if request else profile.avatar.url

    def validate(self, attrs):
        listing = attrs.get("listing")
        request = self.context["request"]
        if listing is None:
            raise serializers.ValidationError({"listing": "Choose a listing to start a conversation."})
        if listing.owner_id == request.user.id:
            raise serializers.ValidationError("You cannot start a conversation on your own listing.")
        if is_demo_user(listing.owner):
            raise serializers.ValidationError(DEMO_LISTING_MESSAGE)
        attrs["seller"] = listing.owner
        attrs["buyer"] = request.user
        return attrs

    def create(self, validated_data):
        listing = validated_data["listing"]
        buyer = validated_data["buyer"]
        seller = validated_data["seller"]
        conversation, _ = Conversation.get_or_create_direct_thread(
            user_a=buyer,
            user_b=seller,
            listing=listing,
        )
        message, created = append_listing_reference(conversation.pk, listing, buyer, self.context.get("request"))
        if created:
            from .realtime import broadcast_message

            broadcast_message(message)
        return conversation


class ConversationToOrderSerializer(serializers.Serializer):
    """No input fields — creating an Order from a conversation is derived entirely from the
    conversation's own listing/buyer/seller, so there's nothing for the client to supply."""

from datetime import datetime  # noqa: F401 - used in a type hint

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Offer
from .services import role_of

SELLER_ONLY_FIELDS = ("fee_kobo", "seller_net_kobo", "seller_verified_snapshot")


class OfferListingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    photo = serializers.SerializerMethodField()

    def get_photo(self, listing) -> str | None:
        photo = listing.photos.first()
        if not photo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(photo.image.url) if request else photo.image.url


class OfferSerializer(serializers.ModelSerializer):
    """An offer as one participant sees it. The fee and the seller's net are only ever included for the seller: the
    buyer pays the offer amount (plus a rider fee if chosen) and never sees Choropia's cut."""

    listing = OfferListingSerializer(read_only=True)
    viewer_role = serializers.SerializerMethodField()
    total_kobo = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True, allow_null=True)
    server_now = serializers.SerializerMethodField(help_text="The server's clock, so countdowns don't drift with the phone's.")

    class Meta:
        model = Offer
        fields = (
            "id",
            "reference",
            "conversation",
            "listing",
            "seller",
            "buyer",
            "viewer_role",
            "amount_kobo",
            "listing_price_kobo",
            "fee_kobo",
            "seller_net_kobo",
            "seller_verified_snapshot",
            "allowed_delivery_methods",
            "note",
            "status",
            "expires_at",
            "delivery_method",
            "delivery_fee_kobo",
            "total_kobo",
            "order_id",
            "created_at",
            "updated_at",
            "paid_at",
            "closed_at",
            "server_now",
        )
        read_only_fields = fields

    def _viewer(self):
        if "viewer" in self.context:
            return self.context["viewer"]
        request = self.context.get("request")
        return getattr(request, "user", None)

    @extend_schema_field(serializers.ChoiceField(choices=["seller", "buyer"], allow_null=True))
    def get_viewer_role(self, offer):
        return role_of(offer, self._viewer())

    def get_server_now(self, offer) -> "datetime":
        # Formatted here: the realtime path sends this through plain json.dumps, which can't encode datetimes.
        return serializers.DateTimeField().to_representation(timezone.now())

    def to_representation(self, offer):
        data = super().to_representation(offer)
        # Show the truth even if the expiry job hasn't run yet; every action expires it for real under a lock.
        if offer.status == Offer.Status.PENDING and offer.expires_at <= timezone.now():
            data["status"] = Offer.Status.EXPIRED
        from .settlement import last_payment_failed

        data["last_payment_failed"] = last_payment_failed(offer)
        data["order_stage"] = order_stage(offer)
        if role_of(offer, self._viewer()) != "seller":
            for field in SELLER_ONLY_FIELDS:
                data.pop(field, None)
        return data


def order_stage(offer):
    """Where the money is, for the offer card's timeline: None (no order yet), awaiting_payment, escrow_held,
    handed_over, released, disputed, refund_pending, refunded or cancelled."""
    order = offer.order
    if order is None:
        return None
    payment = getattr(order, "payment", None) if hasattr(order, "payment") else None
    payment_status = getattr(payment, "status", None)
    if payment_status == "refund_pending":
        return "refund_pending"
    return {
        "pending_payment": "awaiting_payment",
        "paid_escrow": "escrow_held",
        "courier_assigned": "escrow_held",
        "in_transit": "escrow_held",
        "delivered": "handed_over",
        "confirmed": "handed_over",
        "completed": "released",
        "disputed": "disputed",
        "refunded": "refunded",
        "cancelled": "cancelled",
    }.get(order.status, order.status)


class CreateOfferSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField()
    amount_kobo = serializers.IntegerField(min_value=1, max_value=100_000_000_000)
    allowed_delivery_methods = serializers.ListField(
        child=serializers.ChoiceField(choices=Offer.Delivery.choices), min_length=1, max_length=3
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)
    pin = serializers.CharField(write_only=True, max_length=12, trim_whitespace=True)


class OfferCheckoutSerializer(serializers.Serializer):
    delivery_method = serializers.ChoiceField(choices=Offer.Delivery.choices)
    source = serializers.ChoiceField(choices=("web", "app"), default="web", required=False)

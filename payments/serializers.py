from rest_framework import serializers

from .models import Payment


class WalletTransactionSerializer(serializers.ModelSerializer):
    """A Payment from one user's point of view — role flips what the amount means (money they
    paid in vs. money they're owed), reusing the existing Payment data rather than a separate
    ledger. See payments/views.py's WalletTransactionsView for the role/queryset logic."""

    role = serializers.SerializerMethodField()
    listing_title = serializers.CharField(source="order.listing.title", read_only=True)
    other_party_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "order",
            "listing_title",
            "role",
            "other_party_name",
            "amount",
            "crypto_amount",
            "crypto_currency",
            "status",
            "tx_hash",
            "paid_at",
            "released_at",
            "refunded_at",
            "created_at",
        )

    def get_role(self, obj):
        user = self.context["request"].user
        return "selling" if obj.order.seller_id == user.id else "buying"

    def get_other_party_name(self, obj):
        user = self.context["request"].user
        other = obj.order.seller if obj.order.buyer_id == user.id else obj.order.buyer
        return other.get_full_name() or other.email

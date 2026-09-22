from rest_framework import serializers

from orders.models import Order

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Review
        fields = ("id", "order", "reviewer", "reviewee", "rating", "comment", "created_at")
        read_only_fields = ("id", "reviewee", "created_at")

    def validate_order(self, order):
        if order.status != Order.Status.COMPLETED:
            raise serializers.ValidationError("You can only review an order once it is completed.")
        return order

    def validate(self, attrs):
        order = attrs["order"]
        reviewer = self.context["request"].user
        if reviewer.id not in (order.buyer_id, order.seller_id):
            raise serializers.ValidationError("You were not a participant in this order.")
        attrs["reviewee"] = order.seller if reviewer.id == order.buyer_id else order.buyer
        return attrs

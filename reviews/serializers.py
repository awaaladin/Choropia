from rest_framework import serializers

from . import rules
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.HiddenField(default=serializers.CurrentUserDefault())
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "order", "reviewer", "reviewee", "reviewer_name", "rating", "comment", "created_at")
        read_only_fields = ("id", "reviewee", "reviewer_name", "created_at")

    def get_reviewer_name(self, obj):
        first = (obj.reviewer.first_name or "").strip() or "Buyer"
        last = (obj.reviewer.last_name or "").strip()
        return f"{first} {last[0]}." if last else first

    def validate(self, attrs):
        order = attrs["order"]
        reviewer = self.context["request"].user
        allowed, reason = rules.check(order, reviewer)
        if not allowed:
            raise serializers.ValidationError(reason)
        attrs["reviewee"] = order.seller
        return attrs

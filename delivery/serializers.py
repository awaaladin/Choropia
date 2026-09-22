from rest_framework import serializers

from .models import Delivery
from .providers.base import DeliveryStatus


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = ("id", "order", "provider_name", "tracking_id", "status", "created_at", "updated_at")
        read_only_fields = fields


class DeliveryStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            DeliveryStatus.PENDING,
            DeliveryStatus.PICKED_UP,
            DeliveryStatus.IN_TRANSIT,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.FAILED,
        ]
    )

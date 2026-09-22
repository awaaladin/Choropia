from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "verb",
            "actor",
            "target_type",
            "target_object_id",
            "is_read",
            "created_at",
        )

    def get_target_type(self, obj):
        return obj.target_content_type.model if obj.target_content_type_id else None

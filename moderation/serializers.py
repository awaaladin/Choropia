from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from listings.models import Listing

from .models import Report

TARGET_MODELS = {"listing": Listing}


class ReportSerializer(serializers.ModelSerializer):
    reporter = serializers.HiddenField(default=serializers.CurrentUserDefault())
    target_type = serializers.ChoiceField(choices=tuple(TARGET_MODELS.keys()), write_only=True)
    target_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Report
        fields = ("id", "reporter", "target_type", "target_id", "reason", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")

    def validate(self, attrs):
        model = TARGET_MODELS[attrs.pop("target_type")]
        target_id = attrs.pop("target_id")
        if not model.objects.filter(pk=target_id).exists():
            raise serializers.ValidationError("Target does not exist.")
        attrs["content_type"] = ContentType.objects.get_for_model(model)
        attrs["object_id"] = target_id
        return attrs


class ReportResolutionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("reviewed", "actioned", "dismissed"))
    resolution_note = serializers.CharField(required=False, allow_blank=True, default="")

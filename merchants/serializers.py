from rest_framework import serializers

from .models import Merchant, MerchantApplication


class MerchantApplicationSerializer(serializers.ModelSerializer):
    applicant = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = MerchantApplication
        fields = (
            "id",
            "applicant",
            "business_name",
            "business_description",
            "business_phone",
            "business_address",
            "status",
            "rejection_reason",
            "created_at",
        )
        read_only_fields = ("id", "status", "rejection_reason", "created_at")

    def validate_applicant(self, value):
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if hasattr(user, "merchant"):
            raise serializers.ValidationError("You already have a merchant storefront.")
        if MerchantApplication.objects.filter(
            applicant=user, status=MerchantApplication.Status.PENDING
        ).exists():
            raise serializers.ValidationError("You already have a pending application.")
        return attrs


class MerchantApplicationReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("approve", "reject"))
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default="")


class MerchantSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(source="user_id", read_only=True)
    followers_count = serializers.SerializerMethodField()

    def get_followers_count(self, obj):
        from django.contrib.contenttypes.models import ContentType

        from social.models import Follow

        return Follow.objects.filter(
            content_type=ContentType.objects.get_for_model(Merchant), object_id=obj.id
        ).count()

    class Meta:
        model = Merchant
        fields = (
            "id",
            "owner_id",
            "business_name",
            "description",
            "logo",
            "location",
            "status",
            "followers_count",
            "created_at",
        )
        read_only_fields = ("id", "status", "created_at")

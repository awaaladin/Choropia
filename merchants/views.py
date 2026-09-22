from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsStaffOrModerator

from .models import Merchant, MerchantApplication
from .serializers import (
    MerchantApplicationReviewSerializer,
    MerchantApplicationSerializer,
    MerchantSerializer,
)


class MerchantApplicationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MerchantApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_moderator:
            return MerchantApplication.objects.all().order_by("-created_at")
        return MerchantApplication.objects.filter(applicant=user).order_by("-created_at")

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrModerator])
    def review(self, request, pk=None):
        application = self.get_object()
        serializer = MerchantApplicationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if application.status != MerchantApplication.Status.PENDING:
            return Response({"detail": "Application has already been reviewed."}, status=400)

        if serializer.validated_data["action"] == "approve":
            merchant = application.approve(reviewer=request.user)
            return Response(MerchantSerializer(merchant).data)

        application.reject(
            reviewer=request.user, reason=serializer.validated_data.get("rejection_reason", "")
        )
        return Response(MerchantApplicationSerializer(application).data)


class MerchantViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MerchantSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    search_fields = ("business_name", "location")

    def get_queryset(self):
        return Merchant.objects.filter(status=Merchant.Status.ACTIVE).select_related("user")

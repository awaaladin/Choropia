from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsStaffOrModerator

from .models import Merchant, MerchantApplication
from .serializers import (
    MerchantApplicationReviewSerializer,
    MerchantApplicationSerializer,
    MerchantEditSerializer,
    MerchantSerializer,
)
from common.throttling import ScopedWritesMixin


class MerchantApplicationViewSet(ScopedWritesMixin, 
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    write_throttle_scope = "merchant-apply"
    serializer_class = MerchantApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_moderator:
            return MerchantApplication.objects.all().order_by("-created_at")
        return MerchantApplication.objects.filter(applicant=user).order_by("-created_at")

    def perform_create(self, serializer):
        application = serializer.save()
        from notifications import staff_alerts

        staff_alerts.alert(
            "New storefront application", "Someone applied for a storefront",
            [f"Business: {application.business_name}",
             f"Applicant: {application.applicant.get_full_name()} ({application.applicant.email})",
             "Open the staff panel Inbox to approve or reject it."],
            "/staff/inbox/",
        )

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

    @action(detail=False, methods=["get", "patch"], permission_classes=[permissions.IsAuthenticated], url_path="mine")
    def mine(self, request):
        """The signed-in owner's own storefront: read it, or change its name, description and location.
        Renaming emails the owner a confirmation."""
        merchant = Merchant.objects.filter(user=request.user).first()
        if merchant is None:
            return Response({"detail": "You do not have a storefront yet."}, status=404)
        if request.method == "GET":
            return Response(MerchantSerializer(merchant).data)
        if merchant.status != Merchant.Status.ACTIVE:
            return Response({"detail": "Your storefront is suspended, so it cannot be edited."}, status=403)
        old_name = merchant.business_name
        serializer = MerchantEditSerializer(merchant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        merchant = serializer.save()
        if merchant.business_name != old_name:
            from notifications import emails

            emails.send_storefront_renamed(request.user, old_name, merchant.business_name)
        return Response(MerchantSerializer(merchant).data)

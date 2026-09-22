from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsStaffOrModerator

from .models import Report
from .serializers import ReportResolutionSerializer, ReportSerializer


class ReportViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_moderator:
            return Report.objects.all()
        return Report.objects.filter(reporter=user)

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrModerator])
    def resolve(self, request, pk=None):
        report = self.get_object()
        serializer = ReportResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report.status = serializer.validated_data["status"]
        report.resolution_note = serializer.validated_data.get("resolution_note", "")
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "resolution_note", "reviewed_by", "reviewed_at"])
        return Response(ReportSerializer(report).data)

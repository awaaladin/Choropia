from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsStaffOrModerator

from .models import Report
from .serializers import ReportResolutionSerializer, ReportSerializer
from common.throttling import ScopedWritesMixin


class ReportViewSet(ScopedWritesMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    write_throttle_scope = "reports"
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_moderator:
            return Report.objects.all()
        return Report.objects.filter(reporter=user)

    def perform_create(self, serializer):
        report = serializer.save()
        from notifications import staff_alerts

        target = report.target
        what = f"{report.content_type.model} #{report.object_id}" + (f" ({target.title})" if getattr(target, "title", None) else "")
        staff_alerts.alert(
            "New report to review", "Someone reported a listing",
            [f"Reported: {what}.", f"Reason: {report.reason}", f"Reported by: {report.reporter.get_full_name() or report.reporter.email}."],
            "/staff/inbox/",
        )

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

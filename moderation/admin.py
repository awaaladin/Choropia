from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("target", "reporter", "status", "reviewed_by", "created_at")
    list_filter = ("status",)
    actions = ["mark_reviewed"]

    @admin.action(description="Mark selected reports as reviewed")
    def mark_reviewed(self, request, queryset):
        from django.utils import timezone

        queryset.update(status=Report.Status.REVIEWED, reviewed_by=request.user, reviewed_at=timezone.now())

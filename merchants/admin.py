from django.contrib import admin

from .models import Merchant, MerchantApplication


@admin.register(MerchantApplication)
class MerchantApplicationAdmin(admin.ModelAdmin):
    list_display = ("business_name", "applicant", "status", "reviewed_by", "created_at")
    list_filter = ("status",)
    search_fields = ("business_name", "applicant__email")
    actions = ["approve_applications", "reject_applications"]

    @admin.action(description="Approve selected applications")
    def approve_applications(self, request, queryset):
        for application in queryset.filter(status=MerchantApplication.Status.PENDING):
            application.approve(reviewer=request.user)

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        for application in queryset.filter(status=MerchantApplication.Status.PENDING):
            application.reject(reviewer=request.user, reason="Rejected via admin bulk action.")


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "status", "location", "created_at")
    list_filter = ("status",)
    search_fields = ("business_name", "user__email")

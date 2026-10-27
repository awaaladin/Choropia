from django.contrib import admin

from .models import Acceptance


@admin.register(Acceptance)
class AcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "document", "version", "accepted_at", "ip_address")
    list_filter = ("document", "version")
    search_fields = ("user__email",)
    readonly_fields = ("user", "document", "version", "accepted_at", "ip_address")

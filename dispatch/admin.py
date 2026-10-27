from django.contrib import admin, messages
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from notifications import emails

from . import crypto
from .models import (
    Area,
    DeliveryOffer,
    DocumentAccessLog,
    DriverDocument,
    DriverProfile,
    DriverRoute,
    ListingDelivery,
    OrderDelivery,
)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "is_seed", "added_by", "created_at")
    list_filter = ("is_active", "is_seed")
    search_fields = ("name",)


class DocumentInline(admin.TabularInline):
    """Metadata only. The file itself is encrypted; staff open it through the logged link below."""

    model = DriverDocument
    extra = 0
    can_delete = False
    fields = ("kind", "content_type", "size_bytes", "open_link", "created_at")
    readonly_fields = fields

    def open_link(self, obj):
        if not obj.pk:
            return ""
        url = reverse("admin:dispatch-document", args=[obj.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener">Open (logged)</a>', url)

    open_link.short_description = "View"

    def has_add_permission(self, request, obj=None):
        return False


class RouteInline(admin.TabularInline):
    model = DriverRoute
    extra = 0
    can_delete = False
    fields = ("from_area", "to_area", "price", "is_active")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "status", "vehicle_type", "phone", "documents_complete", "created_at")
    list_filter = ("status", "vehicle_type")
    search_fields = ("full_name", "user__email", "phone", "plate_number")
    readonly_fields = ("user", "reviewed_at", "reviewed_by", "terms_accepted_version")
    inlines = [DocumentInline, RouteInline]
    actions = ["approve", "reject", "suspend"]

    @admin.display(boolean=True, description="All 4 documents")
    def documents_complete(self, obj):
        have = set(obj.documents.values_list("kind", flat=True))
        return all(kind.value in have for kind in DriverDocument.REQUIRED)

    def _review(self, request, queryset, status, note=""):
        count = 0
        for driver in queryset:
            driver.status = status
            driver.review_note = note
            driver.reviewed_at = timezone.now()
            driver.reviewed_by = request.user
            driver.save()
            count += 1
        return count

    @admin.action(description="Approve selected drivers (needs all 4 documents)")
    def approve(self, request, queryset):
        ok = []
        for driver in queryset:
            if not self.documents_complete(driver):
                self.message_user(request, f"{driver.full_name} is missing documents, so was not approved.", messages.WARNING)
                continue
            ok.append(driver.pk)
        done = self._review(request, queryset.filter(pk__in=ok), DriverProfile.Status.APPROVED)
        for driver in queryset.filter(pk__in=ok):
            emails.send_dispatch_notice(
                driver.user, "You are approved as a Choropia driver", "You are approved",
                "Your documents have been checked. Add the routes you serve and your prices, and sellers can start choosing you.",
                "/driver",
            )
        self.message_user(request, f"{done} driver(s) approved.")

    @admin.action(description="Reject selected drivers")
    def reject(self, request, queryset):
        note = "We could not verify your documents. Please re-upload clear photos and apply again."
        done = self._review(request, queryset, DriverProfile.Status.REJECTED, note)
        for driver in queryset:
            emails.send_dispatch_notice(driver.user, "Your driver application", "We could not approve your application", note, "/driver")
        self.message_user(request, f"{done} driver(s) rejected.")

    @admin.action(description="Suspend selected drivers")
    def suspend(self, request, queryset):
        done = self._review(request, queryset, DriverProfile.Status.SUSPENDED, "Your driver account is suspended. Contact support.")
        self.message_user(request, f"{done} driver(s) suspended.")

    # --- viewing an encrypted document: staff only, every view is logged -------------------------

    def get_urls(self):
        return [
            path("document/<int:pk>/", self.admin_site.admin_view(self.document_view), name="dispatch-document"),
        ] + super().get_urls()

    def document_view(self, request, pk):
        if not (request.user.is_staff and request.user.has_perm("dispatch.view_driverdocument")):
            raise Http404()
        document = DriverDocument.objects.filter(pk=pk).first()
        if document is None:
            raise Http404()
        try:
            content = crypto.decrypt(document.encrypted_data)
        except crypto.DocumentDecryptionError:
            return HttpResponse("This document cannot be decrypted with the current key.", status=500)
        DocumentAccessLog.objects.create(document=document, staff=request.user)
        response = HttpResponse(content, content_type=document.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = "inline"
        return response


@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    list_display = ("document", "staff", "at")
    readonly_fields = ("document", "staff", "at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OfferInline(admin.TabularInline):
    model = DeliveryOffer
    extra = 0
    can_delete = False
    readonly_fields = ("driver", "status")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(OrderDelivery)
class OrderDeliveryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "driver", "pickup_area", "dropoff_area", "fee", "payer", "offered_at")
    list_filter = ("status", "payer")
    search_fields = ("order__id", "driver__full_name")
    # The handover code is deliberately not shown here: only the buyer holds it.
    exclude = ("handover_code", "proof_photo")
    readonly_fields = ("order", "pickup_area", "dropoff_area", "fee", "buyer_share", "seller_share", "payer", "driver", "code_attempts",
                       "offered_at", "nudged_at", "accepted_at", "picked_up_at", "delivered_at", "proof_content_type")
    inlines = [OfferInline]
    actions = ["unlock_code"]

    @admin.action(description="Unlock the handover code after support has checked with the buyer")
    def unlock_code(self, request, queryset):
        queryset.update(code_attempts=0)


@admin.register(ListingDelivery)
class ListingDeliveryAdmin(admin.ModelAdmin):
    list_display = ("listing", "enabled", "payer", "pickup_area")
    list_filter = ("enabled", "payer")

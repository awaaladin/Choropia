from django.contrib import admin

from .models import Offer, OfferEvent


class OfferEventInline(admin.TabularInline):
    model = OfferEvent
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("reference", "status", "amount_kobo", "fee_kobo", "seller", "buyer", "created_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("reference", "seller__email", "buyer__email")
    inlines = [OfferEventInline]
    # Money and parties are locked once made; nobody edits them by hand.
    readonly_fields = [f.name for f in Offer._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

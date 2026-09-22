from django.contrib import admin

from .models import Category, Listing, ListingPhoto


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "merchant", "category", "price", "status", "created_at")
    list_filter = ("status", "condition", "category")
    search_fields = ("title", "description", "owner__email")
    inlines = [ListingPhotoInline]

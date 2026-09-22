from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("order", "reviewer", "reviewee", "rating", "created_at")
    search_fields = ("reviewer__email", "reviewee__email")

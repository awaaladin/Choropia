from django.contrib import admin

from .models import Reel, ReelComment, ReelLike


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "merchant", "listing", "views_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("caption", "owner__email")


@admin.register(ReelLike)
class ReelLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "reel", "created_at")


@admin.register(ReelComment)
class ReelCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "reel", "author", "created_at")

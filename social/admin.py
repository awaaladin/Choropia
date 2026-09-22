from django.contrib import admin

from .models import Comment, Follow, Like

admin.site.register(Follow)
admin.site.register(Like)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("listing", "author", "body", "created_at")
    search_fields = ("body", "author__email")

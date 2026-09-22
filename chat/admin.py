from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "read_at", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "buyer", "seller", "order", "updated_at")
    search_fields = ("listing__title", "buyer__email", "seller__email")
    inlines = [MessageInline]

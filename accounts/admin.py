from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [ProfileInline]
    ordering = ("-date_joined",)
    list_display = ("email", "phone_number", "is_staff", "is_moderator", "is_active", "date_joined")
    list_filter = ("is_staff", "is_moderator", "is_active")
    search_fields = ("email", "phone_number", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "phone_number", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_moderator",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "phone_number", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("date_joined",)

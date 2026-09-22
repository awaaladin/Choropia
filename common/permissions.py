from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object-level permission: only the owner of an object may edit/delete it."""

    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        owner = getattr(obj, self.owner_field, None)
        return owner == request.user


class IsApprovedMerchant(permissions.BasePermission):
    """Grants access only to users with an approved Merchant storefront."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        merchant = getattr(request.user, "merchant", None)
        return bool(merchant and merchant.status == merchant.Status.ACTIVE)


class IsStaffOrModerator(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))

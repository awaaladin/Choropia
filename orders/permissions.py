from rest_framework import permissions


class IsOrderParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        return obj.buyer_id == user.id or obj.seller_id == user.id

from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeviceToken, Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("target_content_type")

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response(status=204)


class DeviceTokenView(APIView):
    """The app registers its Firebase token here after sign-in and removes it on sign-out."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = str(request.data.get("token", "")).strip()
        if not token or len(token) > 300:
            return Response({"token": "A device token is required."}, status=400)
        # A token belongs to one phone: if someone else signed in on it before, it moves to this account.
        DeviceToken.objects.update_or_create(
            token=token, defaults={"user": request.user, "platform": str(request.data.get("platform", "android"))[:10]}
        )
        return Response(status=204)

    def delete(self, request):
        DeviceToken.objects.filter(user=request.user, token=str(request.data.get("token", ""))).delete()
        return Response(status=204)

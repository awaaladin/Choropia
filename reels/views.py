from django.db import IntegrityError
from django.db.models import F
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from common.permissions import IsOwnerOrReadOnly

from .models import Reel, ReelComment, ReelLike
from .serializers import ReelCommentSerializer, ReelLikeSerializer, ReelSerializer


class ReelViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    serializer_class = ReelSerializer

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "listing-create"
        return super().get_throttles()

    def get_queryset(self):
        return Reel.objects.select_related(
            "owner", "owner__profile", "merchant", "listing"
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Reel.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        instance.refresh_from_db(fields=["views_count"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ReelLikeViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = ReelLikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReelLike.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError("Already liked.")


class ReelCommentViewSet(viewsets.ModelViewSet):
    serializer_class = ReelCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = ReelComment.objects.select_related("author")
        reel_id = self.request.query_params.get("reel")
        if reel_id:
            qs = qs.filter(reel_id=reel_id)
        return qs

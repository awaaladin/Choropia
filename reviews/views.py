from rest_framework import mixins, permissions, viewsets

from .models import Review
from .serializers import ReviewSerializer


class ReviewViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Review.objects.select_related("reviewer", "reviewee", "order")
        user_id = self.request.query_params.get("user")
        if user_id:
            qs = qs.filter(reviewee_id=user_id)
        return qs

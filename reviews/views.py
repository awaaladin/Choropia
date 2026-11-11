from django.db.models import F
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.throttling import ScopedWritesMixin
from orders.models import Order

from . import rules
from .models import Review
from .serializers import ReviewSerializer


class ReviewViewSet(ScopedWritesMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    write_throttle_scope = "reviews"
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # Only buyers' ratings of sellers are shown (older seller-to-buyer reviews are kept but not displayed).
        qs = Review.objects.select_related("reviewer", "reviewee", "order").filter(reviewer=F("order__buyer"))
        user_id = self.request.query_params.get("user")
        if user_id:
            qs = qs.filter(reviewee_id=user_id)
        return qs

    def perform_create(self, serializer):
        review = serializer.save()
        _alert_staff(review)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def summary(self, request):
        """GET /reviews/summary/?user=<seller id>: average, count and whether this seller can be rated."""
        from accounts.models import User

        user = User.objects.filter(pk=request.query_params.get("user") or 0).first()
        if user is None:
            return Response({"eligible": False, "average": None, "count": 0, "verified": False})
        return Response(rules.summary(user))

    @action(detail=False, methods=["get"], url_path="for-order")
    def for_order(self, request):
        """GET /reviews/for-order/?order=<id>: can I rate this order's seller, and if not, why."""
        order = Order.objects.filter(pk=request.query_params.get("order") or 0).first()
        if order is None or request.user.id not in (order.buyer_id, order.seller_id):
            return Response({"can_review": False, "reason": "Order not found.", "review": None})
        allowed, reason = rules.check(order, request.user)
        review = Review.objects.filter(order=order, reviewer=request.user).first()
        return Response({
            "can_review": allowed,
            "reason": reason,
            "review": ReviewSerializer(review, context={"request": request}).data if review else None,
        })


def _alert_staff(review):
    from notifications import staff_alerts

    order = review.order
    stars = "\u2605" * review.rating + "\u2606" * (5 - review.rating)
    lines = [
        f"{stars} for {review.reviewee.get_full_name() or review.reviewee.email}, from {review.reviewer.get_full_name() or review.reviewer.email}.",
        f"Order #{order.id}: {order.listing.title}.",
    ]
    if review.comment:
        lines.append(f"Comment: {review.comment}")
    staff_alerts.alert(f"New {review.rating}-star review", "A buyer reviewed a seller", lines, "/staff/inbox/")

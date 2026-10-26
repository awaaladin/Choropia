from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from orders.state_machine import InvalidOrderTransition

from .models import Delivery
from .serializers import DeliverySerializer, DeliveryStatusUpdateSerializer
from .services import apply_courier_status_update


class DeliveryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Delivery.objects.filter(Q(order__buyer=user) | Q(order__seller=user)).select_related("order")

    @action(detail=True, methods=["post"])
    def advance_status(self, request, pk=None):
        """Simulates (or, for a real provider, receives) a courier status callback."""
        delivery = self.get_object()
        # The buyer has confirm_receipt and open_dispute; letting them (or anyone but the seller or
        # staff) push courier status would let a delivery be faked from the wrong side.
        if request.user.id != delivery.order.seller_id and not request.user.is_staff:
            raise PermissionDenied()

        serializer = DeliveryStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            apply_courier_status_update(delivery, serializer.validated_data["status"])
        except InvalidOrderTransition as exc:
            raise ValidationError(str(exc))

        return Response(DeliverySerializer(delivery).data)

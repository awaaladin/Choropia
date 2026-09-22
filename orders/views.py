from django.db import transaction
from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from common.permissions import IsStaffOrModerator

from .models import Order
from .permissions import IsOrderParticipant
from .serializers import (
    DisputeResolutionSerializer,
    DisputeSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)
from .state_machine import InvalidOrderTransition, OrderStatus


class OrderViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]

    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(Q(buyer=user) | Q(seller=user)).select_related(
            "listing", "buyer", "seller"
        ).prefetch_related("history", "listing__photos")

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=201)

    def _transition_or_400(self, order, target_status, actor, note=""):
        try:
            order.transition_to(target_status, actor=actor, note=note)
        except InvalidOrderTransition as exc:
            raise ValidationError(str(exc))
        return order

    @action(detail=True, methods=["post"])
    def assign_courier(self, request, pk=None):
        order = self.get_object()
        if request.user.id != order.seller_id:
            raise PermissionDenied("Only the seller can assign a courier.")

        from delivery.services import create_shipment_for_order

        self._transition_or_400(order, OrderStatus.COURIER_ASSIGNED, actor=request.user)
        create_shipment_for_order(order)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def confirm_receipt(self, request, pk=None):
        order = self.get_object()
        if request.user.id != order.buyer_id:
            raise PermissionDenied("Only the buyer can confirm receipt.")

        from payments.services import release_escrow

        with transaction.atomic():
            self._transition_or_400(order, OrderStatus.CONFIRMED, actor=request.user)
            self._transition_or_400(order, OrderStatus.COMPLETED, actor=request.user)
            release_escrow(order, auto=False)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def open_dispute(self, request, pk=None):
        order = self.get_object()
        if request.user.id not in (order.buyer_id, order.seller_id):
            raise PermissionDenied()

        serializer = DisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order.dispute_reason = serializer.validated_data["reason"]
        order.save(update_fields=["dispute_reason"])
        self._transition_or_400(
            order, OrderStatus.DISPUTED, actor=request.user, note=serializer.validated_data["reason"]
        )
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrModerator])
    def resolve_dispute(self, request, pk=None):
        order = self.get_object()
        serializer = DisputeResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from payments.services import refund_escrow, release_escrow

        with transaction.atomic():
            if serializer.validated_data["resolution"] == "refund":
                self._transition_or_400(order, OrderStatus.REFUNDED, actor=request.user)
                refund_escrow(order)
            else:
                self._transition_or_400(order, OrderStatus.COMPLETED, actor=request.user)
                release_escrow(order, auto=False)

        return Response(OrderSerializer(order).data)

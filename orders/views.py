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

    # The courier stages a buyer who already has the item in their hands skips over.
    _NEXT_COURIER_STAGE = {
        OrderStatus.PAID_ESCROW: OrderStatus.COURIER_ASSIGNED,
        OrderStatus.COURIER_ASSIGNED: OrderStatus.IN_TRANSIT,
        OrderStatus.IN_TRANSIT: OrderStatus.DELIVERED,
    }

    @action(detail=True, methods=["post"])
    def confirm_receipt(self, request, pk=None):
        """The buyer says they have the item; the seller is paid. Works at any stage from "paid" on, because
        a buyer who meets the seller and takes the item must not have to wait for the seller to tick boxes.
        The skipped stages are still written to the order history (marked [auto] so nobody is spammed)."""
        order = self.get_object()
        if request.user.id != order.buyer_id:
            raise PermissionDenied("Only the buyer can confirm receipt.")

        from payments.services import release_escrow

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            while order.status in self._NEXT_COURIER_STAGE:
                self._transition_or_400(
                    order, self._NEXT_COURIER_STAGE[order.status], actor=request.user,
                    note="[auto] Buyer confirmed receipt in person",
                )
            self._transition_or_400(order, OrderStatus.CONFIRMED, actor=request.user)
            self._transition_or_400(order, OrderStatus.COMPLETED, actor=request.user)
            release_escrow(order, auto=False)
        return Response(OrderSerializer(order, context={"request": request}).data)

    def _seller_step(self, request, order, target_status, delivery_status):
        if request.user.id != order.seller_id:
            raise PermissionDenied("Only the seller can do that.")
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            self._transition_or_400(order, target_status, actor=request.user)
            from delivery.models import Delivery

            Delivery.objects.filter(order=order).update(status=delivery_status)
        return Response(OrderSerializer(order, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def mark_in_transit(self, request, pk=None):
        """Seller: the item has left (handed to a rider, or on its way to the buyer)."""
        return self._seller_step(request, self.get_object(), OrderStatus.IN_TRANSIT, "in_transit")

    @action(detail=True, methods=["post"])
    def mark_delivered(self, request, pk=None):
        """Seller: the item has reached the buyer. Starts the buyer's confirm-or-dispute window; if they do
        neither, the escrow auto-release pays the seller after ESCROW_AUTO_RELEASE_DAYS."""
        return self._seller_step(request, self.get_object(), OrderStatus.DELIVERED, "delivered")

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

        from payments.paystack import PaystackError
        from payments.services import refund_escrow, release_escrow

        try:
            with transaction.atomic():
                if serializer.validated_data["resolution"] == "refund":
                    self._transition_or_400(order, OrderStatus.REFUNDED, actor=request.user)
                    refund_escrow(order)
                else:
                    self._transition_or_400(order, OrderStatus.COMPLETED, actor=request.user)
                    release_escrow(order, auto=False)
        except PaystackError as exc:
            # The refund didn't go through, so the order stays disputed (the transaction rolled back).
            return Response({"detail": f"Paystack refund failed: {exc}"}, status=502)

        return Response(OrderSerializer(order).data)

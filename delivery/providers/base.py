"""
Abstract courier interface. A real courier partner (e.g. GIG Logistics,
Kwik, or an in-house rider network for the Uyo pilot) plugs in by
implementing this interface and pointing settings.DELIVERY_PROVIDER at it —
nothing in the Order state machine or the `delivery` app's models needs to
change.
"""
from abc import ABC, abstractmethod


class DeliveryStatus:
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"


class ShipmentResult:
    def __init__(self, tracking_id, status=DeliveryStatus.PENDING, meta=None):
        self.tracking_id = tracking_id
        self.status = status
        self.meta = meta or {}


class DeliveryProvider(ABC):
    @abstractmethod
    def create_shipment(self, order) -> ShipmentResult:
        """Book a shipment for the given Order and return a ShipmentResult with a tracking_id."""

    @abstractmethod
    def get_status(self, tracking_id: str) -> str:
        """Return one of the DeliveryStatus values for the given tracking id."""

    @abstractmethod
    def cancel_shipment(self, tracking_id: str) -> bool:
        """Cancel a booked shipment. Returns True if the cancellation succeeded."""

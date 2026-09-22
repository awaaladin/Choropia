import uuid

from .base import DeliveryProvider, DeliveryStatus, ShipmentResult


class MockDeliveryProvider(DeliveryProvider):
    """Simulates a courier for local dev/demo. Every shipment starts PENDING and is progressed
    manually (via the /delivery/<id>/advance/ endpoint) or by the seed/demo tooling — there's no
    real dispatch network behind it."""

    def create_shipment(self, order):
        tracking_id = f"MOCK-{uuid.uuid4().hex[:10].upper()}"
        return ShipmentResult(tracking_id=tracking_id, status=DeliveryStatus.PENDING)

    def get_status(self, tracking_id):
        return DeliveryStatus.PENDING

    def cancel_shipment(self, tracking_id):
        return True

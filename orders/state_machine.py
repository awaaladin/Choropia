"""
The Order status graph, isolated from the model so it can be unit-tested and
reasoned about on its own. This is the highest-risk logic in the app — an
order represents real money in escrow and a real parcel in transit, so a
transition that isn't in this graph must never be allowed to happen, silently
or otherwise.
"""


class OrderStatus:
    PENDING_PAYMENT = "pending_payment"
    PAID_ESCROW = "paid_escrow"
    COURIER_ASSIGNED = "courier_assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    COMPLETED = "completed"
    REFUNDED = "refunded"

    CHOICES = (
        (PENDING_PAYMENT, "Pending payment"),
        (PAID_ESCROW, "Paid into escrow"),
        (COURIER_ASSIGNED, "Courier assigned"),
        (IN_TRANSIT, "In transit"),
        (DELIVERED, "Delivered"),
        (CONFIRMED, "Confirmed by buyer"),
        (DISPUTED, "Disputed"),
        (COMPLETED, "Completed"),
        (REFUNDED, "Refunded"),
    )

    TERMINAL = {COMPLETED, REFUNDED}


# Explicit allow-list of transitions. Anything not listed here is rejected —
# there is no default/fallback path.
TRANSITIONS = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.PAID_ESCROW},
    OrderStatus.PAID_ESCROW: {OrderStatus.COURIER_ASSIGNED},
    OrderStatus.COURIER_ASSIGNED: {OrderStatus.IN_TRANSIT},
    OrderStatus.IN_TRANSIT: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.CONFIRMED, OrderStatus.DISPUTED},
    OrderStatus.CONFIRMED: {OrderStatus.COMPLETED},
    OrderStatus.DISPUTED: {OrderStatus.REFUNDED, OrderStatus.COMPLETED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.REFUNDED: set(),
}


class InvalidOrderTransition(Exception):
    def __init__(self, current_status, target_status):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(f"Cannot transition order from '{current_status}' to '{target_status}'.")


def validate_transition(current_status, target_status):
    allowed = TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise InvalidOrderTransition(current_status, target_status)


def is_terminal(status):
    return status in OrderStatus.TERMINAL

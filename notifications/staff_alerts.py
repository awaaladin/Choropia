"""Emails to the people who run Choropia, for things the system cannot decide by itself.

Everything that needs a human (a driver to check, a dispute to settle, money to hand over, a payout that got stuck) sends one
short email to STAFF_ALERT_EMAILS (hiexecontact@gmail.com by default) with a button into the staff panel. A once-a-day
reminder (see staffpanel/digest.py) catches anything left waiting. An alert can never fail the thing that triggered it."""
import logging

from django.conf import settings

from . import emails

logger = logging.getLogger(__name__)


def alert(subject: str, headline: str, lines: list[str], path: str = "/staff/") -> None:
    """Queues the alert to go out after the current database transaction commits."""
    try:
        if not settings.STAFF_ALERTS_ENABLED:
            return
        for to in settings.STAFF_ALERT_EMAILS:
            emails.send_email_after_commit(
                to,
                f"[Choropia admin] {subject}",
                "staff_alert",
                {"headline": headline, "lines": lines, "link": path},
            )
    except Exception:  # noqa: BLE001 - an alert must never break the request that caused it
        logger.exception("Could not queue a staff alert: %s", subject)


def money(amount) -> str:
    return emails.naira(amount)

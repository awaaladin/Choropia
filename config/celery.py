import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("choropia")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "auto-release-escrow-every-hour": {
        "task": "payments.tasks.auto_release_escrow_task",
        "schedule": crontab(minute=0),
    },
    "poll-paystack-payments-every-5-minutes": {
        "task": "payments.tasks.poll_paystack_payments_task",
        "schedule": 300.0,
    },
    "auto-refund-undispatched-hourly": {
        "task": "payments.tasks.auto_refund_undispatched_task",
        "schedule": crontab(minute=30),
    },
    "retry-pending-refunds-every-10-minutes": {
        "task": "payments.tasks.retry_pending_refunds_task",
        "schedule": 600.0,
    },
    "process-payouts-every-5-minutes": {
        "task": "payments.tasks.process_payouts_task",
        "schedule": 300.0,
    },
    "dispatch-nudges-every-15-minutes": {
        "task": "dispatch.tasks.nudge_stale_offers_task",
        "schedule": 900.0,
    },
    "poll-gaxtron-payments-every-2-minutes": {
        "task": "payments.tasks.poll_gaxtron_payments_task",
        "schedule": 120.0,
    },
}

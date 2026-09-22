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
}

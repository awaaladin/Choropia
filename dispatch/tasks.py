from celery import shared_task


@shared_task
def nudge_stale_offers_task():
    from .services import nudge_stale_offers

    return nudge_stale_offers()

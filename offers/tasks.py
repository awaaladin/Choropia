from celery import shared_task


@shared_task
def expire_offers_task():
    from .services import expire_due_offers

    return expire_due_offers()

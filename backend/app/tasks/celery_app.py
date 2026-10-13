from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("orderflow", broker=settings.broker_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_delivery_mode="persistent",
    broker_transport_options={"confirm_publish": True},
    broker_connection_timeout=3,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=240,
    task_time_limit=300,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={},
)

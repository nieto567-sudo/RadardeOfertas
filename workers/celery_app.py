"""
Celery application factory.
"""
from celery import Celery

from config.settings import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

app = Celery(
    "radardeofertas",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["workers.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Mexico_City",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

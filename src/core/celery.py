from celery import Celery
from src.core.config import settings

import src.auth.models  # noqa: F401
import src.interviews.models  # noqa: F401

celery_app = Celery(
    "app",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.tasks.generation"]
)

celery_app.conf.update(
    task_track_started=True,
)

from celery import Celery
from common.utils.config import settings
import os

# Create Celery application
app = Celery(
    "market_data_system",
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/1",
)

# Configure Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.timezone,
    enable_utc=True,
)

import os

from celery import Celery
from django.conf import settings
from judoscale.celery import judoscale_celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'
app.autodiscover_tasks()

judoscale_celery(app, extra_config=settings.JUDOSCALE)
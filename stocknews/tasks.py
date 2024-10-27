from unittest.mock import call
from celery.app import shared_task
from django.core.management import call_command


@shared_task
def fetch_news_task():
    call_command("fetch_news3")

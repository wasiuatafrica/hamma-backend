from celery.app import shared_task
from .asset_classify import classify


@shared_task
def classify_asset_task():
    classify()

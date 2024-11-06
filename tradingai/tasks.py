from celery.app import shared_task
from .asset_classify import classify
from .signal_scrape import get_signal_tv


@shared_task
def classify_asset_task():
    classify()


@shared_task
def get_tv_signal_task():
    get_signal_tv()

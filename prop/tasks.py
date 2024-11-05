from celery.app import shared_task
from .utils import get_all_balance_equity_data


@shared_task
def get_all_balance_equity_data_task():
    get_all_balance_equity_data()

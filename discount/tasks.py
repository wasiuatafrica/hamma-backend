from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import date
from portfolio.models import Wallet, Transaction
from decimal import Decimal
from notifications.utils import save_and_send_notification
from execution.models import Portfolio

from django.core.management import call_command

logger = get_task_logger(__name__)

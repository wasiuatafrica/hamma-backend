from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.core.management import call_command
from portfolio.models import Wallet,Portfolio
from execution.trades import simulate_trades
from accounts.utils import send_welcome_email

logger = get_task_logger(__name__)

User=get_user_model()

@shared_task
def set_up_user(user_email):
    user=User.objects.get(email=user_email)
    Wallet.objects.create(user=user)
    Portfolio.objects.create(user=user)
    send_welcome_email(user)
    simulate_trades(user)
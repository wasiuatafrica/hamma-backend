from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.core.management import call_command
from execution.trades import simulate_trades
from accounts.utils import send_welcome_email
from execution.models import DemoDailyReturns, DailyReturns, get_price



logger = get_task_logger(__name__)

User=get_user_model()

@shared_task
def set_up_user(user_email):
    user=User.objects.get(email=user_email)
    simulate_trades(user)
    
@shared_task
def daily_returns_setup(id):
    user= User.objects.get(id=id)
    data = get_price ('ASI')
    pr = data['current_price']
    DemoDailyReturns.objects.create(user=user, ngx_price = pr)
    DailyReturns.objects.create(user=user, ngx_price = pr)
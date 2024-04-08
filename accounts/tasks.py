from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from execution.trades import simulate_trades
from execution.models import DemoDailyReturns, DailyReturns, get_price
from django.template.loader import render_to_string
from django.core.mail import send_mail

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
    
@shared_task
def send_welcome_email(id):
    user = User.objects.get(id=id)
    # Send token to users email
    context={
        "firstname":user.firstname.title()
    }
    html_message = render_to_string('competition/welcome_competition2.html', context)
    plain_message = ""
    subject = 'Welcome to Hamma'
    from_email = "teamgohamma@gmail.com"
    recipient_list = [user.email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
from django.core.management.base import BaseCommand
from datetime import datetime,timedelta,time
from django.contrib.auth import get_user_model
import time
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.utils import timezone
from execution.trades import simulate_trades
from execution.models import DemoDailyReturns, DailyReturns, DemoDailyReturns2, get_price, DemoCumulativeReturns
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django_celery_beat.models import PeriodicTask, CrontabSchedule

User =get_user_model()

def create_crontab(target_time):
    start_schedule, created1 = CrontabSchedule.objects.get_or_create(
            minute=target_time.minute,
            hour=target_time.hour,
            day_of_month=target_time.day,
            month_of_year=target_time.month
            )
    return start_schedule

def send_welcome_email(user):
    # user = User.objects.get(id=id)
    
    schedule1 = create_crontab(timezone.now()   + timedelta(minutes=5))
    schedule2 = create_crontab(timezone.now()  + timedelta(hours=12))
    schedule3 = create_crontab(timezone.now()  + timedelta(hours=24))
    
    PeriodicTask.objects.create(
        name=f"join clan {user.email} email",
        task='accounts.tasks.welcome_1b',
        one_off=True,
        crontab = schedule1
    )
    
    PeriodicTask.objects.create(
        name=f"create clan {user.email} email",
        task='accounts.tasks.welcome_1c',
        one_off=True,
        crontab = schedule2
    )
    
    PeriodicTask.objects.create(
        name=f"SM invite {user.email} email",
        task='accounts.tasks.after_signup_36h',
        one_off=True,
        crontab = schedule3
    )
    
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        yesterday = timezone.now().date() - timedelta(days=1)
        # cutoff_time = datetime.combine(yesterday, time(20, 0))  # 8 PM
        # cutoff_time = timezone.make_aware(datetime.combine(yesterday, time(20, 0)))
        cutoff_time = datetime(yesterday.year, yesterday.month, yesterday.day, 20, 0)


        # Filter users where date_joined is less than cutoff_time
        users = User.objects.filter(date_joined__lte=cutoff_time)
        # users = User.objects.all()
        for user in users:
            send_welcome_email(user)
            print(user.email,'scheduled')
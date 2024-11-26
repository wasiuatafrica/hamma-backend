from datetime import timedelta
import json
import time
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.utils import timezone
from execution.trades import simulate_trades
from execution.models import (
    DemoDailyReturns,
    DailyReturns,
    DemoDailyReturns2,
    get_price,
    DemoCumulativeReturns,
)
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django_celery_beat.models import PeriodicTask, CrontabSchedule

logger = get_task_logger(__name__)

User = get_user_model()


@shared_task
def set_up_user(user_email):
    user = User.objects.get(email=user_email)
    simulate_trades(user)


@shared_task
def after_signup_36h(id):  # 36h
    user = User.objects.get(id=id)

    context = {"firstname": user.firstname, "email": user.email}
    html_message = render_to_string("competition/after_signup_36h.html", context)
    plain_message = ""
    subject = "Are We Friends on Social Media?"
    from_email = "Hamma Team <teamgohamma@gmail.com>"
    recipient_list = [user.email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )


@shared_task
def welcome_1c(id):  # 24h
    user = User.objects.get(id=id)

    context = {
        "email": user.email
        # "firstname":user.firstname,
    }
    html_message = render_to_string("competition/welcome_1c.html", context)
    plain_message = ""
    subject = "Why You Should Create a Clan!"
    from_email = "Hamma Team <teamgohamma@gmail.com>"
    recipient_list = [user.email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )


@shared_task
def welcome_1b(id):  # 12h
    user = User.objects.get(id=id)

    context = {"firstname": user.firstname, "email": user.email}
    html_message = render_to_string("competition/welcome_1b.html", context)
    plain_message = ""
    subject = "Why You Should Join a Clan!"
    from_email = "Hamma Team <teamgohamma@gmail.com>"
    recipient_list = [user.email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )


@shared_task
def daily_returns_setup(id):
    user = User.objects.get(id=id)
    DemoDailyReturns2.objects.create(user=user, created=timezone.now())
    DemoCumulativeReturns.objects.create(user=user, created=timezone.now())


def create_crontab(target_time):
    start_schedule, created1 = CrontabSchedule.objects.get_or_create(
        minute=target_time.minute,
        hour=target_time.hour,
        day_of_month=target_time.day,
        month_of_year=target_time.month,
    )
    return start_schedule


@shared_task
def send_welcome_email(id):
    user = User.objects.get(id=id)
    # Send token to users email
    context = {"firstname": user.firstname.title()}
    html_message = render_to_string("competition/welcome_competition2.html", context)
    plain_message = ""
    subject = "Welcome to Hamma"
    from_email = "Hamma Team <teamgohamma@gmail.com>"
    recipient_list = [user.email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )

    schedule1 = create_crontab(timezone.now() + timedelta(hours=12))
    schedule2 = create_crontab(timezone.now() + timedelta(hours=24))
    schedule3 = create_crontab(timezone.now() + timedelta(hours=48))

    PeriodicTask.objects.create(
        name=f"join clan {user.email} email",
        task="accounts.tasks.welcome_1b",
        one_off=True,
        crontab=schedule1,
        args=json.dumps([user.id]),
    )

    PeriodicTask.objects.create(
        name=f"create clan {user.email} email",
        task="accounts.tasks.welcome_1c",
        one_off=True,
        crontab=schedule2,
        args=json.dumps([user.id]),
    )

    PeriodicTask.objects.create(
        name=f"SM invite {user.email} email",
        task="accounts.tasks.after_signup_36h",
        one_off=True,
        crontab=schedule3,
        args=json.dumps([user.id]),
    )


@shared_task
def send_prop_welcome_email(id):
    user = User.objects.get(id=id)
    # Send token to users email
    context = {"firstname": user.firstname.title()}
    html_message = render_to_string("prop/welcome_hamma_prop.html", context)
    plain_message = ""
    subject = "🌟 Welcome to Hamma Prop firm! Let's Get This Bread 🤑"
    from_email = "Hamma Prop <hello@hamma.trade>"
    recipient_list = [user.email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )

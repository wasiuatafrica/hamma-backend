from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model
from competition.tasks import trading_rule_task
from competition.start_competition_mails import send_trade_reminder

from django.utils import timezone
User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        user = User.objects.get(email='nexxyb@gmail.com')
        # trading_rule_task(user.id)
        send_trade_reminder(user)
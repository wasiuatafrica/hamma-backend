from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from portfolio.models import Wallet
from execution.models import Portfolio

from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = ""

    def handle(self, *args, **options):

        user = User.objects.get(email="effiongr98@gmail.com")
        user.delete()

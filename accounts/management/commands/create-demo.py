from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
import portfolio
from portfolio.models import Wallet
from execution.models import Portfolio, DemoPortfolio

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        users = User.objects.all()
        for user in users:
            portfolio = DemoPortfolio.objects.filter(user=user).first()
            if not portfolio:
                DemoPortfolio.objects.create(user=user)
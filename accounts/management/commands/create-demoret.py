from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
import portfolio
from portfolio.models import Wallet
from execution.models import DailyReturns2, DemoCumulativeReturns, Portfolio, DemoPortfolio, DemoDailyReturns2

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        portfolios = DemoPortfolio.objects.all()
        for portfolio in portfolios:
            returns = DemoDailyReturns2.objects.filter(portfolio=portfolio)
            if not returns.exists():
                DemoDailyReturns2.objects.create(portfolio=portfolio, created=timezone.now(), user= portfolio.user)
                DemoCumulativeReturns.objects.create(portfolio=portfolio, created=timezone.now(),user= portfolio.user)
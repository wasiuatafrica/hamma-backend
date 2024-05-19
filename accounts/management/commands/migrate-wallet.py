from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from portfolio.models import Wallet
from execution.models import Portfolio

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        portfolios = Portfolio.objects.all()
        for portfolio in portfolios:
            if portfolio.balance > 0:
                print(portfolio.user, portfolio.balance)
                # wallet = Wallet.objects.get(user=portfolio.user)
                # wallet.balance = portfolio.balance
                # wallet.save()
                # print('wallet balance updated for user', portfolio.user)
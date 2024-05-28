import json
from math import e
from django.core.management.base import BaseCommand
from competition.models import get_price
import portfolio
from portfolio.models import Stock
from execution.models import DemoPortfolio
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()



class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        
            portfolios = DemoPortfolio.objects.all()
            for portfolio in portfolios:
                if portfolio.balance == 0:
                    print(portfolio.user.email)
                    portfolio.balance=1000000
                    portfolio.save()

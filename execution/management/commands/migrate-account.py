# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
import competition
from hackathon.models import Competition
from portfolio.utils import get_stockdata2
from execution.models import DemoPortfolio, DemoDailyReturns2, DemoCumulativeReturns, CumulativeMarketReturns, MarketReturns, CompetitionMarketReturns, CompetitionCumulativeMarketReturns
from django.contrib.auth import get_user_model
from competition.models import CompetitionPortfolio, CompetitionDailyReturns

User = get_user_model()

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            portfolio = DemoPortfolio.objects.filter(user=user)
            competitions = CompetitionPortfolio.objects.filter(user=user)
            daily_returns = DemoDailyReturns2.objects.filter(user=user)
            print (user.email)
            print (portfolio )
            print(competitions)
            print (daily_returns)
       
            
            
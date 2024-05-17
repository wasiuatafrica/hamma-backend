# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
import competition
from execution.tasks import daily_returns
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
            
            if portfolio.exists():
                portfolio = portfolio.first()
                daily_returns=DemoDailyReturns2.objects.filter(portfolio=portfolio)
                # daily_returns2 = daily_returns.filter(portfolio=portfolio)
                market_returns = MarketReturns.objects.all()
                for dr in daily_returns:
                    # print(dr.created, dr.portfolio, dr.portfolio_returns, dr.market_returns)
                    for market in market_returns:
                        if market.created.date() == dr.created.date():
                            print(market.created, market.market_returns)
                            dr.market_returns = market.market_returns
                            # dr.save()
                            
                
            
            
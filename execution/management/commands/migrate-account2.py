
from django.core.management.base import BaseCommand
from execution.models import DemoPortfolio, DemoDailyReturns2, DemoCumulativeReturns, CumulativeMarketReturns, MarketReturns
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            print(user)
            portfolio = DemoPortfolio.objects.filter(user=user)
            market_returns = MarketReturns.objects.all()
            cum_market_returns = CumulativeMarketReturns.objects.all()
            
            
            if portfolio.exists():
                portfolio = portfolio.first()
                
                daily_returns=DemoDailyReturns2.objects.filter(portfolio=portfolio).order_by('created')  
                if daily_returns.exists():
                    if daily_returns.count() > 1:
               
                        print('daily')
                        for dr in daily_returns[1:]:
                            # print(dr.created, dr.portfolio, dr.portfolio_returns, dr.market_returns)
                            
                            for market in market_returns:
                                if market.created.date() == dr.created.date():
                                    print(market.created, market.market_returns)
                                    dr.market_returns = market.market_returns
                                    dr.save()
                                    break
                else:
                    DemoDailyReturns2.objects.create(portfolio=portfolio, created=timezone.now(),user=user)
                    
                print('cum')     
                cum_returns  = DemoCumulativeReturns.objects.filter(portfolio=portfolio).order_by('created')   
                if cum_returns.exists():
                            
                    if cum_returns.count() > 1:
                        for dr in cum_returns[1:]:
                            # if dr.portfolio_returns !=0:
                            # print(dr.created, dr.portfolio, dr.portfolio_returns, dr.market_returns)
                            for market in cum_market_returns:
                                if market.created.date() == dr.created.date():
                                    print(market.created, market.market_returns, dr.portfolio.user)
                                    dr.market_returns = market.market_returns     
                                    dr.save()
                                    break
                else:
                    DemoCumulativeReturns.objects.create(portfolio=portfolio,created=timezone.now(),user=user)
                print('next')
                
          
               
            
            
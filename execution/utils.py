
from re import M
from .models import DemoPosition, DemoPortfolio, DemoCumulativeReturns, DemoDailyReturns, DemoDailyReturns2, MarketReturns, CumulativeMarketReturns
from rest_framework import serializers
import pandas as pd
import pytz

from anyon.views import User



class DemoPositionSerializer(serializers.ModelSerializer):
    symbol = serializers.SerializerMethodField()
    class Meta:
        model = DemoPosition
        fields = [
            "id",
            "quantity",
            "open_price",
            "close_price",
            "limit_price",
            "status",
            "created",
            "updated",
            "amount_invested",
            "action",
            "time_in_force",
            "order_type",
            "profit_loss",
            "symbol"
        ]

    def get_symbol(self, obj):
        return obj.stock.symbol
    
def get_positions(user,status=None):
    portfolio = DemoPortfolio.objects.get(user=user)
    if status == 'all' or status == None:
        positions = DemoPosition.objects.filter(portfolio=portfolio)
    else:
        positions = DemoPosition.objects.filter(portfolio=portfolio, status=status)
    
    serializer = DemoPositionSerializer(positions, many=True)
    return serializer.data


def calculate_cumulative_returns():
    """
    Calculates the cumulative returns for each day in the DailyReturns table
    and stores the results in the CumulativeReturns model.
    """
    users = User.objects.all()
    returns = DemoDailyReturns.objects.all().order_by('created')
    
    for user in users:
        
        daily_returns = returns.filter(user=user)

        if daily_returns.exists():
            data = {
                'portfolio_returns': [dr.portfolio_returns/100 for dr in daily_returns],
                'market_returns': [dr.market_returns/100 for dr in daily_returns],
                'ngx_price': [dr.ngx_price for dr in daily_returns],
                'user': [dr.user for dr in daily_returns],
                'created': [dr.created for dr in daily_returns]
            }
            df = pd.DataFrame(data)
            
            print(df)

            df['portfolio_cumulative'] = ((1 + df['portfolio_returns']).cumprod() - 1) *100
            df['market_cumulative'] = ((1 + df['market_returns']).cumprod() - 1) *100

            print(df)
            for index, row in df.iterrows():
                DemoCumulativeReturns.objects.create(
                    user=user,
                    portfolio_returns=round(row['portfolio_cumulative'],2),
                    market_returns=round(row['market_cumulative'],2),
                    ngx_price=row['ngx_price'],
                    created=row['created']
                )
        else:
            DemoCumulativeReturns.objects.create(
                    user=user
                )
            
def calculate_cumulative_returns_user(user):
    """
    Calculates the cumulative returns for each day in the DailyReturns table
    and stores the results in the CumulativeReturns model.
    """
    
        
    daily_returns = DemoDailyReturns.objects.filter(user=user)

    if daily_returns.exists():
        data = {
            'portfolio_returns': [dr.portfolio_returns/100 for dr in daily_returns],
            'market_returns': [dr.market_returns/100 for dr in daily_returns],
            'ngx_price': [dr.ngx_price for dr in daily_returns],
            'user': [dr.user for dr in daily_returns],
            'created': [dr.created for dr in daily_returns]
        }
        df = pd.DataFrame(data)
        
        # print(df)

        df['portfolio_cumulative'] = ((1 + df['portfolio_returns']).cumprod() - 1) *100
        df['market_cumulative'] = ((1 + df['market_returns']).cumprod() - 1) *100

        print(df)
        for index, row in df.iterrows():
            DemoCumulativeReturns.objects.create(
                user=user,
                portfolio_returns=round(row['portfolio_cumulative'],2),
                market_returns=round(row['market_cumulative'],2),
                ngx_price=row['ngx_price'],
                created=row['created']
            )
from django.utils import timezone

def daily_returns2():
    users = User.objects.all()
    for user in users:
        print(user)
        positions = DemoPosition.objects.filter(portfolio__user=user, status='close')
        if positions.exists():
            
            data = {
            'email': [position.portfolio.user.email for position in positions],
            'Stock': [position.stock.symbol for position in positions],
            'Quantity': [position.quantity for position in positions],
            'Open_Price': [position.open_price for position in positions],
            'Close_Price': [position.close_price for position in positions],
            'Status': [position.get_status_display() for position in positions],
            'closedatetime': [timezone.localtime(position.updated).replace(tzinfo=None) for position in positions],
            'Amount_Invested': [float(position.amount_invested) for position in positions],
            
            'Profit_Loss': [float(position.profit_loss) for position in positions],
        }
            df = pd.DataFrame(data)
            
            df["Balance"]= df['Amount_Invested'] + df['Profit_Loss']
            df['Closedate'] = df['closedatetime'].dt.date
            
            df = df[["Stock", "Balance", "Amount_Invested", "Closedate", "closedatetime"]]
            df = df.reset_index(drop=True)
            df = df.sort_values(by='closedatetime')
            
            df['Sum_Balance'] = df.groupby('Closedate')['Balance'].cumsum()
            df['Sum_Invested'] = df.groupby('Closedate')['Amount_Invested'].cumsum()
            
            df['Daily_PortfolioReturns'] = ((df['Sum_Balance']/df['Sum_Invested'])-1)*100
            
            idx_max_time = df.groupby('Closedate')['closedatetime'].idxmax()

            max_time = df.loc[idx_max_time].reset_index(drop=True).sort_values(by='closedatetime')
            
            # print(max_time)
            
            for index, row in max_time.iterrows():
                # print(row['Daily_PortfolioReturns'], row['closedatetime'])
                DemoDailyReturns2.objects.create(
                user=user,
                portfolio_returns=round(row['Daily_PortfolioReturns'],2),
                created=row['closedatetime']
            )
                
            cum_table = max_time[['closedatetime', 'Sum_Balance','Sum_Invested']]
            cum_table = cum_table.reset_index(drop=True)
            
            cum_table['running_Balance'] = cum_table['Sum_Balance'].cumsum()
            cum_table['running_Invested'] = cum_table['Sum_Invested'].cumsum()
            cum_table['cum_returns'] = ((cum_table.running_Balance/cum_table.running_Invested)-1)*100
            
            # print(cum_table)
            
            for index, row in cum_table.iterrows():
            
                DemoCumulativeReturns.objects.create(
                    user=user,
                    portfolio_returns=round(row['cum_returns'],2),
                    created=row['closedatetime']
                )
        print('done')
import numpy as np
            
def mark_returns():
    from tvDatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
    df = tv.get_hist(symbol="ASI", exchange='NSENG', interval=Interval.in_daily, n_bars=65)
    ASI_daily_selected = df.reset_index()
    ASI_daily_selected['ASI_daily_retuns'] = ASI_daily_selected['close'].pct_change() * 100
    ASI_daily_selected['Date'] = ASI_daily_selected['datetime'].dt.strftime('%Y-%m-%d')

    for index, row in ASI_daily_selected.iterrows():
        print(row['Date'], row['ASI_daily_retuns'])
        market_returns = row['ASI_daily_retuns']
        if np.isnan(market_returns):
            market_returns = 0  # or any other valid value
        # MarketReturns.objects.create(market_returns=round(market_returns, 2), created=row['datetime'])

    cum_mark_table = ASI_daily_selected[['Date', 'ASI_daily_retuns']]
    cum_mark_table['cum_ASI_daily_retuns'] = (1 + cum_mark_table.ASI_daily_retuns / 100).cumprod() - 1
    cum_mark_table['cum_ASI_daily_retuns'] = cum_mark_table.cum_ASI_daily_retuns * 100

    for index, row in cum_mark_table.iterrows():
        print(row['Date'], row['cum_ASI_daily_retuns'])
        cum_market_returns = row['cum_ASI_daily_retuns']
        if np.isnan(cum_market_returns):
            cum_market_returns = 0  # or any other valid value
        # CumulativeMarketReturns.objects.create(market_returns=round(cum_market_returns, 2), created=row['Date'])
    # print(ASI_daily_selected)

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
    
def daily_returns2():
    users = User.objects.all()
    for user in users:
        print(user)
        positions = DemoPosition.objects.filter(portfolio__user=user, status='close')
        if positions.exists():
            # print(positions)
            data = {
                'user': [p.portfolio.user.email for p in positions],
                'Balance': [float(p.amount_invested + p.profit_loss) for p in positions],
                'Invested': [float(p.amount_invested) for p in positions],
                'Closedate': [p.created.date() for p in positions],
                'DateTime': [p.created for p in positions],
            }

            df = pd.DataFrame(data)
            df['DateTime'] = pd.to_datetime(df['DateTime'])
            df['DateTime'] = df['DateTime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df = df.sort_values(by='DateTime')

            df['Sum_Balance'] = df.groupby('Closedate')['Balance'].cumsum()
            df['Sum_Invested'] = df.groupby('Closedate')['Invested'].cumsum()
            df['Daily_PortfolioReturns'] = (df['Sum_Balance'] / df['Sum_Invested']) - 1

            tz = pytz.timezone('Africa/Lagos')
            df['DateTime'] = pd.to_datetime(df['DateTime']).dt.tz_localize(tz)
            
            # print(df)
            idx_max_time = df.groupby('Closedate')['DateTime'].idxmax()
            max_time = df.loc[idx_max_time].reset_index(drop=True).sort_values(by='DateTime')

            
            max_time['running_Balance'] = max_time['Sum_Balance'].cumsum()
            max_time['running_Invested'] = max_time['Sum_Invested'].cumsum()
            
            max_time['cum_returns'] = (max_time.running_Balance/max_time.running_Invested)-1
            print(max_time)
            
            for index, row in max_time.iterrows():
                DemoDailyReturns2.objects.create(
                    user=user,
                    portfolio_returns=round(row['Daily_PortfolioReturns']*100,2),
                    created=row['DateTime']
                )
                
                DemoCumulativeReturns.objects.create(
                    user=user,
                    portfolio_returns=round(row['running_Profit']*100,2),
                    created=row['DateTime']
                )
            print('done')
            
def mark_returns():
    from tvDatafeed import TvDatafeed, Interval
    tv = TvDatafeed()
    
    df = tv.get_hist(symbol="ASI", exchange='NSENG', interval=Interval.in_daily, n_bars=65)
    # print(data.head(27))
    
    df['Sum_Balance'] = df['close'].cumsum()

    
    print(df.head(27))
    
    # returns=  DemoDailyReturns.objects.filter(user__email='nexxyb@gmail.com')
    
    # for return_ in returns:
    #     MarketReturns.objects.create(market_returns=return_.market_returns, created=return_.created, ngx_price = return_.ngx_price)
    
    # simple_markets = MarketReturns.objects.all()
     
    # data = {
    #     'market_returns': [mr.market_returns for mr in simple_markets],
    #     'datetime': [mr.created for mr in simple_markets],
    #     'ngx_price': [mr.ngx_price for mr in simple_markets]
        
    # }
    
    # df = pd.DataFrame(data)
    # df['datetime'] = pd.to_datetime(df['datetime'])
    # df['cum_market_returns'] = ((1 + df['market_returns']).cumprod() - 1)
    # print(df)
    # for index, row in df.iterrows():
    #         CumulativeMarketReturns.objects.create(
    #             market_returns=round(row['cum_market_returns'],2),
    #             created=row['datetime'],
                
    #         )
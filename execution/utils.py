
from .models import DemoPosition, DemoPortfolio, DemoCumulativeReturns, DemoDailyReturns
from rest_framework import serializers
import pandas as pd

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
    
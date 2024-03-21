from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Avg, F
import auto_prefetch
from decimal import Decimal
from datetime import datetime, timedelta
import json
import websockets
import asyncio
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
import competition
import portfolio
from portfolio.models import  Stock, Trade
from portfolio.utils import connect_to_mongodb

User=get_user_model()

async def connect_to_websocket(stock_symbol):
    # uri = f"ws://localhost:8765/{stock_symbol}"
    uri = f"ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765/{stock_symbol}"

    async with websockets.connect(uri) as websocket:
        try:
            # Sending authentication token
            auth_token = "Ab$455"
            await websocket.send(auth_token)

            
            data = await websocket.recv()
            stock_data = json.loads(data)
            print(stock_data)
            return stock_data
        except websockets.exceptions.ConnectionClosed as e:
            if e.code != 1000:
                print(f"Connection closed unexpectedly: {e}")
                
# def get_price(stock):
#     return asyncio.run(connect_to_websocket(stock))

def get_price(symbol):
    from portfolio.utils import connect_to_mongodb
    db = connect_to_mongodb("stock_prices")
    collection = db["price_combined"]
    last_item = collection.find_one(sort=[('_id', -1)])

    return last_item[symbol]

class Competition(auto_prefetch.Model):
    start_date=models.DateTimeField(blank=True)
    end_date=models.DateTimeField(blank=True)
    title=models.CharField(max_length=200, unique=True,blank=True,db_index=True)
    created_at=models.DateTimeField(blank=True,null=True, auto_now_add=True)
    status=models.CharField(max_length=200,default='current', choices=(('current','current'),('closed','closed')),blank=True)
    first_prize=models.CharField(max_length=200,null=True, blank=True)
    second_prize=models.CharField(max_length=200,null=True, blank=True)
    third_prize=models.CharField(max_length=200,null=True, blank=True)
    message=models.TextField(null=True, blank=True)

    
    def __str__(self):
        return f'{self.title} | {self.status}'
    
  

class CompetitionPortfolio(auto_prefetch.Model):
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE, related_name='competition')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='comportfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user}"


 
class CompetitionPosition(auto_prefetch.Model):
    OPEN = 'open'
    CLOSED = 'close'
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    
    STATE_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
        (PENDING,'Pending'),
        (CANCELLED, 'Cancel')
    ]
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, related_name='composition')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, related_name='composition')
    quantity = models.PositiveIntegerField(default=0)
    open_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    close_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    limit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    action = models.CharField(max_length=20, default='buy')
    alert_name = models.CharField(max_length=50, blank=True, null=True)
    time_in_force = models.CharField(max_length=20, default='day')
    order_type = models.CharField(max_length=20, default='market')
    order_id = models.CharField(max_length=40,  blank=True, null=True)
    profit_loss = models.IntegerField(blank=True, null=True)
    
    
    def __str__(self):
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.action} - {self.status}"
    
    def calculate_profit_loss(self):
        price = self.current_price
        current_value = round(self.quantity * price,2)
        # print(self.status)
        if self.status=='open':
            if self.action == 'buy':
                profit_loss = Decimal(current_value) - self.amount_invested
            elif self.action == 'sell':
                profit_loss = self.amount_invested - Decimal(current_value)
        elif self.status=='close':
            profit_loss =  self.profit_loss
            current_value = self.quantity * self.close_price
        else:
            current_value = 0
            profit_loss = 0
        # print(profit_loss)
        return profit_loss, current_value,price


    @property
    def current_price(self):
        return get_price(self.stock.symbol)['current_price']

    
    
    
    
class CompetitionTrade(models.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comtrades')
    position = auto_prefetch.ForeignKey(CompetitionPosition, on_delete=models.CASCADE, related_name='comtrades')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, default='pending')
    order_type = models.CharField(max_length=20, default='buy')
    
    def __str__(self):
        return f'{self.position.stock.symbol} - {self.order_type} - {self.quantity}units at {self.price} - {self.status}'
    
    @property
    def amount(self):
        return self.quantity * self.price    
  

class CompetitionProfitLoss(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comprofitloss')
    profit_loss = models.IntegerField(default=0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

class CompetitionDailyReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comreturns')
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.created}"


    def __str__(self):
        return f"{self.user} - {self.created}"

class CompetitionSummary(auto_prefetch.Model):
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE,null=True, blank=True)
    user=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='competition_summary',null=True, blank=True)
    portfolio=auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, blank=True, null=True)
    profit=models.FloatField(blank=True,null=True)
    created_at=models.DateTimeField(blank=True,null=True, auto_now_add=True)
    updated_at=models.DateTimeField(blank=True,null=True, auto_now=True)
    position=models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} | {self.clan} | {self.competition.title} | {self.position}"

    @property
    def competition_title(self):
        return self.competition.title
    
    # @property
    # def country(self):
    #     user=self.user
    #     profile=Profile.objects.get(user=user)
    #     return profile.country
    
    @property
    def email(self):
        return self.user.email
    
    @property
    def fullname(self):
        return f'{self.user.firstname} {self.user.lastname}'

class CompetitionTransaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comtransactions')
    transaction_type = models.CharField(max_length=50, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'),('buy', 'Buy'), ('sell', 'Sell')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status= models.CharField(max_length=20, default='unprocessed', blank=True,null=True)

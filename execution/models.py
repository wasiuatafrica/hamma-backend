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
from portfolio.models import  Stock
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
    # print(symbol)
    return last_item[symbol]

class DemoPortfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='demoportfolio2')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return f"{self.user}"
    
class DemoPosition(auto_prefetch.Model):
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
    portfolio = auto_prefetch.ForeignKey(DemoPortfolio, on_delete=models.CASCADE, related_name='demopositions2')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, related_name='demopositions2')
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
    profit_loss = models.IntegerField(default=0)
    
    
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

    
    
    
    
class DemoTrade(models.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='demotrades2')
    position = auto_prefetch.ForeignKey(DemoPosition, on_delete=models.CASCADE, related_name='demotrades2')
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
  
# class MasterWallet(auto_prefetch.Model):
#     commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
#     created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     trade = auto_prefetch.ForeignKey(Trade, on_delete=models.CASCADE,related_name='master_wallet', null=True, blank=True)

class DemoProfitLoss(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='demoprofitloss')
    profit_loss = models.IntegerField(default=0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

class DemoDailyReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='demoreturns')
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.created}"


    def __str__(self):
        return f"{self.user} - {self.created}"

class Portfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='portfolio2')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    def __str__(self):
        return f"{self.user}"

class Position(auto_prefetch.Model):
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
    portfolio = auto_prefetch.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='positions2')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, related_name='positions2')
    quantity = models.PositiveIntegerField(default=0)
    open_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    close_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    limit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    action = models.CharField(max_length=20, default='buy')
    alert_name = models.CharField(max_length=20, blank=True, null=True)
    time_in_force = models.CharField(max_length=20, default='day')
    order_type = models.CharField(max_length=20, default='market')
    profit_loss = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.action}"
    
    def calculate_profit_loss(self):
        price = self.current_price
        current_value = self.quantity * price
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

    
class DailyReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='returns')
    portfolio_returns = models.FloatField(default=0)
    market_returns = models.FloatField(default=0)
    ngx_price = models.FloatField(default=0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user} - {self.created}"
    
class WithdrawalRequest(auto_prefetch.Model):
    wallet=auto_prefetch.ForeignKey(Portfolio, on_delete=models.CASCADE)
    amount = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    status= models.CharField(max_length=20, default='Unprocessed', blank=True,null=True)
    flag=models.BooleanField(default=False, null=True, blank=True)
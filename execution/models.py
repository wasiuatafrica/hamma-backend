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
from portfolio.models import  Stock, Trade

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
                
def get_price(stock):
    return asyncio.run(connect_to_websocket(stock))

class DemoPortfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='demoportfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    equity = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

class DemoPosition(auto_prefetch.Model):
    OPEN = 'open'
    CLOSED = 'closed'
    PENDING = 'pending'
    
    STATE_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
        (PENDING,'Pending')
    ]
    portfolio = auto_prefetch.ForeignKey(DemoPortfolio, on_delete=models.CASCADE, related_name='demopositions')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    fill_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    limit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    
    def close_position(self):
        self.state = self.CLOSED
        self.save()
    
    @property
    def calculate_profit_loss(self):
        # current_value = self.quantity * self.current_price
        # profit_loss = current_value - self.amount_invested
        profit_loss = self.current_price - self.fill_price
        return profit_loss


    @property
    def current_price(self):
        return get_price(self.stock.symbol)['current_price']

    @property
    def openpl(self):
        return self.current_price - self.fill_price
    
    
    
class DemoTrade(models.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    position = auto_prefetch.ForeignKey(DemoPosition, on_delete=models.CASCADE, related_name='demotrades')
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
  
class MasterWallet(auto_prefetch.Model):
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    trade = auto_prefetch.ForeignKey(Trade, on_delete=models.CASCADE,related_name='master_wallet', null=True, blank=True)
    
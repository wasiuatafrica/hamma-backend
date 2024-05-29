from email.policy import default
from pyexpat import model
from time import time
from tokenize import blank_re
from django.db import models
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



User= get_user_model()
def get_holding_detail(holding, trades):
    from .utils import get_price
    stock= holding.stock.symbol
    data=get_price(stock)
    id = holding.id
    quantity=holding.quantity
    created = holding.created
    updated = holding.updated
    filled = trades.filter(status='completed').aggregate(total_quantity=Sum('quantity'))['total_quantity'] if trades else 0
    incomplete_ = trades.filter(status='pending')
    
    if not filled :
        filled = 0
    
    if incomplete_:
        incomplete1 = incomplete_.aggregate(total_quantity=Sum('quantity'))['total_quantity']
        if incomplete1:
            incomplete = incomplete1
        else:
            incomplete = 0
    else:
        incomplete = 0
        
    shares= filled + incomplete
    avg_cost = holding.avg_cost() 
    ltp =  Decimal(data['current_price'])
    cur_val = round((ltp * quantity),2)
    pnl = round((ltp - avg_cost) * filled, 2) if avg_cost else 0
    change = round(ltp- avg_cost ,2) if avg_cost else 0
    percent_change = round((change/avg_cost) * 100,2) if avg_cost else 0
    avg_volume_3_months =60000
    volume = 9000000
    return {
            'id':id,
            'stock':stock,
            'quantity':quantity,
            'created':created,
            'updated':updated,
            'filled':filled,
            'incomplete':incomplete,
            'shares':shares,
            'avg_cost':avg_cost,
            'ltp':ltp,
            'cur_val':cur_val,
            'pnl':pnl,
            'change':change,
            'percent_change':percent_change,
            'avg_volume_3_months':avg_volume_3_months,
            'volume':volume,}

def get_holding_details_concurrently(holding):
    try:
        trades = holding.trades.all()
        return get_holding_detail(holding, trades)
    finally:
        # Close the old database connections to avoid connection exhaustion
        close_old_connections()

def get_demo_holding_details_concurrently(holding):
    try:
        trades = holding.demotrades.all()
        return get_holding_detail(holding, trades)
    finally:
        # Close the old database connections to avoid connection exhaustion
        close_old_connections()
      
TRADING_STATUS_CHOICES = [
    ('Listed', 'Listed'),
    ('Delisted', 'Delisted')
]

class Wallet(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.balance}"
    
class Stock(auto_prefetch.Model):
    
    company = models.CharField(max_length=200, default='')
    symbol = models.CharField(max_length=20)
    sector = models.CharField(max_length=50, null=True, blank=True)
    listing_date = models.DateField(_('Listing Date'), null=True, blank=True)
    incorporation_date = models.DateField(_('Incorporation Date'), null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    active = models.BooleanField(default=True)
    logo_url = models.TextField(blank=True, null=True) 
    
    def __str__(self):
        return  self.symbol
    
    @property
    def ltp(self):
        from .utils import get_price
        data=get_price(self.symbol)
        price= data['current_price']
        return price

    
    @property
    def current_price(self):
        from .utils import get_price
        data=get_price(self.symbol)
        price= data['current_price']
        return price



    @property
    def change(self):
        return round(self.ltp - self.current_price,2)

    @property
    def percent_change(self):
        return round((self.change / self.ltp),2) * 100 if self.ltp != 0 else 0

    
class Receipts(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="Reciepts/", max_length=355, blank=True)
    amount = models.IntegerField(blank=True,null=True)
    date = models.DateField(auto_now_add=True)
    receipt_status = models.CharField(max_length=20,default='Unprocessed'  )
    comment = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    approved_date = models.DateTimeField(auto_now=True)
    payment_method= models.CharField(max_length=20,default='Bank Transfer'  )
    flag=models.BooleanField(default=False, null=True, blank=True)
    
    def __str__(self) -> str:
        return f'{self.user}-{self.amount} - {self.receipt_status}'
    
class PayStackReceipts(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    reference=models.CharField(max_length=255, blank=True, null=True)
    transaction=models.CharField(max_length=255, blank=True, null=True)
    amount = models.IntegerField(blank=True,null=True)
    date = models.DateTimeField(auto_now_add=True)
    receipt_status = models.CharField(max_length=20,default='unprocessed')
    comment = models.TextField(blank=True, null=True)
    flag=models.BooleanField(default=False, null=True, blank=True)
    
    
    def __str__(self):
        return f'{self.user}-{self.amount}'
    

    
class Transaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=50, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'),('buy', 'Buy'), ('sell', 'Sell')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status= models.CharField(max_length=20, default='unprocessed', blank=True,null=True)
    channel= models.CharField(max_length=20, blank=True,null=True)
    


    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.amount}"
    
class DemoTransaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='demotransactions')
    transaction_type = models.CharField(max_length=50, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'),('buy', 'Buy'), ('sell', 'Sell')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status= models.CharField(max_length=20, default='unprocessed', blank=True,null=True)


class WithdrawalOTPRequest(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    expiration_time=models.DateTimeField(null=True, blank=True)
    otp= models.IntegerField(blank=True,null=True)
    used=models.BooleanField(default=False)
    created=models.DateTimeField(auto_now_add=True,null=True, blank=True)
  

class Alert(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    stock= auto_prefetch.ForeignKey(Stock,on_delete=models.CASCADE)
    alert_name=models.CharField(max_length=50)
    task_name=models.CharField(max_length=50, blank=True, null=True)
    description=models.TextField(default="")
    alert_type=models.CharField(max_length=30, choices=(("price", "price"), ("volume", "volume")), default='price')
    action=models.CharField(max_length=50, choices=(("above", "above"), ("below", "below")))
    to_price=models.FloatField(blank=True, null=True)
    to_volume=models.FloatField(blank=True, null=True)    
    frequency=models.CharField(max_length=50, choices=(("Once","Once"),("Everytime", "Everytime")), default='Once')
    expire = models.DateTimeField(blank=True, null=True)
    created=models.DateTimeField(auto_now_add=True)
    trigerred = models.BooleanField(default=False)
    last_email_sent = models.DateTimeField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expire:
            last_day_of_month = timezone.now().replace(day=1, month=(timezone.now().month % 12) + 1, hour=22, minute=59, second=59) - timedelta(days=1)
            self.expire = last_day_of_month
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.email}|{self.id} {self.created} {self.stock.symbol} alert"
    
class AlertAI(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    prompt=models.TextField()
    created=models.DateTimeField(auto_now_add=True)
    alert_created = models.BooleanField(default=False)
    extracted_parameters = models.TextField()

class MarketAI(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    prompt=models.TextField()
    created=models.DateTimeField(auto_now_add=True)
    position_created = models.BooleanField(default=False)
    extracted_parameters = models.TextField()
 
class AlertAITracker(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    created=models.DateTimeField(auto_now_add=True)
    count = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.user} - {self.created} - {self.count}"

class Conversation(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(to=User, on_delete=models.CASCADE, related_name='conversation')
    created = models.DateTimeField(auto_now_add=True)
    name=models.CharField(max_length=50)
    thread_id = models.CharField(max_length=50, null=True, blank=True)
    
class Message(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(to=User, on_delete=models.CASCADE, related_name='messages')
    room = auto_prefetch.ForeignKey(Conversation, on_delete=models.CASCADE,related_name='messages')
    sender=models.CharField(max_length=10, default='user')
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content

class FeedsCategory(auto_prefetch.Model):
    name=models.CharField(max_length=50)
    created=models.DateTimeField(auto_now_add=True)
    updated=models.DateTimeField(auto_now=True)

class DashboardFeed(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to="feed/", blank=True, null=True)
    image_caption = models.CharField(max_length=100, blank=True, null=True)
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, blank=True, null=True)
    subtitle = models.TextField(blank=True, null=True)
    content = models.TextField()
    created=models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(default='draft', max_length=20)
    category =  auto_prefetch.ForeignKey(FeedsCategory, on_delete=models.DO_NOTHING)
    
    
    def __str__(self):
        return self.title

class FeedReaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    feed = models.ForeignKey(DashboardFeed, on_delete=models.CASCADE, related_name='reactions')
    agree = models.BooleanField(default=False)
    disagree = models.BooleanField(default=False)
    like = models.BooleanField(default=False)
    trading = models.BooleanField(default=False)
    monitoring = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'feed')

class UserSubscribedCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscribed_categories')
    category = models.ForeignKey(FeedsCategory, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'category')

class ButtonClick(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    button_name=models.CharField(max_length=50)
    page = models.CharField(max_length=50)
    created=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} -{self.page} - {self.button_name}"
    
class StockWatchlist(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, related_name='watchlisted_by')
    created = models.DateTimeField(auto_now_add=True)

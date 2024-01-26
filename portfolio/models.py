from time import time
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

class DemoPortfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='demoportfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    equity = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def update_equity(self):
        # Calculate and update the portfolio equity based on the current value of holdings
        total_equity = sum(holding.cur_val for holding in self.demoholdings.all())
        self.equity = total_equity
        self.save()

    def __str__(self):
        return f"{self.user} - Portfolio"
    
    # def portfolio_value(self):
    #     holdings = self.demoholdings.all()
    #     if not holdings.exists():
    #         return Decimal(0)
    #     return sum(holding.cur_val for holding in holdings)
    
    def portfolio_value(self):
        holdings = self.demoholdings.all()
        if not holdings.exists():
            return Decimal(0)
        
        with ThreadPoolExecutor() as executor:
                futures = [executor.submit(get_demo_holding_details_concurrently, holding) for holding in holdings]
                holdings_data = [future.result() for future in futures]
        cur_vals = [holding['cur_val'] for holding in holdings_data]
        portfolio_value = sum(cur_vals)
        return portfolio_value

    @property
    def total_invested(self):
        holdings = self.demoholdings.all()
        if not holdings.exists():
            return Decimal(0)
        # return sum(holding.avg_cost() * holding.filled for holding in holdings )
        return sum(holding.avg_cost() * holding.filled if hasattr(holding, 'filled') and holding.filled else 0 for holding in holdings)


    @property
    def profit_loss(self):
        holdings = self.holdings.all()
        if not holdings.exists():
            return Decimal(0)
        return sum((holding.ltp - holding.avg_cost()) * holding.filled for holding in holdings)

    def get_positions(self):
        # Get a list of positions (holdings) in the portfolio
        positions = [{"stock": holding.stock.symbol, "quantity": holding.quantity} for holding in self.holdings.all()]
        return positions

    def calculate_portfolio_return(self):
        total_invested = self.total_invested
        current_portfolio_value = self.portfolio_value()

        if total_invested == Decimal(0):
            return Decimal(0)

        return ((current_portfolio_value - total_invested) / total_invested) * Decimal(100)
    
    
class Portfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='portfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    equity = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def update_equity(self):
        # Calculate and update the portfolio equity based on the current value of holdings
        total_equity = sum(holding.calculate_value() for holding in self.holdings.all())
        self.equity = total_equity
        self.save()

    def __str__(self):
        return f"{self.user} - Portfolio"
    
    
    def portfolio_value(self):
        holdings = self.holdings.all()
        if not holdings.exists():
            return Decimal(0)
        
        with ThreadPoolExecutor() as executor:
                futures = [executor.submit(get_holding_details_concurrently, holding) for holding in holdings]
                holdings_data = [future.result() for future in futures]
        cur_vals = [holding['cur_val'] for holding in holdings_data]
        portfolio_value = sum(cur_vals)
        return portfolio_value

    @property
    def total_invested(self):
        holdings = self.holdings.all()
        if not holdings.exists():
            return Decimal(0)
        return sum(holding.avg_cost() * holding.filled for holding in holdings)

    @property
    def profit_loss(self):
        holdings = self.holdings.all()
        if not holdings.exists():
            return Decimal(0)
        return sum((holding.ltp - holding.avg_cost()) * holding.filled for holding in holdings)

    def get_positions(self):
        # Get a list of positions (holdings) in the portfolio
        positions = [{"stock": holding.stock.symbol, "quantity": holding.quantity} for holding in self.holdings.all()]
        return positions

    def calculate_portfolio_return(self):
        total_invested = self.total_invested
        current_portfolio_value = self.portfolio_value()

        if total_invested == Decimal(0):
            return Decimal(0)

        return ((current_portfolio_value - total_invested) / total_invested) * Decimal(100)
    
class DemoHolding(auto_prefetch.Model):
    portfolio = auto_prefetch.ForeignKey(DemoPortfolio, on_delete=models.CASCADE, related_name='demoholdings')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.quantity}"

    # @property
    # def current_value(self):
    #     return self.quantity * self.ltp
    
    @property
    def filled(self):
        trades= self.demotrades.filter(status='completed') 
        # print(trades)
        return trades.aggregate(total_quantity=Sum('quantity'))['total_quantity'] 

    @property
    def incomplete(self):
        return self.trades.filter(status='pending').aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

    @property
    def shares(self):
        return self.filled + self.incomplete

    
    @classmethod
    def calculate_avg_cost(cls, holding_id):
        trades = DemoTrade.objects.filter(holding_id=holding_id, status='completed')
        # print(trades)
        if not trades.exists():
            return Decimal(0)

        prices = trades.values_list('price', flat=True)
        # print(prices)
        avg_price = sum(prices) / len(prices)
        # print('avg',avg_price)
        return round(Decimal(avg_price),2)

    def avg_cost(self):
        # print(self.stock.symbol)
        return self.calculate_avg_cost(self.id)
    
    
    @property
    def ltp(self):
        from .utils import get_price
        data=get_price(self.stock.symbol)
        price= data['current_price']
        return Decimal(price)

    @property
    def cur_val(self):
        return self.ltp * self.quantity

    @property
    def pnl(self):
        profit_loss = (self.ltp - self.avg_cost()) * self.filled
        return f"+{profit_loss:.2f}" if profit_loss >= 0 else f"-{abs(profit_loss):.2f}"

    @property
    def change(self):
        return round(self.ltp - self.avg_cost(),2)

    @property
    def percent_change(self):
        return round((self.change / self.ltp),2) * 100 if self.ltp != 0 else 0

    @property
    def avg_volume_3_months(self):
        return '65M'

    @property
    def volume(self):
        return '65M'



class Holding(auto_prefetch.Model):
    portfolio = auto_prefetch.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.quantity}"

    # @property
    # def current_value(self):
    #     return self.quantity * self.ltp
    
    @property
    def filled(self):
        trades= self.trades.filter(status='completed') 
        # print(trades)
        return trades.aggregate(total_quantity=Sum('quantity'))['total_quantity'] 

    @property
    def incomplete(self):
        return self.trades.filter(status='pending').aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

    @property
    def shares(self):
        return self.filled + self.incomplete

    
    @classmethod
    def calculate_avg_cost(cls, holding_id):
        trades = Trade.objects.filter(holding_id=holding_id, status='completed')
        # print(trades)
        if not trades.exists():
            return Decimal(0)

        prices = trades.values_list('price', flat=True)
        # print(prices)
        avg_price = sum(prices) / len(prices)
        # print('avg',avg_price)
        return round(Decimal(avg_price),2)

    def avg_cost(self):
        # print(self.stock.symbol)
        return self.calculate_avg_cost(self.id)
    
    
    @property
    def ltp(self):
        from .utils import get_price
        data=get_price(self.stock.symbol)
        price= data['current_price']
        return Decimal(price)

    @property
    def cur_val(self):
        return self.ltp * self.quantity

    @property
    def pnl(self):
        profit_loss = (self.ltp - self.avg_cost()) * self.filled
        return f"+{profit_loss:.2f}" if profit_loss >= 0 else f"-{abs(profit_loss):.2f}"

    @property
    def change(self):
        return round(self.ltp - self.avg_cost(),2)

    @property
    def percent_change(self):
        return round((self.change / self.ltp),2) * 100 if self.ltp != 0 else 0

    @property
    def avg_volume_3_months(self):
        return '65M'

    @property
    def volume(self):
        return '65M'


    
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
    
    
    def __str__(self):
        return f'{self.user}-{self.amount}'
    
class WithdrawalRequest(auto_prefetch.Model):
    wallet=auto_prefetch.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    status= models.CharField(max_length=20, default='Unprocessed', blank=True,null=True)
    
class Transaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=50, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'),('buy', 'Buy'), ('sell', 'Sell')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status= models.CharField(max_length=20, default='unprocessed', blank=True,null=True)


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
    
class Trade(models.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    holding = auto_prefetch.ForeignKey(Holding, on_delete=models.CASCADE, related_name='trades')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    # is_buy = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='pending')
    order_type = models.CharField(max_length=20, default='buy')
    
    def __str__(self):
        return f'{self.holding.stock.symbol} - {self.order_type} - {self.quantity}units at {self.price} - {self.status}'
    
    @property
    def amount(self):
        return self.quantity * self.price
    
    @property
    def symbol(self):
        return self.holding.stock.symbol

    # def save(self, *args, **kwargs):        
    #     activity=UserLoginActivity.objects.create(user=self.user, action_type=self.order_type,description=f"User {self.order_type}'s {self.holding.stock}.")
    #     super().save(*args, **kwargs)

class DemoTrade(models.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    holding = auto_prefetch.ForeignKey(DemoHolding, on_delete=models.CASCADE, related_name='demotrades')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    # is_buy = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='pending')
    order_type = models.CharField(max_length=20, default='buy')
    
    def __str__(self):
        return f'{self.holding.stock.symbol} - {self.order_type} - {self.quantity}units at {self.price} - {self.status}'
    
    @property
    def amount(self):
        return self.quantity * self.price
    

class Alert(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    stock= auto_prefetch.ForeignKey(Stock,on_delete=models.CASCADE)
    alert_name=models.CharField(max_length=50)
    description=models.TextField(default="")
    alert_type=models.CharField(max_length=30, choices=(("price", "price"), ("volume", "volume")), default='price')
    action=models.CharField(max_length=50, choices=(("above", "above"), ("below", "below")))
    to_price=models.FloatField(blank=True, null=True)
    to_volume=models.FloatField(blank=True, null=True)    
    frequency=models.CharField(max_length=50, choices=(("Once","Once"),("Everytime", "Everytime")), default='Once')
    expire = models.DateTimeField(default=timezone.now() + timedelta(weeks=2))
    created=models.DateTimeField(auto_now_add=True)
    trigerred = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        
        last_day_of_month = timezone.now().replace(day=1, month=(timezone.now().month % 12) + 1, hour=22, minute=59, second=59) - timedelta(days=1)
        self.expire = last_day_of_month
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.stock.symbol} alert"
    
class AlertAI(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    prompt=models.TextField()
    created=models.DateTimeField(auto_now_add=True)
    alert_created = models.BooleanField(default=False)
    extracted_parameters = models.TextField()
    
class AlertAITracker(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    created=models.DateTimeField(auto_now_add=True)
    count = models.IntegerField(default=0)

class Conversation(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(to=User, on_delete=models.CASCADE, related_name='conversation')
    created = models.DateTimeField(auto_now_add=True)
    name=models.CharField(max_length=10)
    
class Message(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(to=User, on_delete=models.CASCADE, related_name='messages')
    room = auto_prefetch.ForeignKey(Conversation, on_delete=models.CASCADE,related_name='messages')
    sender=models.CharField(max_length=5, default='user')
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content
    
class Position(auto_prefetch.Model):
    OPEN = 'open'
    CLOSED = 'closed'
    
    STATE_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
    ]
    
    portfolio = auto_prefetch.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='positions')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    average_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    
    def close_position(self):
        self.state = self.CLOSED
        self.save()

    def update_position(self, trade):
        # Update the position based on the executed trade
        if trade.order_type == 'buy':
            total_value = (self.quantity * self.average_price) + (trade.quantity * trade.price)
            total_quantity = self.quantity + trade.quantity
            self.average_price = total_value / total_quantity
            self.quantity = total_quantity
        elif trade.order_type == 'sell':
            self.quantity -= trade.quantity

        self.save()
        
    def calculate_profit_loss(self):
        # Calculate profit or loss based on the current price
        total_value = self.quantity * self.current_price
        total_cost = self.quantity * self.average_price
        self.profit_loss = total_value - total_cost
        return self.profit_loss
    
class DemoPosition(auto_prefetch.Model):
    OPEN = 'open'
    CLOSED = 'closed'
    
    STATE_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
    ]
    portfolio = auto_prefetch.ForeignKey(DemoPortfolio, on_delete=models.CASCADE, related_name='demopositions')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    average_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    
    def close_position(self):
        self.state = self.CLOSED
        self.save()
        
    def calculate_profit_loss(self):
        # Calculate profit or loss based on the current price
        total_value = self.quantity * get_price(self.stock.symbol)['current_price']
        total_cost = self.quantity * self.average_price
        self.profit_loss = total_value - total_cost
        return self.profit_loss

    def update_position(self, trade):
        # Update the position based on the executed trade
        if trade.order_type == 'buy':
            total_value = (self.quantity * self.average_price) + (trade.quantity * trade.price)
            total_quantity = self.quantity + trade.quantity
            self.average_price = total_value / total_quantity
            self.quantity = total_quantity
        elif trade.order_type == 'sell':
            self.quantity -= trade.quantity

        self.save()

    @property
    def current_price(self):
        return get_price(self.stock.symbol)['current_price']

# class UserTradeActivityLog(models.Model):
#     user=models.ForeignKey(User, related_name='trade_user', on_delete=models.CASCADE)
#     trade=models.ForeignKey(Trade, related_name='trade', on_delete=models.CASCADE)
#     action_type=models.CharField(max_length=20)
#     timestamp = models.DateTimeField(auto_now_add=True)
#     description=models.CharField(max_length=100)

#     def __str__(self) -> str:
#         return self.user

    


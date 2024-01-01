from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Avg, F
import auto_prefetch
from random import uniform
from decimal import Decimal

User= get_user_model()

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
        random_factor = Decimal(uniform(4, 50))
        return round(random_factor,2)
    
    @property
    def current_price(self):
        random_factor = Decimal(uniform(0.8, 1.2))
        return round(self.ltp * random_factor,2)


    @property
    def change(self):
        return round(self.ltp - self.current_price,2)

    @property
    def percent_change(self):
        return round((self.change / self.ltp),2) * 100 if self.ltp != 0 else 0

class Portfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='portfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    

    def __str__(self):
        return f"{self.user} - Portfolio"
    
    
    def portfolio_value(self):
        holdings = self.holdings.all()
        if not holdings.exists():
            return Decimal(0)
        return sum(holding.cur_val for holding in holdings)

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
        return price

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
    
    
class PayStackReceipts(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    reference=models.CharField(max_length=255, blank=True, null=True)
    transaction=models.CharField(max_length=255, blank=True, null=True)
    amount = models.IntegerField(blank=True,null=True)
    date = models.DateTimeField(auto_now_add=True)
    receipt_status = models.CharField(max_length=20,default='Unprocessed'  )
    comment = models.TextField(blank=True, null=True)
    
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

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.amount}"


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
    

class Alert(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    stock= auto_prefetch.ForeignKey(Stock,on_delete=models.CASCADE)
    alert_name=models.CharField(max_length=50)
    description=models.TextField(default="")
    price_action=models.CharField(max_length=50, choices=(("above", "above"), ("below", "below")))
    from_price=models.FloatField()
    to_price=models.FloatField()
    from_volume=models.FloatField()
    to_volume=models.FloatField()    
    schedules=models.CharField(max_length=50, choices=(("Daily","Daily"),("Weekly", "Weekly"), ("MOnthly", "Monthly")))
    created_at=models.DateTimeField(auto_now_add=True)
    communication_channel=models.CharField(max_length=50, choices=(("email", "email"), ("notification", "notification")))


    def __str__(self) -> str:
        return f"{self.stock.symbol} alert"
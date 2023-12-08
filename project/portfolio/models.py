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
    

class Portfolio(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='portfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    

    def __str__(self):
        return f"{self.user} - Portfolio"
    
    # def calculate_equity(self):
    #     # Calculate the total equity based on the current value of all holdings
    #     total_equity = sum(holding.calculate_value() for holding in self.holdings.all())
    #     return total_equity

    # def calculate_current_value(self):
    #     # Calculate the total current value of all holdings
    #     total_value = sum(holding.current_value for holding in self.holdings.all())
    #     return total_value
    
    def portfolio_value(self):
        return sum(holding.cur_val for holding in self.holdings.all())

    @property
    def total_invested(self):
        return sum(holding.avg_cost * holding.filled for holding in self.holdings.all())

    @property
    def profit_loss(self):
        return sum((holding.ltp - holding.avg_cost) * holding.filled for holding in self.holdings.all())

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

    @property
    def current_value(self):
        return self.quantity * self.ltp
    
    @property
    def filled(self):
        return self.trades.filter(status='completed').aggregate(total_quantity=Sum('quantity'))['total_quantity'] 

    @property
    def incomplete(self):
        return self.trades.filter(status='pending').aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0

    @property
    def shares(self):
        return self.filled + self.incomplete

    
    @property
    def avg_cost(self):
        prices = self.trades.filter(status='completed').values_list('price', flat=True)
        print(prices)
        avg_price = sum(prices) / len(prices)
        print(avg_price)
        
        return Decimal(avg_price)
    
    
    @property
    def ltp(self):
        random_factor = Decimal(uniform(0.8, 1.2))
        return self.avg_cost * random_factor

    @property
    def cur_val(self):
        return self.ltp * self.quantity

    @property
    def pnl(self):
        profit_loss = (self.ltp - self.avg_cost) * self.filled
        return f"+{profit_loss:.2f}" if profit_loss >= 0 else f"-{abs(profit_loss):.2f}"

    @property
    def change(self):
        return self.stock.price_change

    @property
    def percent_change(self):
        return (self.change / self.ltp) * 100 if self.ltp != 0 else 0

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
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'),('buy', 'Buy'), ('sell', 'Sell')])
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
    # is_buy = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='pending')
    order_type = models.CharField(max_length=20, default='buy')
    
    def __str__(self):
        return f'{self.holding.stock.symbol} - {self.order_type} - {self.quantity}units at {self.price} - {self.status}'
    
    @property
    def amount(self):
        return self.quantity * self.price
    
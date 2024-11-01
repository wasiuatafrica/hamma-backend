from django.db import models
from django.contrib.auth import get_user_model
import auto_prefetch
from portfolio.models import Stock
import random
import string
from portfolio.utils import db_merged
from decimal import Decimal

User = get_user_model()


def generate_account_id():
    return "".join(random.choices(string.digits, k=6))


def get_price(symbol):
    collection = db_merged["merged_live_price"]
    last_item = collection.find_one(sort=[("_id", -1)])
    # print(symbol)
    return last_item[symbol]


class PropTradingAccount(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="prop_accounts"
    )
    model_type = models.CharField(
        max_length=10, choices=[("model_1", "Model 1"), ("model_2", "Model 2")]
    )
    initial_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=10000000
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=10000000)
    profit_target = models.DecimalField(max_digits=15, decimal_places=2)
    account_drawdown_limit = models.DecimalField(max_digits=15, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    account_name = models.CharField(max_length=20, null=True, blank=True)
    account_id = models.CharField(max_length=20, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.account_id:
            self.generate_unique_account_id()
        super().save(*args, **kwargs)

    def generate_unique_account_id(self):
        max_attempts = 5
        for _ in range(max_attempts):
            generated_id = "".join(random.choices(string.digits, k=6))
            if not PropTradingAccount.objects.filter(account_id=generated_id).exists():
                self.account_id = generated_id
                return
        raise ValueError(
            "Failed to generate a unique account ID after multiple attempts."
        )


class PropPosition(auto_prefetch.Model):
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    STATE_CHOICES = [
        (OPEN, "Open"),
        (CLOSED, "Closed"),
        (PENDING, "Pending"),
        (CANCELLED, "Cancelled"),
    ]

    portfolio = auto_prefetch.ForeignKey(
        PropTradingAccount, on_delete=models.CASCADE, related_name="prop_positions"
    )
    stock = auto_prefetch.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="prop_positions"
    )
    quantity = models.PositiveIntegerField(default=0)
    open_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    close_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    limit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    amount_invested = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    action = models.CharField(max_length=20, default="buy")
    alert_name = models.CharField(max_length=20, blank=True, null=True)
    time_in_force = models.CharField(max_length=20, default="day")
    order_type = models.CharField(max_length=20, default="market")
    profit_loss = models.IntegerField(default=0)
    take_profit = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    stop_loss = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    trailing_stop_loss = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    last_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.action}"

    def calculate_profit_loss(self):
        price = self.current_price
        current_value = self.quantity * price
        # print(self.status)
        if self.status == "open":
            if self.action == "buy":
                profit_loss = Decimal(current_value) - self.amount_invested
            elif self.action == "sell":
                profit_loss = self.amount_invested - Decimal(current_value)
        elif self.status == "close":
            profit_loss = self.profit_loss
            current_value = self.quantity * self.close_price
        else:
            current_value = 0
            profit_loss = 0
        # print(profit_loss)
        return profit_loss, current_value, price

    @property
    def current_price(self):
        return get_price(self.stock.symbol)["current_price"]


class PropTradingTransaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="prop_transactions"
    )
    account = auto_prefetch.ForeignKey(
        PropTradingAccount, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(
        max_length=10, choices=[("deposit", "Deposit"), ("payout", "Payout")]
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)
    description = models.TextField(null=True, blank=True)


class TradingMetrics(auto_prefetch.Model):
    account = models.OneToOneField(
        PropTradingAccount, on_delete=models.CASCADE, related_name="metrics"
    )
    total_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    max_drawdown = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    daily_drawdown = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    last_active = models.DateTimeField(null=True, blank=True)
    minimum_trading_days_met = models.BooleanField(default=False)

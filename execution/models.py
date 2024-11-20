from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
import auto_prefetch
from decimal import Decimal
from datetime import datetime, timedelta
import portfolio
from portfolio.models import Receipts, Stock
from accounts.models import Profile
from competition.models import CompetitionPortfolio
import random
import string
from portfolio.utils import db_merged

User = get_user_model()


def generate_account_id():
    return "".join(random.choices(string.digits, k=6))


def get_price(symbol):
    collection = db_merged["merged_live_price"]
    last_item = collection.find_one(sort=[("_id", -1)])
    # print(symbol)
    return last_item[symbol]


class DiscountCode(auto_prefetch.Model):
    TYPE_CHOICES = (
        ("prop", "Prop"),
        ("main", "Main"),
        ("general", "General"),
        ("account-size", "Account Size"),
        ("personal", "Personal"),
    )

    MODEL_CHOICES = (("model_1", "Model 1"), ("model_2", "Model 2"))

    code = models.CharField(max_length=25, unique=True)
    discount_percentage = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    num_of_accounts = models.IntegerField(null=True, blank=True)
    user = auto_prefetch.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="discount_codes",
    )
    use_limit = models.PositiveIntegerField(
        null=True, blank=True
    )  # Number of times code can be used
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="prop")
    acc_size = models.CharField(max_length=30, blank=True, null=True)
    domain = models.CharField(max_length=30, blank=True, null=True, default="hamma")
    acc_model = models.CharField(
        max_length=30, blank=True, null=True, choices=MODEL_CHOICES
    )

    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.created <= now <= self.expiry_date

    def __str__(self):
        return f"{self.user.email if self.user else None} - {self.code}"

    def total_used(self):
        if self.is_active:
            if timezone.now() > self.expiry_date:

                self.is_active = False
                self.save()
        return DemoPortfolio.objects.filter(discount_code=self).count()


class DemoPortfolio(auto_prefetch.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="demoportfolio2"
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=1000000.0)
    account_name = models.CharField(max_length=20, default="Demo Account 1")
    account_id = models.CharField(max_length=20, null=True, blank=True)
    initial_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=1000000
    )
    is_prop = models.BooleanField(default=False)
    profit_target = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    account_drawdown_limit = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )
    is_active = models.BooleanField(default=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    blown = models.BooleanField(default=False)
    inactive_by_inactivity = models.BooleanField(default=False)
    activated = models.BooleanField(default=False)
    receipt_approved = models.BooleanField(default=False)
    broker = models.CharField(max_length=255, blank=True, default="Hamma")
    model_type = models.CharField(max_length=255, default="model_1")
    payout = models.CharField(max_length=255, default="weekly")
    time_to_payout = models.IntegerField(blank=True, null=True)
    target_met = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    balance_based_drawdown = models.BooleanField(default=False)
    last_swap_charge_date = models.DateField(null=True, blank=True)
    passed_date = models.DateTimeField(blank=True, null=True)
    discount_code = auto_prefetch.ForeignKey(
        DiscountCode, on_delete=models.SET_NULL, null=True, blank=True
    )
    account_type_level = models.CharField(max_length=25, default="challenge")

    def save(self, *args, **kwargs):
        if not self.account_id:
            self.generate_unique_account_id()
        super().save(*args, **kwargs)

    def generate_unique_account_id(self):
        max_attempts = 10
        for _ in range(max_attempts):
            if self.is_prop:
                generated_id = "".join(random.choices(string.digits, k=8))
            else:
                generated_id = "".join(random.choices(string.digits, k=6))
            if not DemoPortfolio.objects.filter(account_id=generated_id).exists():
                self.account_id = generated_id
                return
        raise ValueError(
            "Failed to generate a unique account ID after multiple attempts."
        )

    def __str__(self):
        return (
            f"{self.user} - {self.account_name} - {self.account_id}"
            if self.account_id
            else f"{self.user} - {self.account_name}"
        )

    @property
    def account_type(self):
        # if self.is_prop:
        #     return "prop_account"
        return "demo_portfolio"


class HammaAccountRequest(auto_prefetch.Model):
    choices = (
        ("Eligible", "Eligible"),
        ("Ineligible", "Ineligible"),
    )
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    account = models.CharField(max_length=255, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=255, choices=choices, default="Unprocessed", blank=True, null=True
    )
    comment = models.CharField(max_length=255, blank=True, default="", null=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} | {self.account}"


class Portfolio(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="portfolio2"
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    account_name = models.CharField(max_length=20, default="Live Account 1")
    account_id = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.account_id:
            self.generate_unique_account_id()
        super().save(*args, **kwargs)

    def generate_unique_account_id(self):
        max_attempts = 5
        for _ in range(max_attempts):
            generated_id = "".join(random.choices(string.digits, k=6))
            if not Portfolio.objects.filter(account_id=generated_id).exists():
                self.account_id = generated_id
                return
        raise ValueError(
            "Failed to generate a unique account ID after multiple attempts."
        )

    def __str__(self):
        return f"{self.user}"

    @property
    def account_type(self):
        return "live_portfolio"

    class Meta(auto_prefetch.Model.Meta):
        unique_together = ("user", "account_name")


class Position(auto_prefetch.Model):
    OPEN = "open"
    CLOSED = "close"
    PENDING = "pending"
    CANCELLED = "cancelled"

    STATE_CHOICES = [
        (OPEN, "Open"),
        (CLOSED, "Closed"),
        (PENDING, "Pending"),
        (CANCELLED, "Cancel"),
    ]
    portfolio = auto_prefetch.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="positions2"
    )
    stock = auto_prefetch.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="positions2"
    )
    quantity = models.PositiveIntegerField(default=0)
    open_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    close_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    limit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
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


class DemoPosition(auto_prefetch.Model):
    OPEN = "open"
    CLOSED = "close"
    PENDING = "pending"
    CANCELLED = "cancelled"

    STATE_CHOICES = [
        (OPEN, "Open"),
        (CLOSED, "Closed"),
        (PENDING, "Pending"),
        (CANCELLED, "Cancel"),
    ]
    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, related_name="demopositions2"
    )
    stock = auto_prefetch.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="demopositions2"
    )
    quantity = models.PositiveIntegerField(default=0)
    open_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    close_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    limit_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    action = models.CharField(max_length=20, default="buy")
    alert_name = models.CharField(max_length=50, blank=True, null=True)
    time_in_force = models.CharField(max_length=20, default="day")
    order_type = models.CharField(max_length=20, default="market")
    order_id = models.CharField(max_length=40, blank=True, null=True)
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
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.action} - {self.status}| {self.updated}"

    def calculate_profit_loss(self):
        price = self.current_price
        current_value = round(self.quantity * price, 2)
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
        print(self.stock.symbol)
        price = get_price(self.stock.symbol)
        if price is None:
            return 0
        return price["current_price"]


class DemoTrade(models.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="demotrades2"
    )
    position = auto_prefetch.ForeignKey(
        DemoPosition, on_delete=models.CASCADE, related_name="demotrades2"
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, default="pending")
    order_type = models.CharField(max_length=20, default="buy")

    def __str__(self):
        return f"{self.position.stock.symbol} - {self.order_type} - {self.quantity}units at {self.price} - {self.status}"

    @property
    def amount(self):
        return self.quantity * self.price


# class MasterWallet(auto_prefetch.Model):
#     commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
#     created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     trade = auto_prefetch.ForeignKey(Trade, on_delete=models.CASCADE,related_name='master_wallet', null=True, blank=True)


class DemoProfitLoss(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="demoprofitloss"
    )
    profit_loss = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)


class DemoDailyReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="demoreturns"
    )
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} {self.portfolio_returns} - {self.created.date()}"


class DemoDailyReturns2(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="returns2"
    )
    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )
    first_entry = models.BooleanField(default=True)
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return (
            f"{self.user}-{self.portfolio.account_name}-{self.portfolio_returns}"
            if self.portfolio and self.portfolio.account_name
            else self.user
        )


class DailyReturns2(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="demoreturns2"
    )
    portfolio = auto_prefetch.ForeignKey(
        Portfolio, on_delete=models.CASCADE, blank=True, null=True
    )
    first_entry = models.BooleanField(default=True)
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.portfolio:
            return f"{self.portfolio.id} {self.user} {self.portfolio_returns} - {self.created.date()}"
        else:
            return f"{self.user} {self.portfolio_returns} - {self.created.date()}"


class MarketReturns(auto_prefetch.Model):
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)
    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"{self.market_returns} - {self.created.date()}"


class CompetitionMarketReturns(auto_prefetch.Model):
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)
    portfolio = auto_prefetch.ForeignKey(
        CompetitionPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"{self.market_returns} - {self.created.date()}"


class CumulativeMarketReturns(auto_prefetch.Model):
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)
    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )


class CompetitionCumulativeMarketReturns(auto_prefetch.Model):
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)
    portfolio = auto_prefetch.ForeignKey(
        CompetitionPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"{self.market_returns} - {self.created.date()}"


class DemoCumulativeReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="democumureturns"
    )
    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )
    first_entry = models.BooleanField(default=True)
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.created:
            return f"{self.user} {self.portfolio_returns} - {self.created.date()}"
        else:
            return f"{self.user} {self.portfolio_returns}"


class DailyReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="returns"
    )
    portfolio_returns = models.FloatField(default=0)
    market_returns = models.FloatField(default=0)
    ngx_price = models.FloatField(default=0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.created}"


class CumulativeReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="cumureturns"
    )
    portfolio = auto_prefetch.ForeignKey(
        Portfolio, on_delete=models.CASCADE, blank=True, null=True
    )
    first_entry = models.BooleanField(default=True)
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    created = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.created}"


class WithdrawalRequest(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True
    )
    amount = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20, default="Unprocessed", blank=True, null=True
    )
    flag = models.BooleanField(default=False, null=True, blank=True)

    @property
    def bank_name(self):
        user = self.wallet.user
        profile = Profile.objects.get(user__email=user.email)
        # print(profile, "jbabah")
        return profile.bank_name

    @property
    def account_number(self):
        user = self.wallet.user
        profile = Profile.objects.get(user__email=user.email)
        # print(profile, "jbabah")
        return profile.account_number


class DemoAdminTransaction(auto_prefetch.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True)
    position = auto_prefetch.ForeignKey(
        DemoPosition, on_delete=models.CASCADE, related_name="demo_admin_transaction"
    )


class AdminTransaction(auto_prefetch.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True)
    position = auto_prefetch.ForeignKey(
        Position, on_delete=models.CASCADE, related_name="admin_transaction"
    )


class DemoAdminWallet(auto_prefetch.Model):
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True)


class AdminWallet(auto_prefetch.Model):
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True)


class PropReceipt(auto_prefetch.Model):
    account = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, blank=True, null=True
    )
    receipt = auto_prefetch.ForeignKey(
        Receipts, on_delete=models.CASCADE, blank=True, null=True
    )

    discount_code = auto_prefetch.ForeignKey(
        DiscountCode, on_delete=models.CASCADE, blank=True, null=True
    )

    def __str__(self):
        return f"{self.account} - {self.receipt}"

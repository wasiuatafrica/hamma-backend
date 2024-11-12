from datetime import datetime, timedelta
from decimal import Decimal

import auto_prefetch
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import close_old_connections, models
from django.db.models import Avg, F, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def get_holding_detail(holding, trades):
    from .utils import get_price

    stock = holding.stock.symbol
    data = get_price(stock)
    id = holding.id
    quantity = holding.quantity
    created = holding.created
    updated = holding.updated
    filled = (
        trades.filter(status="completed").aggregate(total_quantity=Sum("quantity"))[
            "total_quantity"
        ]
        if trades
        else 0
    )
    incomplete_ = trades.filter(status="pending")

    if not filled:
        filled = 0

    if incomplete_:
        incomplete1 = incomplete_.aggregate(total_quantity=Sum("quantity"))[
            "total_quantity"
        ]
        if incomplete1:
            incomplete = incomplete1
        else:
            incomplete = 0
    else:
        incomplete = 0

    shares = filled + incomplete
    avg_cost = holding.avg_cost()
    ltp = Decimal(data["current_price"])
    cur_val = round((ltp * quantity), 2)
    pnl = round((ltp - avg_cost) * filled, 2) if avg_cost else 0
    change = round(ltp - avg_cost, 2) if avg_cost else 0
    percent_change = round((change / avg_cost) * 100, 2) if avg_cost else 0
    avg_volume_3_months = 60000
    volume = 9000000
    return {
        "id": id,
        "stock": stock,
        "quantity": quantity,
        "created": created,
        "updated": updated,
        "filled": filled,
        "incomplete": incomplete,
        "shares": shares,
        "avg_cost": avg_cost,
        "ltp": ltp,
        "cur_val": cur_val,
        "pnl": pnl,
        "change": change,
        "percent_change": percent_change,
        "avg_volume_3_months": avg_volume_3_months,
        "volume": volume,
    }


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


TRADING_STATUS_CHOICES = [("Listed", "Listed"), ("Delisted", "Delisted")]


class Wallet(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.balance}"


class BonusWallet(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.balance}"


class Stock(auto_prefetch.Model):

    company = models.CharField(max_length=200, default="")
    symbol = models.CharField(max_length=20)
    sector = models.CharField(max_length=50, null=True, blank=True)
    listing_date = models.DateField(_("Listing Date"), null=True, blank=True)
    incorporation_date = models.DateField(
        _("Incorporation Date"), null=True, blank=True
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    active = models.BooleanField(default=True)
    logo_url = models.TextField(blank=True, null=True)
    email_logo_url = models.TextField(blank=True, null=True)
    converted_png = models.BooleanField(default=False)
    reversed_to_svg = models.BooleanField(default=False)

    def __str__(self):
        return self.symbol

    @property
    def ltp(self):
        from .utils import get_price

        data = get_price(self.symbol)
        price = data["current_price"]
        return price

    @property
    def current_price(self):
        from .utils import get_price

        data = get_price(self.symbol)
        price = data["current_price"]
        return price

    @property
    def change(self):
        return round(self.ltp - self.current_price, 2)

    @property
    def percent_change(self):
        return round((self.change / self.ltp), 2) * 100 if self.ltp != 0 else 0


class CompanyFundamental(models.Model):
    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="fundamentals"
    )
    date = models.DateField()

    # Financial Statement Data
    revenue = models.DecimalField(max_digits=20, decimal_places=2)
    net_income = models.DecimalField(max_digits=20, decimal_places=2)
    total_assets = models.DecimalField(max_digits=20, decimal_places=2)
    total_liabilities = models.DecimalField(max_digits=20, decimal_places=2)
    total_equity = models.DecimalField(max_digits=20, decimal_places=2)
    operating_cash_flow = models.DecimalField(max_digits=20, decimal_places=2)

    # Financial Ratios
    pe_ratio = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    pb_ratio = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    debt_to_equity = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    roe = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )
    roa = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )

    # Dividend Information
    dividend_yield = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    payout_ratio = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Growth Metrics
    revenue_growth = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    earnings_growth = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    # Profitability Measures
    gross_margin = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    operating_margin = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )
    net_profit_margin = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )

    # Valuation Metrics
    market_cap = models.DecimalField(max_digits=20, decimal_places=2)
    enterprise_value = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )

    # Efficiency Ratios
    inventory_turnover = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    receivables_turnover = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    # Liquidity Ratios
    current_ratio = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    quick_ratio = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # Additional Fields
    shares_outstanding = models.BigIntegerField()
    employees = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("stock", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.company.name} Fundamentals - {self.date}"


class Receipts(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="Reciepts/", max_length=355, blank=True)
    amount = models.IntegerField(blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    receipt_status = models.CharField(max_length=20, default="Unprocessed")
    comment = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    approved_date = models.DateTimeField(auto_now=True)
    payment_method = models.CharField(max_length=20, default="Bank Transfer")
    flag = models.BooleanField(default=False, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user}-{self.amount} - {self.receipt_status}"


class PayStackReceipts(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    reference = models.CharField(max_length=255, blank=True, null=True)
    transaction = models.CharField(max_length=255, blank=True, null=True)
    amount = models.IntegerField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)
    receipt_status = models.CharField(max_length=20, default="unprocessed")
    comment = models.TextField(blank=True, null=True)
    flag = models.BooleanField(default=False, null=True, blank=True)

    def __str__(self):
        return f"{self.user}-{self.amount}"


class Transaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(
        max_length=50,
        choices=[
            ("deposit", "Deposit"),
            ("withdrawal", "Withdrawal"),
            ("buy", "Buy"),
            ("sell", "Sell"),
        ],
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, default="unprocessed", blank=True, null=True
    )
    channel = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.amount}"


class DemoTransaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="demotransactions"
    )
    transaction_type = models.CharField(
        max_length=50,
        choices=[
            ("deposit", "Deposit"),
            ("withdrawal", "Withdrawal"),
            ("buy", "Buy"),
            ("sell", "Sell"),
        ],
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, default="unprocessed", blank=True, null=True
    )


class WithdrawalOTPRequest(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    expiration_time = models.DateTimeField(null=True, blank=True)
    otp = models.IntegerField(blank=True, null=True)
    used = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)


class Alert(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE)
    alert_name = models.CharField(max_length=50)
    task_name = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(default="")
    alert_type = models.CharField(
        max_length=30,
        choices=(("price", "price"), ("volume", "volume")),
        default="price",
    )
    action = models.CharField(
        max_length=50, choices=(("above", "above"), ("below", "below"))
    )
    to_price = models.FloatField(blank=True, null=True)
    to_volume = models.FloatField(blank=True, null=True)
    frequency = models.CharField(
        max_length=50,
        choices=(("Once", "Once"), ("Everytime", "Everytime")),
        default="Once",
    )
    expire = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    trigerred = models.BooleanField(default=False)
    last_email_sent = models.DateTimeField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expire:
            last_day_of_month = timezone.now().replace(
                day=1,
                month=(timezone.now().month % 12) + 1,
                hour=22,
                minute=59,
                second=59,
            ) - timedelta(days=1)
            self.expire = last_day_of_month
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.email}|{self.id} {self.created} {self.stock.symbol} alert"


class AlertAI(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    prompt = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    alert_created = models.BooleanField(default=False)
    extracted_parameters = models.TextField()


class MarketAI(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    prompt = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    position_created = models.BooleanField(default=False)
    extracted_parameters = models.TextField()


class AlertAITracker(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    count = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.user} - {self.created} - {self.count}"


class Conversation(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        to=User, on_delete=models.CASCADE, related_name="conversation"
    )
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=50)
    thread_id = models.CharField(max_length=50, null=True, blank=True)


class Message(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        to=User, on_delete=models.CASCADE, related_name="messages"
    )
    room = auto_prefetch.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.CharField(max_length=10, default="user")
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content


class FeedsCategory(auto_prefetch.Model):
    name = models.CharField(max_length=50)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DashboardFeed(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to="feed/", blank=True, null=True)
    image_caption = models.CharField(max_length=100, blank=True, null=True)
    stock = auto_prefetch.ForeignKey(
        Stock, on_delete=models.CASCADE, blank=True, null=True, related_name="feed"
    )
    subtitle = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    bullet_1 = models.TextField(blank=True, null=True)
    bullet_2 = models.TextField(blank=True, null=True)
    bullet_3 = models.TextField(blank=True, null=True)
    bullet_4 = models.TextField(blank=True, null=True)
    bullet_5 = models.TextField(blank=True, null=True)
    bullet_6 = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(default="draft", max_length=20)
    category = auto_prefetch.ForeignKey(FeedsCategory, on_delete=models.DO_NOTHING)
    published_date = models.DateTimeField(blank=True, null=True)
    sent = models.IntegerField(default=0)
    opened = models.IntegerField(default=0)
    clicked = models.IntegerField(default=0)
    bounced = models.IntegerField(default=0)
    unsubscribed = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.title} - {self.status}"

    @property
    def unique_email_open_count(self):
        return OpenedDashboardFeed.objects.filter(feed=self).count()


class OpenedDashboardFeed(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="opened_by"
    )
    feed = models.ForeignKey(
        DashboardFeed, on_delete=models.CASCADE, related_name="opened_feeds"
    )
    created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.email}-{self.feed.title} -{self.created}"


class FeedReaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    feed = models.ForeignKey(
        DashboardFeed, on_delete=models.CASCADE, related_name="reactions"
    )
    agree = models.BooleanField(default=False)
    disagree = models.BooleanField(default=False)
    like = models.BooleanField(default=False)
    trading = models.BooleanField(default=False)
    monitoring = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "feed")


class UserSubscribedCategory(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscribed_categories"
    )
    category = models.ForeignKey(FeedsCategory, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "category")


class ButtonClick(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    button_name = models.CharField(max_length=50)
    page = models.CharField(max_length=50)
    created = models.DateTimeField(auto_now_add=True)
    device_type = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.user} -{self.page} - {self.button_name}"


class StockWatchlist(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    stock = auto_prefetch.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="watchlisted_by"
    )
    created = models.DateTimeField(auto_now_add=True)


class ViewOtherIdeasLog(auto_prefetch.Model):
    email = models.EmailField()
    idea = auto_prefetch.ForeignKey(
        DashboardFeed, on_delete=models.CASCADE, blank=True, null=True
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.created}"

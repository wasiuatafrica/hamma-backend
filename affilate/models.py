from email.policy import default
from django.db import models
from django.contrib.auth import get_user_model
import auto_prefetch
from datetime import datetime, timedelta
from execution.models import Position
from accounts.models import Profile

# Create your models here.

User = get_user_model()


def get_quarter_dates():
    today = datetime.now()
    quarter_start_month = (today.month - 1) // 3 * 3 + 1
    first_day_of_quarter = datetime(today.year, quarter_start_month, 1)

    last_day_of_quarter = first_day_of_quarter + timedelta(days=89)
    year, month = last_day_of_quarter.year, last_day_of_quarter.month

    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            last_day = 29
        else:
            last_day = 28
    elif month in (4, 6, 9, 11):
        last_day = 30
    else:
        last_day = 31

    last_day_of_quarter_end = datetime(year, month, last_day, 23, 59, 59)

    return (first_day_of_quarter, last_day_of_quarter_end)


def get_quarter(date_str):
    try:
        date_object = date_str
        # date_object = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        quarter = (date_object.month - 1) // 3 + 1

        return quarter
    except ValueError:
        return "Invalid date format"


class RewardActivities(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reward_activities",
        null=True,
        blank=True,
    )
    trader = auto_prefetch.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="person_refeered",
        null=True,
        blank=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    reward_type = models.CharField(max_length=50)
    amount = models.FloatField()
    status = models.CharField(
        max_length=50, default="unprocessed", null=True, blank=True
    )
    comment = models.CharField(max_length=50, null=True, blank=True)
    flag = models.BooleanField(default=False, null=True, blank=True)

    def __str__(self):
        return f"{self.trader.firstname} | {self.reward_type}"

    @property
    def username(self):
        return f"{self.trader.firstname} {self.trader.lastname}"


class Rankings(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ranking_user",
        null=True,
        blank=True,
    )
    min_brokage_commission = models.FloatField()
    referal_count = models.IntegerField()


class ReferralWallet(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referral_wallet",
        null=True,
        blank=True,
    )
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)


class BrokageCommission(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True
    )
    person_refferred = auto_prefetch.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="brokage_commsissions",
        null=True,
        blank=True,
    )
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    trade = auto_prefetch.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="brokage_commsissions",
        null=True,
        blank=True,
    )


class CampaignQuarter(auto_prefetch.Model):
    start_date = models.DateTimeField(blank=True)
    end_date = models.DateTimeField(blank=True)
    quarter = models.IntegerField()
    year = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=200,
        default="ongoing",
        choices=(("ongoing", "ongoing"), ("closed", "closed")),
        blank=True,
    )
    first_prize = models.CharField(max_length=200, null=True, blank=True)
    second_prize = models.CharField(max_length=200, null=True, blank=True)
    third_prize = models.CharField(max_length=200, null=True, blank=True)
    message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.start_date} | {self.status}"

    def save(self, *args, **kwargs):
        if (
            not self.start_date
            or not self.end_date
            or not self.quarter
            or not self.year
        ):
            start_date, end_date = get_quarter_dates()
            self.start_date = start_date
            self.end_date = end_date
            self.quarter = get_quarter(start_date)
            self.year = start_date.year
        super().save(*args, **kwargs)


class CampaignSummary(auto_prefetch.Model):
    campaign = auto_prefetch.ForeignKey(CampaignQuarter, on_delete=models.CASCADE)
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="affiliate_campaign_summary"
    )
    earnings = models.FloatField(default=0.0)
    referrals = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    rank = models.PositiveIntegerField()
    awarded = models.BooleanField(default=False)


class ReferralWithdrawalRequest(auto_prefetch.Model):
    wallet = auto_prefetch.ForeignKey(ReferralWallet, on_delete=models.CASCADE)
    amount = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=2)
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


class ReferralWalletTransaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="referral_wallet_transactions"
    )
    transaction_type = models.CharField(
        max_length=50,
        choices=[("deposit", "Deposit"), ("withdrawal", "Withdrawal")],
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, default="unprocessed", blank=True, null=True
    )

from django.db import models
from django.utils import timezone
import auto_prefetch
from execution.models import DemoPortfolio
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords

User = get_user_model()


class Payout(auto_prefetch.Model):
    # STATUS_CHOICES = [
    #     ("pending", "Pending"),
    #     ("approved", "Approved"),
    #     ("rejected", "Rejected"),
    #     ("paid", "paid"),
    # ]

    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, related_name="payouts"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    request_date = models.DateTimeField(auto_now_add=True)
    process_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")
    profit_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )  # Stores the profit split percentage
    week_number = models.IntegerField()  # Track which trading week this payout is for
    rejected_reason = models.TextField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)
    processed_by = auto_prefetch.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="processed_payouts",
        blank=True,
    )
    history = HistoricalRecords()
    updated = models.DateTimeField(auto_now=True, null=True)

    class Meta(auto_prefetch.Model.Meta):
        ordering = ["-request_date"]

    def __str__(self):
        return f"Payout for {self.portfolio.account_id} - {self.status}"


class PropReferral(auto_prefetch.Model):
    referrer = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="prop_referrals"
    )
    referee = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="prop_referred_by"
    )
    status = models.CharField(
        max_length=20, default="registered"
    )  # 'registered' or 'trader'
    created_at = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class PropReferralWallet(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PropReferralHistory(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20)  # 'earning' or 'withdrawal'
    status = models.CharField(
        max_length=20, default="pending"
    )  # 'pending', 'approved', 'rejected'
    created_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

from django.db import models
from django.utils import timezone
import auto_prefetch
from execution.models import DemoPortfolio
from django.contrib.auth import get_user_model

User = get_user_model()


class Payout(auto_prefetch.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("processed", "Processed"),
    ]

    portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, related_name="payouts"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    request_date = models.DateTimeField(auto_now_add=True)
    process_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    profit_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )  # Stores the profit split percentage
    week_number = models.IntegerField()  # Track which trading week this payout is for
    rejected_reason = models.TextField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)
    processed_by = auto_prefetch.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="processed_payouts"
    )

    class Meta(auto_prefetch.Model.Meta):
        ordering = ["-request_date"]

    def __str__(self):
        return f"Payout for {self.portfolio.account_id} - {self.status}"

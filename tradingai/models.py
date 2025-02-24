from django.db import models
import auto_prefetch
from portfolio.models import Stock
from django.contrib.auth import get_user_model


from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()


class SubscriptionPlan(auto_prefetch.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField()
    description = models.TextField()
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(auto_prefetch.Model.Meta):
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} - ₦{self.price}"


class Subscription(auto_prefetch.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("pending", "Pending"),
    ]

    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = auto_prefetch.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    last_billing_date = models.DateTimeField(null=True)
    next_billing_date = models.DateTimeField(null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(auto_prefetch.Model.Meta):
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = timezone.now()
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return (
            self.status == "active"
            and self.start_date <= timezone.now() <= self.end_date
        )


class Trial(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="ai_trial")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    first_reminder_sent = models.BooleanField(default=False)
    halfway_reminder_sent = models.BooleanField(default=False)
    final_reminder_sent = models.BooleanField(default=False)
    trial_ended_notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=14)  # 14-day trial
        super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        if not self.is_active:
            return 0
        now = timezone.now()
        if now > self.end_date:
            return 0
        return (self.end_date - now).days

    @property
    def has_expired(self):
        return timezone.now() > self.end_date


class SubscriptionNotification(auto_prefetch.Model):
    NOTIFICATION_TYPES = [
        ("trial_started", "Trial Started"),
        ("trial_reminder", "Trial Reminder"),
        ("trial_ending", "Trial Ending"),
        ("trial_ended", "Trial Ended"),
        ("subscription_expiring", "Subscription Expiring"),
        ("subscription_expired", "Subscription Expired"),
        ("payment_successful", "Payment Successful"),
        ("payment_failed", "Payment Failed"),
    ]

    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(auto_prefetch.Model.Meta):
        ordering = ["-created_at"]

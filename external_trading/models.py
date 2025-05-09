# external_trading/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import secrets

User = get_user_model()


class PlatformType(models.TextChoices):
    TRADING_VIEW = "trading_view", "TradingView"
    RSI30 = "rsi30", "RSI30"
    CUSTOM = "custom", "Custom Platform"


class ExternalConnection(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="external_connections"
    )
    platform_type = models.CharField(max_length=50, choices=PlatformType.choices)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.name} ({self.platform_type})"

    class Meta:
        unique_together = ("user", "name", "platform_type")


class ApiKey(models.Model):
    connection = models.ForeignKey(
        ExternalConnection, on_delete=models.CASCADE, related_name="api_keys"
    )
    key_id = models.UUIDField(default=uuid.uuid4, editable=False)
    api_key = models.CharField(max_length=64, unique=True)
    secret_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(32)
            self.secret_key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"API Key: {self.key_id}"

    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def update_last_used(self):
        self.last_used = timezone.now()
        self.save(update_fields=["last_used"])


class ExternalPlatformPermission(models.Model):
    connection = models.OneToOneField(
        ExternalConnection, on_delete=models.CASCADE, related_name="permissions"
    )
    can_view_positions = models.BooleanField(default=True)
    can_open_trades = models.BooleanField(default=True)
    can_close_trades = models.BooleanField(default=False)
    max_trade_size = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    max_daily_trades = models.IntegerField(null=True, blank=True)
    allowed_symbols = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Permissions for {self.connection}"


class ExternalTradingLog(models.Model):
    connection = models.ForeignKey(
        ExternalConnection, on_delete=models.CASCADE, related_name="logs"
    )
    action = models.CharField(max_length=50)  # open_trade, close_trade, view_positions
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_data = models.JSONField(null=True, blank=True)
    response_data = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20)  # success, failed
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.action} by {self.connection} at {self.timestamp}"

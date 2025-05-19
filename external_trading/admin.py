# external_trading/admin.py
from django.contrib import admin
from .models import (
    ExternalConnection,
    ApiKey,
    ExternalPlatformPermission,
    ExternalTradingLog,
    PlatformType,
)


class ApiKeyInline(admin.TabularInline):
    model = ApiKey
    extra = 0
    readonly_fields = (
        "key_id",
        "api_key",
        "secret_key",
        "created_at",
        "last_used",
        "is_active",
    )
    can_delete = False


class ExternalPlatformPermissionInline(admin.StackedInline):
    model = ExternalPlatformPermission
    extra = 0
    max_num = 1


@admin.register(ExternalConnection)
class ExternalConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "name",
        "platform_type",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("platform_type", "is_active", "created_at")
    search_fields = ("user__email", "name", "platform_type")
    inlines = [ApiKeyInline, ExternalPlatformPermissionInline]
    ordering = ("-created_at",)


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = (
        "connection",
        "key_id",
        "api_key",
        "is_active",
        "created_at",
        "expires_at",
        "last_used",
    )
    list_filter = ("is_active", "created_at", "expires_at")
    search_fields = ("connection__name", "key_id", "api_key")
    readonly_fields = ("key_id", "api_key", "secret_key", "created_at", "last_used")
    ordering = ("-created_at",)


@admin.register(ExternalPlatformPermission)
class ExternalPlatformPermissionAdmin(admin.ModelAdmin):
    list_display = (
        "connection",
        "can_view_positions",
        "can_open_trades",
        "can_close_trades",
        "max_trade_size",
        "max_daily_trades",
    )
    search_fields = ("connection__name",)
    ordering = ("connection__name",)


@admin.register(ExternalTradingLog)
class ExternalTradingLogAdmin(admin.ModelAdmin):
    list_display = ("connection", "action", "timestamp", "status", "ip_address")
    list_filter = ("action", "status", "timestamp")
    search_fields = (
        "connection__name",
        "action",
        "status",
        "ip_address",
        "error_message",
    )
    readonly_fields = ("timestamp",)
    ordering = ("-timestamp",)

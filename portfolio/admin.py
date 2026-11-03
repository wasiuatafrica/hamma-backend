from pyexpat.errors import messages
from django.contrib import admin
from django.utils import timezone

from .models import (
    ButtonClick,
    DashboardFeed,
    Stock,
    PayStackReceipts,
    Receipts,
    WithdrawalOTPRequest,
    Wallet,
    Transaction,
    Alert,
    AlertAI,
    AlertAITracker,
    Conversation,
    Message,
    DemoTransaction,
    FeedsCategory,
    ViewOtherIdeasLog,
    OpenedDashboardFeed,
    BonusWallet,
    CompanyFundamental,
    CompanyProfile,
)
from .models import DataSourceSetting, MarketHoliday, StockChange, StockSyncRun


@admin.register(DemoTransaction)
class DemoTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "transaction_type", "amount", "date", "status")
    search_fields = ("user__username", "transaction_type", "status")
    list_filter = ("transaction_type", "status", "date")
    ordering = ("-date",)
    date_hierarchy = "date"


@admin.register(BonusWallet)
class BonusWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "created")
    search_fields = ["user__email"]


class StockAdmin(admin.ModelAdmin):
    search_fields = ["symbol", "company", "isin"]
    list_display = ("company", "symbol", "isin", "tv_symbol", "ngx_status", "active")
    list_filter = ("active", "ngx_status")


admin.site.register(Stock, StockAdmin)
admin.site.register(PayStackReceipts)
admin.site.register(Receipts)
admin.site.register(WithdrawalOTPRequest)
admin.site.register(Wallet)


@admin.register(CompanyFundamental)
class CompanyFundamentalAdmin(admin.ModelAdmin):
    list_display = ("stock", "market_cap")
    search_fields = ["stock__symbol"]


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = (
        "stock",
        "company_name",
        "shares_outstanding",
        "prev_close",
        "updated",
    )
    search_fields = ["stock__symbol", "company_name"]
    readonly_fields = ("created", "updated", "raw_ngx_data")


@admin.register(DataSourceSetting)
class DataSourceSettingAdmin(admin.ModelAdmin):
    list_display = ("source", "updated")
    actions = None


class TransactionAdmin(admin.ModelAdmin):
    # Displaying all relevant fields in the list view
    list_display = ("user", "transaction_type", "amount", "date", "status", "channel")

    # Allowing filtering by the 'status' field
    list_filter = ("status",)

    # Adding a search field for searching by user email
    search_fields = ["user__email"]


admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Alert)
admin.site.register(FeedsCategory)
admin.site.register(AlertAI)
admin.site.register(AlertAITracker)
admin.site.register(Message)
admin.site.register(Conversation)
admin.site.register(ButtonClick)
admin.site.register(DashboardFeed)
admin.site.register(ViewOtherIdeasLog)
admin.site.register(OpenedDashboardFeed)


@admin.register(MarketHoliday)
class MarketHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")
    ordering = ("-date",)


@admin.register(StockSyncRun)
class StockSyncRunAdmin(admin.ModelAdmin):
    list_display = ("started", "applied", "listed_count", "has_error")
    list_filter = ("applied",)
    readonly_fields = [f.name for f in StockSyncRun._meta.fields]

    @admin.display(boolean=True, description="Error")
    def has_error(self, obj):
        return bool(obj.error)


@admin.register(StockChange)
class StockChangeAdmin(admin.ModelAdmin):
    """NGX listing changes. Approve a pending delisting to deactivate the stock."""

    list_display = ("created", "kind", "symbol", "old_value", "new_value", "status", "holders")
    list_filter = ("status", "kind")
    search_fields = ("symbol", "old_value", "new_value", "isin")
    readonly_fields = [
        f.name for f in StockChange._meta.fields if f.name not in ("note",)
    ]
    actions = ["approve", "reject"]

    @admin.action(description="Approve (delistings: deactivate the stock)")
    def approve(self, request, queryset):
        done = 0
        for change in queryset.filter(status=StockChange.PENDING):
            if change.kind == StockChange.DELISTED and change.stock_id:
                Stock.objects.filter(pk=change.stock_id).update(
                    active=False, tv_symbol=None
                )
            change.status = StockChange.APPROVED
            change.resolved_at = timezone.now()
            change.resolved_by = request.user
            change.save(update_fields=["status", "resolved_at", "resolved_by"])
            done += 1
        self.message_user(request, f"Approved {done} change(s).")

    @admin.action(description="Reject (keep the stock as it is)")
    def reject(self, request, queryset):
        done = queryset.filter(status=StockChange.PENDING).update(
            status=StockChange.REJECTED,
            resolved_at=timezone.now(),
            resolved_by=request.user,
        )
        self.message_user(request, f"Rejected {done} change(s).")

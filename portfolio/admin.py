from pyexpat.errors import messages
from django.contrib import admin

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
from .models import DataSourceSetting, MarketHoliday


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

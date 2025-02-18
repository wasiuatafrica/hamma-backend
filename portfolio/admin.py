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
)


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
    search_fields = ["symbol"]


admin.site.register(Stock, StockAdmin)
admin.site.register(PayStackReceipts)
admin.site.register(Receipts)
admin.site.register(WithdrawalOTPRequest)
admin.site.register(Wallet)


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

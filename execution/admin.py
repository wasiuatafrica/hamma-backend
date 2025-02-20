from django.contrib import admin
from .models import (
    DemoPortfolio,
    DemoPosition,
    DemoTrade,
    DemoProfitLoss,
    Portfolio,
    WithdrawalRequest,
    Position,
    DemoDailyReturns,
    DailyReturns,
    DemoCumulativeReturns,
    CumulativeReturns,
    DemoDailyReturns2,
    CumulativeMarketReturns,
    MarketReturns,
    PropReceipt,
    HammaAccountRequest,
)
from simple_history.admin import SimpleHistoryAdmin


@admin.register(HammaAccountRequest)
class HammaAccountRequestAdmin(SimpleHistoryAdmin):
    list_display = ["user", "account", "status", "created", "comment", "updated"]
    search_fields = ["user__email", "account"]
    list_filter = ["status", "created"]


class DemoPositionAdmin(admin.ModelAdmin):
    search_fields = [
        "portfolio__user__email",
        "portfolio__account_name",
        "portfolio__account_id",
    ]
    list_display = [
        "id",
        "portfolio",
        "stock",
        "status",
        "quantity",
        "open_price",
        "amount_invested",
        "profit_loss",
        "swap_fee",
        "created",
        "closed_at",
        "updated",
    ]
    list_filter = ["status", "created", "stock"]


admin.site.register(DemoPosition, DemoPositionAdmin)
admin.site.register(DemoTrade)


class DemoPortfolioAdmin(SimpleHistoryAdmin):
    search_fields = ["user__email", "account_name", "account_id"]
    list_display = (
        "id",
        "user",
        "account_name",
        "account_id",
        "balance",
        "model_type",
        "is_prop",
        "activated",
        "initial_balance",
        "receipt_approved",
        "target_met",
        "blown",
        "inactive_by_inactivity",
        "has_hamma",
        "created",
    )
    list_filter = ["is_prop", "created"]


admin.site.register(DemoPortfolio, DemoPortfolioAdmin)
admin.site.register(DemoProfitLoss)


class DemoDailyReturnsAdmin(admin.ModelAdmin):
    search_fields = ["user__email"]


admin.site.register(DemoDailyReturns, DemoDailyReturnsAdmin)


class DemoDailyReturnsAdmin2(admin.ModelAdmin):
    search_fields = ["user__email"]


admin.site.register(DemoDailyReturns2, DemoDailyReturnsAdmin2)
# admin.site.register(DemoDailyReturns)


class DemoCumulativeReturnsAdmin(admin.ModelAdmin):
    search_fields = ["user__email"]


admin.site.register(DemoCumulativeReturns, DemoCumulativeReturnsAdmin)

admin.site.register(CumulativeReturns)
admin.site.register(CumulativeMarketReturns)
admin.site.register(MarketReturns)
admin.site.register(Position)
admin.site.register(Portfolio)
admin.site.register(DailyReturns)
admin.site.register(WithdrawalRequest, SimpleHistoryAdmin)
admin.site.register(PropReceipt, SimpleHistoryAdmin)

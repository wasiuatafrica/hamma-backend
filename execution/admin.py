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
)


class DemoPositionAdmin(admin.ModelAdmin):
    search_fields = ["portfolio__user__email", "portfolio__account_name"]
    list_display = ["portfolio", "stock", "quantity", "open_price", "created"]


admin.site.register(DemoPosition, DemoPositionAdmin)
admin.site.register(DemoTrade)


class DemoPortfolioAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "account_name", "account_id"]
    list_display = (
        "user",
        "account_name",
        "account_id",
        "balance",
        "created",
    )


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
admin.site.register(WithdrawalRequest)

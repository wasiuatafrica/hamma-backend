from django.contrib import admin
from .models import (DemoPortfolio, DemoPosition, DemoTrade, DemoProfitLoss, Portfolio, WithdrawalRequest,Position, DemoDailyReturns, DailyReturns,
                     DemoCumulativeReturns, CumulativeReturns,
                     )




admin.site.register(DemoPosition)
admin.site.register(DemoTrade)
admin.site.register(DemoPortfolio)
admin.site.register(DemoProfitLoss)
admin.site.register(DemoDailyReturns)
admin.site.register(DemoCumulativeReturns)
admin.site.register(CumulativeReturns)
admin.site.register(Position)
admin.site.register(Portfolio)
admin.site.register(DailyReturns)
admin.site.register(WithdrawalRequest)

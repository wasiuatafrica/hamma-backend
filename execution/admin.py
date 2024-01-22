from django.contrib import admin
from .models import DemoPortfolio, DemoPosition, DemoTrade, DemoProfitLoss, Portfolio, Position, ProfitLoss



admin.site.register(DemoPosition)
admin.site.register(DemoTrade)
admin.site.register(DemoPortfolio)
admin.site.register(DemoProfitLoss)
admin.site.register(ProfitLoss)
admin.site.register(Position)
admin.site.register(Portfolio)

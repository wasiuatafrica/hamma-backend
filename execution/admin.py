from django.contrib import admin
from .models import DemoPortfolio, DemoPosition, DemoTrade, DemoProfitLoss



admin.site.register(DemoPosition)
admin.site.register(DemoTrade)
admin.site.register(DemoPortfolio)
admin.site.register(DemoProfitLoss)

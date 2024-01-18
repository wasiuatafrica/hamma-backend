from django.contrib import admin
from .models import DemoPortfolio, DemoPosition, DemoTrade



admin.site.register(DemoPosition)
admin.site.register(DemoTrade)
admin.site.register(DemoPortfolio)

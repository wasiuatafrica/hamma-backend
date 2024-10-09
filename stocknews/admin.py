from django.contrib import admin
from .models import StockNews


# Register your models here.
class StockNewsAdmin(admin.ModelAdmin):
    list_display = [
        "stock",
        "title",
        "published_date",
        "url",
    ]
    search_fields = [
        "stock__symbol",
        "title",
    ]


admin.site.register(StockNews, StockNewsAdmin)

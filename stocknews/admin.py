from django.contrib import admin
from .models import StockNews


# Register your models here.
class StockNewsAdmin(admin.ModelAdmin):
    list_display = [
        "stock",
        "title",
        "published_date",
        "body",
        "ai_summary",
        "created",
        "url",
    ]
    search_fields = [
        "stock__symbol",
        "title",
    ]

    ordering = ["-created"]
    list_filter = ["stock__symbol", "published_date", "created"]


admin.site.register(StockNews, StockNewsAdmin)

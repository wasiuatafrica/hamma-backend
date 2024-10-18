from django.contrib import admin
from .models import StockNews


def mark_as_validated(modeladmin, request, queryset):
    queryset.update(validated=True)


mark_as_validated.short_description = "Mark selected news as validated"


class StockNewsAdmin(admin.ModelAdmin):
    list_display = [
        "stock",
        "title",
        "published_date",
        "body",
        "ai_summary",
        "created",
        "validated",
        "url",
    ]
    search_fields = [
        "stock__symbol",
        "title",
    ]

    ordering = ["-created"]
    list_filter = ["stock__symbol", "published_date", "created"]
    actions = [mark_as_validated]


admin.site.register(StockNews, StockNewsAdmin)

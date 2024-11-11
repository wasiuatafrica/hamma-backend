from django.contrib import admin
from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "amount", "request_date", "status")
    list_filter = ("status", "request_date")
    search_fields = ("portfolio__account_id", "portfolio__user__email")
    actions = ["mark_as_paid"]

    def mark_as_paid(self, request, queryset):
        queryset.update(status="paid")

    mark_as_paid.short_description = "Mark selected payouts as paid"

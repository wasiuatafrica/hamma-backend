from django.contrib import admin

from .models import (
    Payout,
    PropReferral,
    PropReferralHistory,
    PropReferralWallet,
    PropWithdrawalRequest,
)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "amount", "request_date", "status")
    list_filter = ("status", "request_date")
    search_fields = ("portfolio__account_id", "portfolio__user__email")
    actions = ["mark_as_paid"]

    def mark_as_paid(self, request, queryset):
        queryset.update(status="paid")

    mark_as_paid.short_description = "Mark selected payouts as paid"


@admin.register(PropReferral)
class PropReferralAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referee", "status", "created_at", "updated")
    list_filter = ("status", "created_at")
    search_fields = ("referrer__email", "referee__email")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated")


@admin.register(PropReferralWallet)
class PropReferralWalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "total_earned", "last_updated", "created_at")
    search_fields = ("user__email",)
    readonly_fields = ("last_updated", "created_at")
    list_filter = ("created_at", "last_updated")


@admin.register(PropReferralHistory)
class PropReferralHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transaction_type", "status", "created_at")
    list_filter = ("transaction_type", "status", "created_at")
    search_fields = ("user__email", "comment")
    readonly_fields = ("created_at", "updated")
    date_hierarchy = "created_at"


@admin.register(PropWithdrawalRequest)
class PropWithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__email", "admin_comment", "bank_details")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("user", "amount", "status")}),
        ("Details", {"fields": ("bank_details", "admin_comment", "history_entry")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

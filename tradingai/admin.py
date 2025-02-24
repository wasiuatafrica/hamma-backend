from django.contrib import admin
from .models import SubscriptionPlan, Subscription, Trial, SubscriptionNotification


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "is_active",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "description")
    list_filter = ("is_active", "created_at", "updated_at")
    ordering = ("price",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "start_date",
        "end_date",
        "last_billing_date",
        "next_billing_date",
        "cancel_at_period_end",
        "payment_reference",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__username", "plan__name", "payment_reference")
    list_filter = ("status", "cancel_at_period_end", "created_at", "updated_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")

    def activate_subscriptions(self, request, queryset):
        queryset.update(status="active")

    activate_subscriptions.short_description = "Mark selected subscriptions as active"

    actions = [activate_subscriptions]


@admin.register(Trial)
class TrialAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "start_date",
        "end_date",
        "is_active",
        "first_reminder_sent",
        "halfway_reminder_sent",
        "final_reminder_sent",
        "trial_ended_notification_sent",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__username",)
    list_filter = ("is_active", "created_at", "updated_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SubscriptionNotification)
class SubscriptionNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "notification_type",
        "title",
        "is_read",
        "is_email_sent",
        "created_at",
    )
    search_fields = ("user__username", "title", "message")
    list_filter = ("notification_type", "is_read", "is_email_sent", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

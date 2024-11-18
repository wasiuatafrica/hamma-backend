from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from execution.models import DiscountCode


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    # List display configuration
    list_display = (
        "code",
        "user_email",
        "discount_percentage",
        "type",
        "is_active_status",
        "expiry_status",
        "usage_count",
        "created",
    )

    # Filtering options
    list_filter = (
        "is_active",
        "type",
        "domain",
        "acc_model",
        "created",
    )

    # Search configuration
    search_fields = (
        "code",
        "user__email",
        "description",
        "domain",
    )

    # Fields grouping in detail view
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("code", "discount_percentage", "type", "description")},
        ),
        (
            "Usage Settings",
            {"fields": ("is_active", "expiry_date", "use_limit", "num_of_accounts")},
        ),
        (
            "User and Model Settings",
            {"fields": ("user", "domain", "acc_model", "acc_size")},
        ),
    )

    # Readonly fields
    readonly_fields = ("created",)

    # Custom display methods
    def user_email(self, obj):
        return obj.user.email if obj.user else "No User"

    user_email.short_description = "User Email"

    def is_active_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✔</span>')
        return format_html('<span style="color: red;">✘</span>')

    is_active_status.short_description = "Active"

    def expiry_status(self, obj):
        if not obj.expiry_date:
            return "No expiry"
        if obj.expiry_date > timezone.now():
            remaining = obj.expiry_date - timezone.now()
            return f"Valid ({remaining.days} days left)"
        return format_html('<span style="color: red;">Expired</span>')

    expiry_status.short_description = "Expiry Status"

    def usage_count(self, obj):
        total = obj.total_used()
        if obj.use_limit:
            return f"{total}/{obj.use_limit}"
        return total

    usage_count.short_description = "Usage"

    # Actions
    actions = ["activate_codes", "deactivate_codes"]

    def activate_codes(self, request, queryset):
        queryset.update(is_active=True)

    activate_codes.short_description = "Activate selected discount codes"

    def deactivate_codes(self, request, queryset):
        queryset.update(is_active=False)

    deactivate_codes.short_description = "Deactivate selected discount codes"

    # Form customization
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["description"].widget.attrs[
            "style"
        ] = "width: 45em; height: 5em;"
        return form

    # Ordering
    ordering = ("-created",)

    # Save model customization
    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)

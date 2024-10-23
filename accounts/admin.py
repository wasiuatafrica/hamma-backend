from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import (
    CustomUser,
    Profile,
    Referral,
    FirstLogin,
    UserActivityLog,
    AdminUserActivityLog,
    TradingProfile,
)


class ProfileAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "referral_code"]


admin.site.register(Profile, ProfileAdmin)


class ReferralAdmin(admin.ModelAdmin):
    search_fields = ["user__email"]


admin.site.register(Referral, ReferralAdmin)
admin.site.register(FirstLogin)
admin.site.register(UserActivityLog)
admin.site.register(AdminUserActivityLog)


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = (
        "email",
        "id",
        "firstname",
        "lastname",
        "is_staff",
        "is_active",
        "twofa_type",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "firstname",
                    "lastname",
                    "password",
                    "twofa_type",
                    "last_login",
                    "date_joined",
                    "has_2fa",
                    "totp_url",
                    "last_ip",
                    "last_location",
                    "last_device",
                )
            },
        ),
        (
            "Permissions",
            {"fields": ("is_superuser", "is_staff", "is_active", "is_analyst")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "firstname",
                    "lastname",
                    "email",
                    "password1",
                    "password2",
                    "twofa_type",
                    "last_login",
                    "date_joined",
                    "has_2fa",
                    "totp_url",
                    "last_ip",
                    "last_location",
                    "last_device",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    search_fields = ("email",)
    ordering = ("-date_joined",)
    readonly_fields = ("id",)


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(TradingProfile)
class TradingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "trader",
        "trading_frequency",
        "trading_style",
        "risk_tolerance",
        "market_sentiment",
    )
    list_filter = ("trading_frequency", "trading_style", "risk_tolerance")
    search_fields = ("trader__email",)

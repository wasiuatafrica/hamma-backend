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
    TwoFactorToken,
)


class ProfileAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "referral_code"]
    list_display = ["user__email", "phone"]


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
        "date_joined",
        "signup_route",
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
                    "signup_route",
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
                    "signup_route",
                ),
            },
        ),
    )

    search_fields = ("email", "firstname", "lastname")
    ordering = ("-date_joined",)
    readonly_fields = ("id",)
    list_filter = ["signup_route"]


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(TradingProfile)
class TradingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "trader",
        "trading_frequency",
        "trading_style",
        "risk_tolerance",
        "preferred_asset_type",
        "preferred_stocks",
        "market_sentiment1",
        "market_sentiment2",
    )
    list_filter = ("trading_frequency", "trading_style", "risk_tolerance")
    search_fields = ("trader__email",)


@admin.register(TwoFactorToken)
class TwoFactorTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "token",
        "expiration",
    )
    search_fields = ("user__email", "token")

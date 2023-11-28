from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from Accounts.forms import CustomUserCreationForm, CustomUserChangeForm
from Accounts.models import CustomUser, Profile, Referral, FirstLogin, ReferralPayment

class ProfileAdmin(admin.ModelAdmin):
    search_fields = ['user__email','referral_code']
admin.site.register(Profile,ProfileAdmin)
class ReferralAdmin(admin.ModelAdmin):
    search_fields = ['user__email']

admin.site.register(Referral, ReferralAdmin)
admin.site.register(FirstLogin)
class ReferralPaymentAdmin(admin.ModelAdmin):
    search_fields = ("user__email",)

admin.site.register(ReferralPayment,ReferralPaymentAdmin)


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = (
        "firstname",
        "lastname",
        "email",
        "is_staff",
        "is_active",
        "is_ft9ja_staff",
        "is_ft9ja_staff_payouts",
        "is_ft9ja_staff_receipts",
    )
    
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "firstname",
                    "lastname",
                    "email",
                    "password",
                    # "phone",
                    "is_ft9ja_staff",
                    "is_ft9ja_staff_payouts",
                    "is_ft9ja_staff_receipts",
                )
            },
        ),
        ("Permissions", {"fields": ("is_superuser","is_staff", "is_active")}),
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
                    # "phone",
                    "is_staff",
                    "is_active",
                    "is_ft9ja_staff",
                    "is_ft9ja_staff_payouts",
                    "is_ft9ja_staff_receipts",
                ),
            },
        ),
    )
    search_fields = ("email",)
    ordering = ("email",)


admin.site.register(CustomUser, CustomUserAdmin)

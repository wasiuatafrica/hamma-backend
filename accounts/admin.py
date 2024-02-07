from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser, Profile, Referral, FirstLogin, UserActivityLog, AdminUserActivityLog

class ProfileAdmin(admin.ModelAdmin):
    search_fields = ['user__email','referral_code']
admin.site.register(Profile,ProfileAdmin)
class ReferralAdmin(admin.ModelAdmin):
    search_fields = ['user__email']

admin.site.register(Referral, ReferralAdmin)
admin.site.register(FirstLogin)
admin.site.register(UserActivityLog)
admin.site.register(AdminUserActivityLog)

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
        'twofa_type',)
    
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "firstname",
                    "lastname",
                    "email",
                    "password",
                    'twofa_type',
                    # "phone",
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
                    "is_active",)
            },
        ),
    )
    search_fields = ("email",)
    ordering = ("email",)


admin.site.register(CustomUser, CustomUserAdmin)

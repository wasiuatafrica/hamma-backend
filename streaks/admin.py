from django.contrib import admin
from .models import (
    UserActivityBadge,
    UserDailyStreak,
    Leaderboard,
    Reward,
    UserStreakRun,
    UserDailyTradeActivity,
)


class UserActivityBadgeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "badge_name",
    )
    list_filter = ("badge_name",)
    search_fields = ("user__email", "badge_name")


admin.site.register(UserActivityBadge, UserActivityBadgeAdmin)


class UserDailyStreakAdmin(admin.ModelAdmin):
    # list_display = ("user", "streak_count", "last_active_date")
    search_fields = ("user__email",)


admin.site.register(UserDailyStreak, UserDailyStreakAdmin)
admin.site.register(Leaderboard)
admin.site.register(Reward)
admin.site.register(UserStreakRun)
admin.site.register(UserDailyTradeActivity)

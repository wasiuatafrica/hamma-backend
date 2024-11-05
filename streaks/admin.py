from django.contrib import admin
from .models import (
    UserActivityBadge,
    UserDailyStreak,
    Leaderboard,
    Reward,
    UserStreakRun,
    UserDailyTradeActivity,
    RewardAmount,
)


class UserActivityBadgeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "badge_name",
    )
    list_filter = ("badge_name",)
    search_fields = ("user__email", "badge_name")


admin.site.register(UserActivityBadge, UserActivityBadgeAdmin)


admin.site.register(Leaderboard)
admin.site.register(RewardAmount)
admin.site.register(Reward)


@admin.register(UserStreakRun)
class UserStreakRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "demo_portfolio",
        "comp_portfolio",
        "end_date",
        "is_active",
        "streak_length",
    )
    list_filter = ("is_active", "start_date", "end_date")
    search_fields = ("user__email", "demo_portfolio__id", "comp_portfolio__id")

    fields = (
        "user",
        "demo_portfolio",
        "comp_portfolio",
        "end_date",
        "is_active",
    )


@admin.register(UserDailyTradeActivity)
class UserDailyTradeActivityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "streak_run",
        "demo_portfolio",
        "comp_portfolio",
        "trade_date",
    )
    list_filter = ("trade_date",)
    search_fields = (
        "user__email",
        "streak_run__id",
        "demo_portfolio__id",
        "comp_portfolio__id",
    )
    date_hierarchy = "trade_date"

    fields = ("user", "streak_run", "demo_portfolio", "comp_portfolio", "trade_date")


@admin.register(UserDailyStreak)
class UserDailyStreakAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "demo_portfolio",
        "comp_portfolio",
        "current_streak",
        "longest_streak",
    )
    list_filter = ("current_streak", "longest_streak")
    search_fields = ("user__email", "demo_portfolio__id", "comp_portfolio__id")

    fields = (
        "user",
        "demo_portfolio",
        "comp_portfolio",
        "current_streak",
        "longest_streak",
    )

    def get_readonly_fields(self, request, obj=None):
        # Make streak_length read-only since it's a property
        if isinstance(obj, UserStreakRun):
            return ("streak_length",)
        return ()

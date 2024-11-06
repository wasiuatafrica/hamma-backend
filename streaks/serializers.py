from rest_framework import serializers
from django.utils import timezone

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    UserDailyStreak,
    UserDailyTradeActivity,
    UserStreakRun,
)
from accounts.serializers import ShortCustomUserInfoSerializer


# class UserDailyTradeActivitySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserDailyTradeActivity
#         fields = ["trade_date"]


# class UserStreakRunSerializer(serializers.ModelSerializer):
#     trade_days = UserDailyTradeActivitySerializer(source="daily_activities", many=True)

#     class Meta:
#         model = UserStreakRun
#         fields = ["id", "start_date", "end_date", "is_active", "trade_days"]


# class UserDailyStreakSerializer(serializers.ModelSerializer):
#     current_streak_run = UserStreakRunSerializer(
#         source="get_active_streak_run", read_only=True
#     )
#     longest_streak_run = serializers.IntegerField(
#         source="longest_streak", read_only=True
#     )

#     class Meta:
#         model = UserDailyStreak
#         fields = ["user", "longest_streak_run", "current_streak_run"]


class UserDailyTradeActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDailyTradeActivity
        fields = ["trade_date"]


class UserStreakRunSerializer(serializers.ModelSerializer):
    trade_days = UserDailyTradeActivitySerializer(source="daily_activities", many=True)
    week_number = serializers.SerializerMethodField()

    def get_week_number(self, obj):
        return obj.start_date.isocalendar()[1]

    class Meta:
        model = UserStreakRun
        fields = [
            "id",
            "start_date",
            "end_date",
            "is_active",
            "trade_days",
            "week_number",
            "previous_streak",
        ]


class UserDailyStreakSerializer(serializers.ModelSerializer):
    current_streak_run = UserStreakRunSerializer(
        source="get_active_streak_run", read_only=True
    )
    longest_streak_run = serializers.IntegerField(
        source="longest_streak", read_only=True
    )
    current_week_progress = serializers.SerializerMethodField()

    def get_current_week_progress(self, obj):
        if not obj.current_week_start:
            return 0
        today = timezone.now().date()
        days_in_current_week = (today - obj.current_week_start).days + 1
        return min(days_in_current_week, 5)  # Assuming 5 trading days per week

    class Meta:
        model = UserDailyStreak
        fields = [
            "user",
            "longest_streak_run",
            "current_streak_run",
            "current_week_progress",
        ]


class UserActivityBadgeSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserActivityBadge
        fields = ["user", "badge_name", "awarded_on"]


class LeaderboardSerializer(serializers.ModelSerializer):
    user = ShortCustomUserInfoSerializer()

    class Meta:
        model = Leaderboard
        fields = [
            "user",
            "position",
            "streak_count",
            "reward_amount",
            "trade_volume",
            "week_start_date",
        ]


class RewardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Reward
        fields = ["user", "reward_amount", "awarded_on", "reason"]

from rest_framework import serializers

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    UserDailyStreak,
    UserDailyTradeActivity,
    UserStreakRun,
)
from accounts.serializers import ShortCustomUserInfoSerializer


class UserDailyTradeActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDailyTradeActivity
        fields = ["trade_date"]


class UserStreakRunSerializer(serializers.ModelSerializer):
    trade_days = UserDailyTradeActivitySerializer(source="daily_activities", many=True)

    class Meta:
        model = UserStreakRun
        fields = ["id", "start_date", "end_date", "is_active", "trade_days"]


class UserDailyStreakSerializer(serializers.ModelSerializer):
    current_streak_run = UserStreakRunSerializer(
        source="get_active_streak_run", read_only=True
    )
    longest_streak_run = serializers.IntegerField(
        source="longest_streak", read_only=True
    )

    class Meta:
        model = UserDailyStreak
        fields = ["user", "longest_streak_run", "current_streak_run"]


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

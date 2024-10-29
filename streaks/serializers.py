from rest_framework import serializers
from .models import UserDailyStreak, UserActivityBadge, Leaderboard, Reward


class UserDailyStreakSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserDailyStreak
        fields = ["user", "streak_count", "last_active_date"]


class UserActivityBadgeSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserActivityBadge
        fields = ["user", "badge_name", "awarded_on"]


class LeaderboardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Leaderboard
        fields = ["user", "position", "streak_count", "trade_volume", "week_start_date"]


class RewardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Reward
        fields = ["user", "reward_amount", "awarded_on", "reason"]

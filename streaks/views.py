from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    UserDailyStreak,
    UserDailyTradeActivity,
    UserStreakRun,
)
from .serializers import (
    LeaderboardSerializer,
    RewardSerializer,
    UserActivityBadgeSerializer,
    UserDailyStreakSerializer,
    UserStreakRunSerializer,
)


class LeaderboardAPIView(APIView):
    def get(self, request):
        # Get the current week's leaderboard data
        current_week_start = timezone.now().date() - timezone.timedelta(
            days=timezone.now().date().weekday()
        )
        leaderboard = Leaderboard.objects.filter(
            week_start_date=current_week_start
        ).order_by("position")
        serializer = LeaderboardSerializer(leaderboard, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CurrentStreakAPIView(APIView):
    """
    Get the details of the current active streak for a user.
    """

    def get(self, request):
        streak_info = get_object_or_404(UserDailyStreak, user=request.user)
        serializer = UserDailyStreakSerializer(streak_info)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LongestStreakAPIView(APIView):
    """
    Get the longest streak achieved by the user.
    """

    def get(self, request):
        streak_info = get_object_or_404(UserDailyStreak, user=request.user)
        longest_streak_run = streak_info.longest_streak
        return Response(
            {"longest_streak": longest_streak_run}, status=status.HTTP_200_OK
        )


class StreakCalendarAPIView(APIView):
    """
    Get the calendar view of trading days in the current streak run.
    """

    def get(self, request):
        streak_info = get_object_or_404(UserDailyStreak, user=request.user)
        active_streak_run = streak_info.get_active_streak_run()

        if not active_streak_run:
            return Response(
                {"error": "No active streak run found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only include trade dates from the last missed date if any
        trade_activities = active_streak_run.daily_activities.order_by("trade_date")
        trade_dates = [activity.trade_date for activity in trade_activities]

        return Response({"trade_dates": trade_dates}, status=status.HTTP_200_OK)


class UserActivityBadgeAPIView(APIView):
    def get(self, request, user_id=None):
        if user_id:
            # Fetch badges for a specific user
            badges = UserActivityBadge.objects.filter(user__id=user_id)
            serializer = UserActivityBadgeSerializer(badges, many=True)
        else:
            # Fetch all badges
            badges = UserActivityBadge.objects.all()
            serializer = UserActivityBadgeSerializer(badges, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserRewardAPIView(APIView):
    def get(self, request, user_id=None):
        if user_id:
            # Fetch rewards for a specific user
            rewards = Reward.objects.filter(user__id=user_id)
            serializer = RewardSerializer(rewards, many=True)
        else:
            # Fetch all rewards
            rewards = Reward.objects.all()
            serializer = RewardSerializer(rewards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

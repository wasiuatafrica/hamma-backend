from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from execution.models import DemoPosition
from competition.models import CompetitionPosition
from datetime import timedelta

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
from .tasks import update_user_streaks_daily
from competition.models import CompetitionPortfolio
from execution.models import DemoPortfolio


class LeaderboardAPIView(APIView):
    def get(self, request):
        update_user_streaks_daily()
        """
        Get the current week's leaderboard data.
        """
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
        account_type = request.GET.get("account_type")
        account_id = request.GET.get("account_id")

        if not (account_id and account_type):
            return Response(
                {"error": "account_id and account_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get account and streak info based on account type
        if account_type == "competition":
            account = get_object_or_404(CompetitionPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, comp_portfolio=account
            )
        elif account_type == "demo_portfolio":
            account = get_object_or_404(DemoPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, demo_portfolio=account
            )
        else:
            return Response(
                {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserDailyStreakSerializer(streak_info)

        # Calculate date range for this week
        today = timezone.now().date()
        start_of_week = today - timedelta(
            days=today.weekday()
        )  # Monday of the current week

        # Count trades for the specific account this week
        if account_type == "competition":
            num_trades = CompetitionPosition.objects.filter(
                portfolio=account,
                status=CompetitionPosition.OPEN,
                created__date__gte=start_of_week,
                created__date__lte=today,
            ).count()
        else:  # demo_portfolio
            num_trades = DemoPosition.objects.filter(
                portfolio=account,
                status=DemoPosition.OPEN,
                created__date__gte=start_of_week,
                created__date__lte=today,
            ).count()

        # Return the response with streak data and number of trades
        return Response(
            {"streak": serializer.data, "num_of_trades": num_trades},
            status=status.HTTP_200_OK,
        )


class LongestStreakAPIView(APIView):
    """
    Get the longest streak achieved by the user.
    """

    def get(self, request):

        account_type = request.GET.get("account_type")
        account_id = request.GET.get("account_id")

        if not (account_id and account_type):
            return Response(
                {"error": "account_id and account_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition":
            account = get_object_or_404(CompetitionPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, comp_portfolio=account
            )
        elif account_type == "demo_portfolio":
            account = get_object_or_404(DemoPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, demo_portfolio=account
            )
        else:
            return Response(
                {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
            )
        longest_streak_run = streak_info.longest_streak
        return Response(
            {"longest_streak": longest_streak_run}, status=status.HTTP_200_OK
        )


class StreakCalendarAPIView(APIView):
    """
    Get the calendar view of trading days in the current streak run.
    """

    def get(self, request):
        account_type = request.GET.get("account_type")
        account_id = request.GET.get("account_id")

        if not (account_id and account_type):
            return Response(
                {"error": "account_id and account_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition":
            account = get_object_or_404(CompetitionPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, comp_portfolio=account
            )
        elif account_type == "demo_portfolio":
            account = get_object_or_404(DemoPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, demo_portfolio=account
            )
        else:
            return Response(
                {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
            )

        active_streak_run = streak_info.get_active_streak_run()

        if not active_streak_run:
            return Response(
                {"error": "No active streak run found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        print("Helloooo")

        # Only include trade dates from the last missed date if any
        trade_activities = active_streak_run.daily_activities.order_by("trade_date")
        trade_dates = [activity.trade_date for activity in trade_activities]
        print(trade_dates)

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

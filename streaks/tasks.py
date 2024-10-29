from datetime import timedelta

from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone

from competition.models import CompetitionPosition
from execution.models import DemoPosition

from .models import Leaderboard, Reward, UserActivityBadge, UserDailyStreak


@shared_task
def update_user_streaks_daily():
    today = timezone.now().date()

    # Get all users and update their streaks based on today's trade activity
    for user in User.objects.all():
        # Check if the user has any open positions today
        has_open_trade_today = (
            DemoPosition.objects.filter(
                portfolio__user=user, status=DemoPosition.OPEN, created__date=today
            ).exists()
            or CompetitionPosition.objects.filter(
                portfolio__user=user,
                status=CompetitionPosition.OPEN,
                created__date=today,
            ).exists()
        )

        # Get or create the user's streak record
        streak, created = UserDailyStreak.objects.get_or_create(user=user)

        if has_open_trade_today:
            # If user opened a trade today, update the streak
            if streak.last_active_date == today - timezone.timedelta(days=1):
                streak.increment_streak()
            else:
                # If this is the first activity in a while, start a new streak
                streak.streak_count = 1
            streak.last_active_date = today
        else:
            # If no trades, reset the streak
            streak.reset_streak()

        streak.save()


@shared_task
def award_weekly_badges_and_update_leaderboard():
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    for user in User.objects.all():
        # Calculate the user's open trades for the past week
        weekly_open_trades = (
            DemoPosition.objects.filter(
                portfolio__user=user,
                status=DemoPosition.OPEN,
                created__date__range=(week_start, week_end),
            ).count()
            + CompetitionPosition.objects.filter(
                portfolio__user=user,
                status=CompetitionPosition.OPEN,
                created__date__range=(week_start, week_end),
            ).count()
        )

        # Award badges based on weekly trade count
        if weekly_open_trades >= 10:
            UserActivityBadge.objects.get_or_create(
                user=user, badge_name="Key Active User", awarded_on=week_start
            )
        elif weekly_open_trades >= 3:
            UserActivityBadge.objects.get_or_create(
                user=user, badge_name="Active User", awarded_on=week_start
            )

        # Update leaderboard position for the user
        # Get or create leaderboard record for the user
        leaderboard_entry, _ = Leaderboard.objects.get_or_create(
            user=user, week_start_date=week_start
        )
        leaderboard_entry.trade_volume = weekly_open_trades
        leaderboard_entry.streak_count = (
            UserDailyStreak.objects.filter(user=user).first().streak_count or 0
        )
        leaderboard_entry.save()

    # Rank users by streak count and then by trade volume
    leaderboard = Leaderboard.objects.filter(week_start_date=week_start).order_by(
        "-streak_count", "-trade_volume"
    )

    for position, entry in enumerate(leaderboard, start=1):
        entry.position = position
        entry.save()

    # Award rewards to the top X users (e.g., top 5)
    for entry in leaderboard[:5]:
        if not entry.reward_earned:
            Reward.objects.create(
                user=entry.user, reward_amount=100.0, reason="Top Leaderboard Reward"
            )
            entry.reward_earned = True
            entry.save()

    # Reward "Key Active User" badge holders
    key_active_users = UserActivityBadge.objects.filter(
        badge_name="Key Active User", awarded_on=week_start
    )
    for badge in key_active_users:
        Reward.objects.create(
            user=badge.user, reward_amount=50.0, reason="Key Active User Reward"
        )

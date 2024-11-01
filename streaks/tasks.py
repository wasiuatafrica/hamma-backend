import datetime
from datetime import time, timedelta

import pytz
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from competition.models import Competition, CompetitionPortfolio, CompetitionPosition
from execution.models import DemoPortfolio, DemoPosition

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    UserDailyStreak,
    UserDailyTradeActivity,
    UserStreakRun,
)

User = get_user_model()


HOLIDAYS = [
    # Add any static holidays here in YYYY-MM-DD format
    datetime.date(2025, 1, 1),  # New Year's Day
    datetime.date(2024, 7, 4),  # Independence Day
    datetime.date(2024, 12, 25),  # Christmas Day
    datetime.date(2024, 12, 26),  # Christmas Day
    # Add more holidays as needed
]


def is_within_trading_hours():
    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    return (
        current_time_lagos.time() >= time(10, 10)
        and current_time_lagos.time() <= time(14, 30)
        and current_time_lagos.weekday() < 5
    )


def is_trading_day(date):
    """
    Returns True if the date is a trading day (not a weekend or holiday).
    """
    return date.weekday() < 5 and date not in HOLIDAYS


def get_previous_trading_day(date):
    """
    Returns the most recent trading day before the given date.
    """
    previous_day = date - timedelta(days=1)
    while not is_trading_day(previous_day):
        previous_day -= timedelta(days=1)
    return previous_day


# def update_user_streaks_daily():
#     today = timezone.now().date()

#     # Get all users and update their streaks based on today's trade activity
#     for user in User.objects.all():
#         # Check if the user has any open positions today
#         has_open_trade_today = (
#             DemoPosition.objects.filter(
#                 portfolio__user=user, status=DemoPosition.OPEN, created__date=today
#             ).exists()
#             or CompetitionPosition.objects.filter(
#                 portfolio__user=user,
#                 status=CompetitionPosition.OPEN,
#                 created__date=today,
#             ).exists()
#         )

#         # Get or create the user's streak record
#         streak, created = UserDailyStreak.objects.get_or_create(user=user)

#         if has_open_trade_today:
#             # If user opened a trade today, update the streak
#             if streak.last_active_date == today - timezone.timedelta(days=1):
#                 streak.increment_streak()
#             else:
#                 # If this is the first activity in a while, start a new streak
#                 streak.streak_count = 1
#             streak.last_active_date = today
#         else:
#             # If no trades, reset the streak
#             streak.reset_streak()

#         streak.save()


# def award_weekly_badges_and_update_leaderboard():
#     today = timezone.now().date()
#     week_start = today - timedelta(days=today.weekday())
#     week_end = week_start + timedelta(days=6)

#     for user in User.objects.all():
#         # Calculate the user's open trades for the past week
#         weekly_open_trades = (
#             DemoPosition.objects.filter(
#                 portfolio__user=user,
#                 status=DemoPosition.OPEN,
#                 created__date__range=(week_start, week_end),
#             ).count()
#             + CompetitionPosition.objects.filter(
#                 portfolio__user=user,
#                 status=CompetitionPosition.OPEN,
#                 created__date__range=(week_start, week_end),
#             ).count()
#         )

#         # Award badges based on weekly trade count
#         if weekly_open_trades >= 10:
#             UserActivityBadge.objects.get_or_create(
#                 user=user, badge_name="Key Active User", awarded_on=week_start
#             )
#         elif weekly_open_trades >= 3:
#             UserActivityBadge.objects.get_or_create(
#                 user=user, badge_name="Active User", awarded_on=week_start
#             )

#         # Update leaderboard position for the user
#         # Get or create leaderboard record for the user
#         leaderboard_entry, _ = Leaderboard.objects.get_or_create(
#             user=user, week_start_date=week_start
#         )
#         leaderboard_entry.trade_volume = weekly_open_trades
#         leaderboard_entry.streak_count = (
#             UserDailyStreak.objects.filter(user=user).first().streak_count or 0
#         )
#         leaderboard_entry.save()

#     # Rank users by streak count and then by trade volume
#     leaderboard = Leaderboard.objects.filter(week_start_date=week_start).order_by(
#         "-streak_count", "-trade_volume"
#     )

#     for position, entry in enumerate(leaderboard, start=1):
#         entry.position = position
#         entry.save()

#     # Award rewards to the top X users (e.g., top 5)
#     for entry in leaderboard[:5]:
#         if not entry.reward_earned:
#             Reward.objects.create(
#                 user=entry.user, reward_amount=100.0, reason="Top Leaderboard Reward"
#             )
#             entry.reward_earned = True
#             entry.save()

#     # Reward "Key Active User" badge holders
#     key_active_users = UserActivityBadge.objects.filter(
#         badge_name="Key Active User", awarded_on=week_start
#     )
#     for badge in key_active_users:
#         Reward.objects.create(
#             user=badge.user, reward_amount=50.0, reason="Key Active User Reward"
#         )


def update_user_streaks_daily():
    """
    Daily task to update users' streaks based on trading activity.
    """
    today = timezone.now().date()
    current_competition = Competition.objects.filter(status="current").first()
    competition_accounts = CompetitionPortfolio.objects.filter(
        competition=current_competition, active=True
    )
    demo_accs = DemoPortfolio.objects.all()
    market_open_time = time(10, 10)
    market_close_time = time(14, 30)
    current_time = timezone.now().time()

    for account in demo_accs:
        # demo portfolios
        user = account.user
        print(account.account_name)
        # Check if the trade account has any trades opened today
        has_open_trade_today = DemoPosition.objects.filter(
            portfolio=account, status=DemoPosition.OPEN, updated__date=today
        ).exists()

        with transaction.atomic():
            # Fetch the account's current streak information
            streak_info, _ = UserDailyStreak.objects.get_or_create(
                user=user, demo_portfolio=account
            )
            active_streak_run = UserStreakRun.objects.filter(
                user=user, is_active=True, demo_portfolio=account
            ).first()

            if UserDailyTradeActivity.objects.filter(
                user=user, trade_date=today, demo_portfolio=account
            ).exists():
                continue

            if has_open_trade_today:
                if active_streak_run:
                    # Determine the most recent trading day before today
                    last_trade_date = (
                        UserDailyTradeActivity.objects.filter(
                            user=user,
                            streak_run=active_streak_run,
                            demo_portfolio=account,
                        )
                        .order_by("-trade_date")
                        .first()
                    )

                    previous_trading_day = get_previous_trading_day(today)

                    if (
                        last_trade_date
                        and last_trade_date.trade_date == previous_trading_day
                    ):
                        # If the last trading day was consecutive (according to trading days), continue streak
                        UserDailyTradeActivity.objects.create(
                            user=user,
                            streak_run=active_streak_run,
                            trade_date=today,
                            demo_portfolio=account,
                        )
                        streak_info.update_streak(is_new_run=False)
                    else:
                        # If not consecutive, end the current streak and start a new one
                        active_streak_run.end_streak()
                        new_streak_run = UserStreakRun.objects.create(
                            user=user, start_date=today, demo_portfolio=account
                        )
                        try:
                            UserDailyTradeActivity.objects.get_or_create(
                                user=user,
                                streak_run=active_streak_run,
                                trade_date=today,
                                demo_portfolio=account,
                            )
                            streak_info.update_streak(is_new_run=True)
                        except:
                            continue
                else:
                    # No active streak run, start a new streak
                    new_streak_run = UserStreakRun.objects.create(
                        user=user, start_date=today, demo_portfolio=account
                    )
                    UserDailyTradeActivity.objects.create(
                        user=user,
                        streak_run=new_streak_run,
                        trade_date=today,
                        demo_portfolio=account,
                    )
                    streak_info.update_streak(is_new_run=True)
            else:
                if current_time >= market_close_time:
                    if active_streak_run:
                        active_streak_run.end_streak()
                    streak_info.reset_streak()

    for account in competition_accounts:
        # competition
        user = account.user
        print(user.email)
        # Check if the trade account has any trades opened today
        has_open_trade_today = (
            # DemoPosition.objects.filter(
            #     portfolio=account, status=DemoPosition.OPEN, created__date=today
            # ).exists()
            CompetitionPosition.objects.filter(
                portfolio=account,
                status=CompetitionPosition.OPEN,
                updated__date=today,
            ).exists()
        )

        print(has_open_trade_today, "sbffdsvbdf")

        with transaction.atomic():
            # Fetch the account's current streak information
            streak_info, _ = UserDailyStreak.objects.get_or_create(
                user=user, comp_portfolio=account
            )
            active_streak_run = UserStreakRun.objects.filter(
                user=user, is_active=True, comp_portfolio=account
            ).first()

            if UserDailyTradeActivity.objects.filter(
                user=user, trade_date=today, comp_portfolio=account
            ).exists():
                continue

            if has_open_trade_today:
                if active_streak_run:
                    # Determine the most recent trading day before today
                    last_trade_date = (
                        UserDailyTradeActivity.objects.filter(
                            user=user,
                            streak_run=active_streak_run,
                            comp_portfolio=account,
                        )
                        .order_by("-trade_date")
                        .first()
                    )

                    previous_trading_day = get_previous_trading_day(today)

                    if (
                        last_trade_date
                        and last_trade_date.trade_date == previous_trading_day
                    ):
                        # If the last trading day was consecutive (according to trading days), continue streak
                        UserDailyTradeActivity.objects.create(
                            user=user,
                            streak_run=active_streak_run,
                            trade_date=today,
                            comp_portfolio=account,
                        )
                        streak_info.update_streak(is_new_run=False)
                    else:
                        # If not consecutive, end the current streak and start a new one
                        active_streak_run.end_streak()
                        new_streak_run = UserStreakRun.objects.create(
                            user=user, start_date=today, comp_portfolio=account
                        )
                        try:
                            UserDailyTradeActivity.objects.get_or_create(
                                user=user,
                                streak_run=active_streak_run,
                                trade_date=today,
                                comp_portfolio=account,
                            )
                            streak_info.update_streak(is_new_run=True)
                        except:
                            continue
                else:
                    # No active streak run, start a new streak
                    new_streak_run = UserStreakRun.objects.create(
                        user=user, start_date=today, comp_portfolio=account
                    )
                    UserDailyTradeActivity.objects.create(
                        user=user,
                        streak_run=new_streak_run,
                        trade_date=today,
                        comp_portfolio=account,
                    )
                    streak_info.update_streak(is_new_run=True)
            else:
                # If no trade, reset current streak and end any active streak run
                if active_streak_run:
                    active_streak_run.end_streak()
                streak_info.reset_streak()


@shared_task
def award_weekly_badges_and_update_leaderboard():
    """
    Weekly task to award badges and update the leaderboard based on weekly trading activity.
    """
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    for user in User.objects.all():
        # Calculate the number of trades opened by the user in the past week
        weekly_open_trades = (
            DemoPosition.objects.filter(
                portfolio__user=user,
                status=DemoPosition.OPEN,
                updated__date__range=(week_start, week_end),
            ).count()
            + CompetitionPosition.objects.filter(
                portfolio__user=user,
                status=CompetitionPosition.OPEN,
                updated__date__range=(week_start, week_end),
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

        # Update or create leaderboard entry for the user
        leaderboard_entry, _ = Leaderboard.objects.get_or_create(
            user=user, week_start_date=week_start
        )
        leaderboard_entry.trade_volume = weekly_open_trades
        leaderboard_entry.streak_count = (
            UserDailyStreak.objects.filter(user=user).first().current_streak or 0
        )
        leaderboard_entry.save()

    # Rank users by streak count and trade volume for leaderboard positions
    leaderboard = Leaderboard.objects.filter(week_start_date=week_start).order_by(
        "-streak_count", "-trade_volume"
    )

    for position, entry in enumerate(leaderboard, start=1):
        entry.position = position
        entry.save()

    # Award rewards to the top 5 users based on their leaderboard ranking
    for entry in leaderboard[:5]:
        if not entry.reward_earned:
            Reward.objects.create(
                user=entry.user, reward_amount=100.0, reason="Top Leaderboard Reward"
            )
            entry.reward_earned = True
            entry.save()

    # Award additional reward to users with the "Key Active User" badge for the week
    key_active_users = UserActivityBadge.objects.filter(
        badge_name="Key Active User", awarded_on=week_start
    )
    for badge in key_active_users:
        Reward.objects.create(
            user=badge.user, reward_amount=50.0, reason="Key Active User Reward"
        )


@shared_task
def update_user_streaks_daily_task():
    if is_within_trading_hours:
        update_user_streaks_daily()

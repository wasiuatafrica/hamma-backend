import datetime
import logging
from datetime import time, timedelta

import pytz
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from portfolio.market_hours import MARKET_CLOSE_AT, is_trading_time, lagos_now

from competition.models import Competition, CompetitionPortfolio, CompetitionPosition
from execution.models import DemoPortfolio, DemoPosition

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    UserDailyStreak,
    UserDailyTradeActivity,
    UserStreakRun,
    RewardAmount,
)

logger = logging.getLogger(__name__)

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
    return is_trading_time(start_offset=10)


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


@shared_task
def update_user_streaks_daily():
    """
    Daily task to update users' streaks based on trading activity.
    """
    today = timezone.now().date()
    current_time = lagos_now().time()  # was UTC, compared against a Lagos close
    market_close_time = MARKET_CLOSE_AT

    # Get all active accounts
    demo_accounts = DemoPortfolio.objects.all()
    current_competition = Competition.objects.filter(status="current").first()
    competition_accounts = CompetitionPortfolio.objects.filter(
        competition=current_competition, active=True
    )

    # Process both types of accounts
    process_accounts(
        demo_accounts, PortfolioType.DEMO, today, current_time, market_close_time
    )
    process_accounts(
        competition_accounts,
        PortfolioType.COMPETITION,
        today,
        current_time,
        market_close_time,
    )
    # demo_accounts = DemoPortfolio.objects.filter(account_id="79720109")
    # print(demo_accounts)
    # process_accounts(
    #     demo_accounts, PortfolioType.DEMO, today, current_time, market_close_time
    # )


class PortfolioType:
    """Constants for portfolio types"""

    DEMO = "demo"
    COMPETITION = "comp"

    @classmethod
    def get_portfolio_field(cls, portfolio_type):
        """Get the appropriate portfolio field name"""
        return f"{portfolio_type}_portfolio"


def process_accounts(accounts, portfolio_type, today, current_time, market_close_time):
    """
    Process streak updates for a list of accounts.

    Args:
        accounts: QuerySet of either DemoPortfolio or CompetitionPortfolio
        portfolio_type: str from PortfolioType class
        today: date object representing current date
        current_time: time object representing current time
        market_close_time: time object representing market close time
    """
    position_model = (
        DemoPosition if portfolio_type == PortfolioType.DEMO else CompetitionPosition
    )
    portfolio_field = PortfolioType.get_portfolio_field(portfolio_type)
    portfolio_id_field = f"{portfolio_field}_id"
    has_portfolio = {f"{portfolio_field}__isnull": False}

    # Three set-building queries replace 4 queries per account. Most accounts
    # have no trade today and already have a streak record, so they need none.
    traded_ids = set(
        position_model.objects.filter(open_trade_today_filter(position_model, today))
        .values_list("portfolio_id", flat=True)
        .distinct()
    )
    done_ids = set(
        UserDailyTradeActivity.objects.filter(
            trade_date=today, **has_portfolio
        ).values_list(portfolio_id_field, flat=True)
    )
    have_streak_info = set(
        UserDailyStreak.objects.filter(**has_portfolio).values_list(
            "user_id", portfolio_id_field
        )
    )
    after_close = current_time >= market_close_time

    for account in accounts.select_related("user"):
        user = account.user
        needs_streak_info = (account.user_id, account.id) not in have_streak_info
        has_open_trade = account.id in traded_ids

        # Nothing to record for this account in this run.
        if account.id in done_ids or (not has_open_trade and not after_close):
            if needs_streak_info:
                get_or_create_streak_info(user, account, portfolio_field)
            continue

        with transaction.atomic():
            streak_info = get_or_create_streak_info(user, account, portfolio_field)
            # print(f"Streak info: {streak_info.__dict__}")
            # Skip if already processed today (re-checked inside the transaction)
            if check_activity_exists(user, account, portfolio_field, today):
                continue

            if has_open_trade:
                process_trading_day(user, account, portfolio_field, streak_info, today)
            else:
                reset_streak(user, account, portfolio_field, streak_info)


def open_trade_today_filter(position_model, today):
    """Positions that count as a trade opened today."""
    return Q(created__date=today, order_type="market") | Q(
        status=position_model.OPEN, order_type="limit", updated__date=today
    )


def check_open_trades(account, position_model, today):
    """Check if account has open trades today."""
    return (
        position_model.objects.filter(portfolio=account)
        .filter(open_trade_today_filter(position_model, today))
        .exists()
    )


def get_or_create_streak_info(user, account, portfolio_field):
    """Get or create streak info for user and account."""
    kwargs = {"user": user, portfolio_field: account}
    streak_info, _ = UserDailyStreak.objects.get_or_create(**kwargs)
    return streak_info


def check_activity_exists(user, account, portfolio_field, today):
    """Check if trading activity already exists for today."""
    kwargs = {"user": user, "trade_date": today, portfolio_field: account}
    return UserDailyTradeActivity.objects.filter(**kwargs).exists()


def get_active_streak_run(user, account, portfolio_field):
    """Get active streak run for user and account."""
    kwargs = {"user": user, "is_active": True, portfolio_field: account}
    return UserStreakRun.objects.filter(**kwargs).first()


def process_trading_day(user, account, portfolio_field, streak_info, today):
    """Process a day with trading activity."""
    active_streak_run = get_active_streak_run(user, account, portfolio_field)
    # print(active_streak_run.__dict__, "this is the active run")

    if active_streak_run:
        # print("here1")
        last_trade_date = get_last_trade_date(
            user, active_streak_run, account, portfolio_field
        )
        # print(last_trade_date, "this is the last trade date")
        previous_trading_day = get_previous_trading_day(today)
        # print(previous_trading_day, "this is the previous trading day")

        if last_trade_date and last_trade_date.trade_date == previous_trading_day:
            create_daily_activity(
                user, active_streak_run, today, account, portfolio_field
            )
            streak_info.update_streak(is_new_run=False)
        else:
            # Start new streak
            active_streak_run.end_streak()
            new_streak_run = create_new_streak_run(
                user, today, account, portfolio_field
            )
            create_daily_activity(user, new_streak_run, today, account, portfolio_field)
            streak_info.update_streak(is_new_run=True)
    else:
        # Start new streak
        # print("here2")
        new_streak_run = create_new_streak_run(user, today, account, portfolio_field)
        # print(new_streak_run.__dict__, "this is the new run")
        create_daily_activity(user, new_streak_run, today, account, portfolio_field)
        streak_info.update_streak(is_new_run=True)


def get_last_trade_date(user, active_streak_run, account, portfolio_field):
    """Get the last trade date for the current streak."""
    kwargs = {"user": user, "streak_run": active_streak_run, portfolio_field: account}
    return (
        UserDailyTradeActivity.objects.filter(**kwargs).order_by("-trade_date").first()
    )


def create_new_streak_run(user, start_date, account, portfolio_field):
    """Create a new streak run."""
    kwargs = {"user": user, "start_date": start_date, portfolio_field: account}
    return UserStreakRun.objects.create(**kwargs)


def create_daily_activity(user, streak_run, trade_date, account, portfolio_field):
    """Create daily trade activity record."""
    kwargs = {
        "user": user,
        "streak_run": streak_run,
        "trade_date": trade_date,
        portfolio_field: account,
    }
    return UserDailyTradeActivity.objects.create(**kwargs)


def reset_streak(user, account, portfolio_field, streak_info):
    """Reset streak for user."""
    active_streak_run = get_active_streak_run(user, account, portfolio_field)
    if active_streak_run:
        active_streak_run.end_streak()
    streak_info.reset_streak()
    # start another streak run
    # UserStreakRun.objects.create(
    #     user=user, previous_streak=active_streak_run, demo_portfolio=account
    # )


@shared_task
def update_user_streaks_daily_task():
    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)

    if is_trading_time(current_time_lagos, start_offset=5, end_offset=5):
        # logger.info("Updating user streaks during trading hours")
        update_user_streaks_daily()
    else:
        # logger.info(f"Streak checking is outside trading hours: {current_time_lagos}")
        pass

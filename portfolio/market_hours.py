"""
NGX trading hours (Africa/Lagos), weekdays except MarketHoliday dates.

    09:00-09:25  pre-open            09:25-09:30  pre-open order imbalance
    09:30-15:50  continuous trading  <- the market is "open" (market orders, TP/SL, alerts)
    15:50-15:55  pre-close           15:55-16:00  pre-close order imbalance
    16:00        market close

Every trading-hours check in the app goes through this module.
"""

from datetime import date, datetime, time, timedelta

import pytz

LAGOS_TZ = pytz.timezone("Africa/Lagos")
PRE_OPEN_AT = time(9, 0)
OPENS_AT = time(9, 30)  # continuous trading starts
CLOSES_AT = time(15, 50)  # continuous trading ends
MARKET_CLOSE_AT = time(16, 0)  # official close, after the closing auction


def lagos_now(now=None):
    return (now or datetime.now(LAGOS_TZ)).astimezone(LAGOS_TZ)


def shift(at, minutes):
    """time `at` moved by `minutes` (same day)."""
    return (datetime.combine(date.today(), at) + timedelta(minutes=minutes)).time()


def _holidays_from(day):
    from .models import MarketHoliday

    return dict(
        MarketHoliday.objects.filter(
            date__gte=day, date__lte=day + timedelta(days=30)
        ).values_list("date", "name")
    )


def is_trading_day(day):
    from .models import MarketHoliday

    return day.weekday() < 5 and not MarketHoliday.objects.filter(date=day).exists()


def is_trading_time(now=None, start_offset=0, end_offset=0):
    """
    True during continuous trading on a trading day. Offsets (minutes) widen or
    narrow the window, e.g. start_offset=2 waits for the first prices of the day.
    """
    now = lagos_now(now)
    start = shift(OPENS_AT, start_offset)
    end = shift(CLOSES_AT, end_offset)
    return start <= now.time() <= end and is_trading_day(now.date())


def session_end_today(now=None):
    """Datetime (Lagos) when continuous trading ends today; day orders expire then."""
    now = lagos_now(now)
    return LAGOS_TZ.localize(datetime.combine(now.date(), CLOSES_AT))


def market_status(now=None):
    now = lagos_now(now)
    today = now.date()
    holidays = _holidays_from(today)
    t = now.time()

    if now.weekday() >= 5:
        reason = "weekend"
    elif today in holidays:
        reason = "holiday"
    elif t < PRE_OPEN_AT:
        reason = "before_open"
    elif t < OPENS_AT:
        reason = "pre_open"
    elif t <= CLOSES_AT:
        reason = None
    elif t < MARKET_CLOSE_AT:
        reason = "pre_close"
    else:
        reason = "after_close"

    next_open = None
    if reason is not None:
        day = today if reason in ("before_open", "pre_open") else today + timedelta(days=1)
        for _ in range(30):
            if day.weekday() < 5 and day not in holidays:
                next_open = LAGOS_TZ.localize(datetime.combine(day, OPENS_AT))
                break
            day += timedelta(days=1)

    return {
        "is_open": reason is None,
        "reason": reason,
        "session": {
            None: "continuous",
            "pre_open": "pre_open",
            "pre_close": "pre_close",
        }.get(reason, "closed"),
        "holiday_name": holidays.get(today) if reason == "holiday" else None,
        "now": now.isoformat(),
        "opens_at": OPENS_AT.strftime("%H:%M"),
        "closes_at": CLOSES_AT.strftime("%H:%M"),
        "market_close_at": MARKET_CLOSE_AT.strftime("%H:%M"),
        "next_open": next_open.isoformat() if next_open else None,
    }

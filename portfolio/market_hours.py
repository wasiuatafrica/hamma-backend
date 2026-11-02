"""NGX trading session: weekdays 10:00-14:30 Africa/Lagos, excluding MarketHoliday dates."""

from datetime import datetime, time, timedelta

import pytz

LAGOS_TZ = pytz.timezone("Africa/Lagos")
OPENS_AT = time(10, 0)
CLOSES_AT = time(14, 30)


def _holidays_from(day):
    from .models import MarketHoliday

    return dict(
        MarketHoliday.objects.filter(
            date__gte=day, date__lte=day + timedelta(days=30)
        ).values_list("date", "name")
    )


def market_status(now=None):
    now = (now or datetime.now(LAGOS_TZ)).astimezone(LAGOS_TZ)
    today = now.date()
    holidays = _holidays_from(today)

    if now.weekday() >= 5:
        reason = "weekend"
    elif today in holidays:
        reason = "holiday"
    elif now.time() < OPENS_AT:
        reason = "before_open"
    elif now.time() > CLOSES_AT:
        reason = "after_close"
    else:
        reason = None

    next_open = None
    if reason is not None:
        day = today if reason == "before_open" else today + timedelta(days=1)
        for _ in range(30):
            if day.weekday() < 5 and day not in holidays:
                next_open = LAGOS_TZ.localize(datetime.combine(day, OPENS_AT))
                break
            day += timedelta(days=1)

    return {
        "is_open": reason is None,
        "reason": reason,
        "holiday_name": holidays.get(today) if reason == "holiday" else None,
        "now": now.isoformat(),
        "opens_at": OPENS_AT.strftime("%H:%M"),
        "closes_at": CLOSES_AT.strftime("%H:%M"),
        "next_open": next_open.isoformat() if next_open else None,
    }

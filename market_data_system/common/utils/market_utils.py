from datetime import datetime, time
import pytz

from common.utils.config import settings
from common.logging.logger import get_logger

logger = get_logger(__name__)


def is_market_open():
    """Check if the market is currently open."""
    lagos_timezone = pytz.timezone(settings.timezone)
    current_time_lagos = datetime.now(lagos_timezone).time()
    today_weekday = datetime.now(lagos_timezone).weekday()

    # Check if it's a weekday (Monday = 0, Sunday = 6)
    if today_weekday < 5:  # Monday to Friday
        market_open_time = time(settings.market_open_hour, settings.market_open_minute)
        market_close_time = time(
            settings.market_close_hour, settings.market_close_minute
        )

        if market_open_time <= current_time_lagos <= market_close_time:
            return True

    return False


def get_current_time_lagos():
    """Get the current time in Lagos timezone."""
    lagos_timezone = pytz.timezone(settings.timezone)
    return datetime.now(lagos_timezone)


def safe_float(value):
    """Returns a safe float value. Converts inf and NaN to None."""
    if isinstance(value, float):
        import math

        if math.isinf(value) or math.isnan(value):
            return None
    return value

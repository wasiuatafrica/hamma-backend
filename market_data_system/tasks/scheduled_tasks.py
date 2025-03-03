from datetime import datetime
import pytz

from tasks.celery_app import app
from common.utils.config import settings
from common.utils.market_utils import is_market_open, get_current_time_lagos
from common.logging.logger import get_logger
from notifications.email_service import email_service
from collectors.ngx_collector import ngx_collector
from collectors.tv_collector import tv_collector
from collectors.data_merger import data_merger
from processors.asset_classifier import asset_classifier
from processors.signal_generator import signal_generator
from processors.chart_processor import chart_processor

logger = get_logger(__name__)


@app.task
def check_system_status():
    """Check if the system is running."""
    logger.info("System status check running")
    return True


@app.task
def collect_ngx_data():
    """Collect data from NGX API."""
    return ngx_collector.run()


@app.task
def collect_tv_data():
    """Collect data from TradingView."""
    return tv_collector.run()


@app.task
def merge_data():
    """Merge NGX and TradingView data."""
    return data_merger.run()


@app.task
def classify_assets():
    """Classify assets based on metrics."""
    return asset_classifier.run()


@app.task
def generate_signals():
    """Generate trading signals."""
    return signal_generator.run()


@app.task
def update_daily_charts():
    """Update daily chart data."""
    return chart_processor.update_daily_charts()


@app.task
def update_minute_charts():
    """Update minute chart data."""
    return chart_processor.update_minute_charts()


@app.task
def send_startup_notification():
    """Send system startup notification."""
    return email_service.send_system_startup_notification()


@app.task
def send_shutdown_notification():
    """Send system shutdown notification."""
    return email_service.send_system_shutdown_notification()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Set up periodic tasks for the market data system."""
    # System status check (every 5 minutes)
    sender.add_periodic_task(300.0, check_system_status.s(), name="check system status")

    # Market hours tasks (run only if market is open)
    # NGX data collection (every minute)
    sender.add_periodic_task(60.0, collect_ngx_data.s(), name="collect NGX data")

    # TradingView data collection (every 30 minutes)
    sender.add_periodic_task(
        1800.0, collect_tv_data.s(), name="collect TradingView data"
    )

    # Data merging (every minute)
    sender.add_periodic_task(60.0, merge_data.s(), name="merge data")

    # Asset classification (every hour)
    sender.add_periodic_task(3600.0, classify_assets.s(), name="classify assets")

    # Signal generation (every hour)
    sender.add_periodic_task(3600.0, generate_signals.s(), name="generate signals")

    # After-market tasks (run once at specific times)
    # Daily chart update at 15:00 WAT
    sender.add_periodic_task(
        sender.crontab(hour=15, minute=0, day_of_week="1-5"),
        update_daily_charts.s(),
        name="update daily charts",
    )

    # Minute chart update at 15:30 WAT
    sender.add_periodic_task(
        sender.crontab(hour=15, minute=30, day_of_week="1-5"),
        update_minute_charts.s(),
        name="update minute charts",
    )

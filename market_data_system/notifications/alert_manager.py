import traceback
from datetime import datetime
import pytz

from common.utils.config import settings
from common.logging.logger import get_logger
from notifications.email_service import email_service
from common.db.mongodb import mongodb

logger = get_logger(__name__)


class AlertManager:
    def __init__(self):
        self.email_service = email_service

    def handle_error(self, component, error_message, exception=None, data=None):
        """Handle an error by logging it and sending notifications."""
        stack_trace = None
        if exception:
            stack_trace = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )

        # Log to MongoDB
        mongodb.log_error(component, error_message, stack_trace, data)

        # Send email notification
        self.email_service.send_error_notification(
            component, error_message, stack_trace
        )

    def handle_new_symbol(self, symbol):
        """Handle the discovery of a new symbol."""
        logger.info(f"New symbol detected: {symbol}")

        # Log to MongoDB
        mongodb.update_symbol_status(
            symbol=symbol, is_active=True, message="Newly discovered symbol"
        )

        # Send email notification
        self.email_service.send_new_symbol_notification(symbol)

    def handle_inactive_symbol(self, symbol, reason):
        """Handle a symbol becoming inactive."""
        logger.info(f"Symbol inactive: {symbol} - {reason}")

        # Log to MongoDB
        mongodb.update_symbol_status(symbol=symbol, is_active=False, message=reason)

        # Send email notification
        self.email_service.send_inactive_symbol_notification(symbol, reason)

    def send_process_completion(self, process_name, details=None):
        """Send a notification that a process has completed."""
        logger.info(f"Process complete: {process_name}")

        # Send email notification
        self.email_service.send_process_completion_notification(process_name, details)


# Create a singleton instance
alert_manager = AlertManager()

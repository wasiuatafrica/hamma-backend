from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import datetime
import pytz

from common.utils.config import settings
from common.logging.logger import get_logger

logger = get_logger(__name__)


class MongoDB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance

    def _initialize_connection(self):
        """Initialize MongoDB connection."""
        try:
            self.client = MongoClient(
                settings.mongo_url,
                serverSelectionTimeoutMS=settings.mongo_timeout,
                tls=True,
                tlsAllowInvalidCertificates=True,
                maxPoolSize=20,
            )
            # Test the connection
            self.client.admin.command("ismaster")
            logger.info("MongoDB connection established successfully")

            # Initialize database references
            self.db_live = self.client["livelake3_test"]
            self.db_stock_prices = self.client["stock_prices_test"]
            self.db_chart_1d = self.client["chartdata_1D_test"]
            self.db_chart_5m = self.client["chartdata_5_test"]
            self.db_risk = self.client["stock_classification_test"]
            self.db_signals = self.client["trade_signals_test"]
            self.db_cap = self.client["ngxlistedcompanies_test"]

            # Initialize collection references for system status
            self.db_system = self.client["system_status_test"]
            self.system_status_collection = self.db_system["service_status_test"]
            self.symbol_status_collection = self.db_system["symbol_status_test"]
            self.error_log_collection = self.db_system["error_logs_test"]
            self.notification_log_collection = self.db_system["notification_logs_test"]
            self.performance_metrics_collection = self.db_system[
                "performance_metrics_test"
            ]

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def get_today_collection_name(self):
        """Get the collection name for today's data."""
        lagos_tz = pytz.timezone(settings.timezone)
        today_str = datetime.datetime.now(lagos_tz).strftime("%Y-%m-%d")
        return today_str

    def log_error(self, component, error_message, stack_trace=None, data=None):
        """Log an error to the error_log_collection."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.datetime.now(lagos_tz)

        error_log = {
            "timestamp": now,
            "component": component,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "data": data,
        }

        self.error_log_collection.insert_one(error_log)
        logger.error(f"{component}: {error_message}")

    def update_service_status(self, service_name, status, message=None):
        """Update the status of a service."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.datetime.now(lagos_tz)

        self.system_status_collection.update_one(
            {"service": service_name},
            {"$set": {"status": status, "last_updated": now, "message": message or ""}},
            upsert=True,
        )

    def log_notification(self, notification_type, recipient, subject, body):
        """Log a notification to the notification_log_collection."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.datetime.now(lagos_tz)

        notification_log = {
            "timestamp": now,
            "type": notification_type,
            "recipient": recipient,
            "subject": subject,
            "body": body,
        }

        self.notification_log_collection.insert_one(notification_log)

    def update_symbol_status(self, symbol, is_active, last_seen=None, message=None):
        """Update the status of a symbol."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.datetime.now(lagos_tz)

        self.symbol_status_collection.update_one(
            {"symbol": symbol},
            {
                "$set": {
                    "is_active": is_active,
                    "last_updated": now,
                    "last_seen": last_seen or now if is_active else None,
                    "message": message or "",
                }
            },
            upsert=True,
        )

    def record_performance_metric(
        self, component, operation, duration, data_points=None
    ):
        """Record a performance metric."""
        lagos_tz = pytz.timezone(settings.timezone)
        now = datetime.datetime.now(lagos_tz)

        metric = {
            "timestamp": now,
            "component": component,
            "operation": operation,
            "duration_seconds": duration,
            "data_points": data_points,
        }

        self.performance_metrics_collection.insert_one(metric)


# Create a singleton instance
mongodb = MongoDB()

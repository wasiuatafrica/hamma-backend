import requests
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
import time
import traceback

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb
from common.db.postgres import postgres_db
from notifications.alert_manager import alert_manager
from common.utils.market_utils import is_market_open, get_current_time_lagos

logger = get_logger(__name__)


class NGXDataCollector:
    def __init__(self):
        self.token = settings.ngx_token
        self.db = mongodb
        self.active_symbols = set()
        self.update_active_symbols()

    def update_active_symbols(self):
        """Update the list of active symbols from the PostgreSQL database."""
        try:
            stocks = postgres_db.get_active_stocks()
            self.active_symbols = {stock.symbol for stock in stocks}
            logger.info(
                f"Updated active symbols list: {len(self.active_symbols)} symbols"
            )
        except Exception as e:
            logger.error(f"Failed to update active symbols: {e}")
            alert_manager.handle_error(
                "NGXDataCollector", "Failed to update active symbols", e
            )

    def get_live_data(self):
        """Fetch live data from NGX API."""
        start_time = time.time()

        try:
            # Update service status
            self.db.update_service_status(
                "NGXDataCollector", "running", "Fetching data from NGX API"
            )

            url = f"https://marketdataapiv3.ngxgroup.com/v3/api/price/pricesRT.json?_t={self.token}"
            response = requests.get(url, timeout=30)

            if not response.ok:
                error_msg = (
                    f"NGX API request failed with status code: {response.status_code}"
                )
                logger.error(error_msg)
                self.db.update_service_status("NGXDataCollector", "error", error_msg)
                alert_manager.handle_error(
                    "NGXDataCollector",
                    error_msg,
                    data={"status_code": response.status_code},
                )
                return None

            symbol_list = response.json()

            lagos_now = get_current_time_lagos()

            # Filter equity data for current day
            equity = []
            for data in symbol_list:
                if data.get("Asset") == "EQUITY":
                    try:
                        timestamp_str = data.get("Timestamp", "")
                        if not timestamp_str:
                            continue

                        # Split the timestamp string into date and time parts
                        date_part, time_part = timestamp_str.split("T")
                        data_date = datetime.strptime(date_part, "%Y-%m-%d").date()

                        if data_date == lagos_now.date():
                            equity.append(data)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error processing data: {data}, error: {e}")

            # Track received symbols
            received_symbols = set()

            # Process equity data
            combined = {}
            if equity:
                for data in equity:
                    symbol = data["Symbol"].split(" ")[0]
                    received_symbols.add(symbol)

                    try:
                        # Handle datetime
                        date_part, time_part = data["Timestamp"].split("T")
                        time_part = time_part.split("+")[0].split("-")[0].split(".")[0]
                        formatted_datetime = f"{date_part} {time_part}"
                        current_time = datetime.strptime(
                            formatted_datetime, "%Y-%m-%d %H:%M:%S"
                        )

                        # Create data dictionary
                        data1 = {
                            "datetime": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "open": data["Open"],
                            "high": (
                                data["High"]
                                if data["High"]
                                else round(data["Open"] * 1.01, 2)
                            ),
                            "low": (
                                data["Low"]
                                if data["Low"]
                                else round(data["Close"] * 0.99, 2)
                            ),
                            "close": data["Close"],
                            "volume": data["Volume"],
                            "symbol": symbol,
                            "change": data["Change"],
                            "percent": data["PerChange"],
                        }

                        combined[symbol] = data1
                    except Exception as e:
                        logger.error(f"Error processing data for symbol {symbol}: {e}")

                # Check for new symbols
                new_symbols = received_symbols - self.active_symbols
                for symbol in new_symbols:
                    alert_manager.handle_new_symbol(symbol)

                # Check for inactive symbols
                missing_symbols = self.active_symbols - received_symbols
                for symbol in missing_symbols:
                    alert_manager.handle_inactive_symbol(
                        symbol, "Not present in NGX data feed"
                    )
                    # Update PostgreSQL
                    postgres_db.update_stock_active_status(symbol, False)

                # Save data to MongoDB
                if combined:
                    self.write_to_mongodb(combined)

                    end_time = time.time()
                    duration = end_time - start_time
                    self.db.record_performance_metric(
                        "NGXDataCollector", "get_live_data", duration, len(combined)
                    )

                    self.db.update_service_status(
                        "NGXDataCollector",
                        "success",
                        f"Processed {len(combined)} symbols in {duration:.2f} seconds",
                    )

                    return combined
                else:
                    logger.warning("No data to save after processing")
                    self.db.update_service_status(
                        "NGXDataCollector",
                        "warning",
                        "No data to save after processing",
                    )
                    return None
            else:
                logger.warning("No equity data found for the current date")
                self.db.update_service_status(
                    "NGXDataCollector",
                    "warning",
                    "No equity data found for the current date",
                )
                return None

        except Exception as e:
            error_msg = f"Error in get_live_data: {str(e)}"
            logger.error(error_msg)
            self.db.update_service_status("NGXDataCollector", "error", error_msg)
            alert_manager.handle_error("NGXDataCollector", "Failed to get live data", e)
            return None

    def write_to_mongodb(self, data):
        """Write data to MongoDB collections."""
        try:
            # Get collection references
            collection = self.db.db_live["live_price_combined"]
            today_str = self.db.get_today_collection_name()
            collection_today = self.db.db_live[today_str]

            # Insert data into both collections
            collection.insert_one(data)
            collection_today.insert_one(data)

            logger.info(f"Successfully wrote {len(data)} symbols to MongoDB")
            return True
        except Exception as e:
            error_msg = f"Failed to write to MongoDB: {str(e)}"
            logger.error(error_msg)
            alert_manager.handle_error(
                "NGXDataCollector", "Failed to write to MongoDB", e, data
            )
            return False

    def run(self):
        """Run the data collection process if market is open."""
        if is_market_open():
            logger.info("Market is open, collecting NGX data")
            return self.get_live_data()
        else:
            logger.info("Market is closed, skipping NGX data collection")
            self.db.update_service_status(
                "NGXDataCollector", "idle", "Market is closed"
            )
            return None


# Create a singleton instance
ngx_collector = NGXDataCollector()

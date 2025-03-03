import pandas as pd
import time
from datetime import datetime

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb
from notifications.alert_manager import alert_manager
from common.utils.market_utils import is_market_open, get_current_time_lagos, safe_float

logger = get_logger(__name__)


class DataMerger:
    def __init__(self):
        self.db = mongodb

    def get_price(self):
        """Get the last item from "stock_prices" collection."""
        try:
            collection = self.db.db_stock_prices["price_combined_test"]
            last_item = collection.find_one(sort=[("_id", -1)])
            return last_item
        except Exception as e:
            logger.error(f"Error getting price data: {e}")
            return None

    def get_last_live(self):
        """Get the last item from "live_price_combined" collection."""
        try:
            collection = self.db.db_live["live_price_combined_test"]
            last_item = collection.find_one(sort=[("_id", -1)])
            return last_item
        except Exception as e:
            logger.error(f"Error getting last live data: {e}")
            return None

    def merge_data(self):
        """Merge volatile data with live data."""
        start_time = time.time()

        try:
            self.db.update_service_status("DataMerger", "running", "Merging data")

            # Get the data to merge
            volatile_data = self.get_price()
            if not volatile_data:
                logger.warning("No volatile data available for merging")
                self.db.update_service_status(
                    "DataMerger", "warning", "No volatile data available"
                )
                return None

            live_data = self.get_last_live()
            if not live_data:
                logger.warning("No live data available for merging")
                self.db.update_service_status(
                    "DataMerger", "warning", "No live data available"
                )
                return None

            logger.info("Got volatile and live data for merging")

            # Combined data storage
            combined = {}

            # Process each symbol in live_data except '_id'
            for symbol, data in live_data.items():
                if symbol != "_id":
                    data2 = volatile_data.get(symbol, None)
                    if data2:
                        new_data = {
                            "datetime": data["datetime"],
                            "symbol": symbol,
                            "open": data["open"],
                            "high": data["high"],
                            "low": data["low"],
                            "close": data["close"],
                            "volume": data["volume"],
                            "change": data["change"],
                            "percentage_change": data["percent"],
                            "current_price": data["close"],
                            "volatility": safe_float(data2.get("volatility", None)),
                            "momentum": safe_float(data2.get("momentum", None)),
                            "momentum_change": safe_float(
                                data2.get("momentum_change", None)
                            ),
                            "volume_momentum": safe_float(
                                data2.get("volume_momentum", None)
                            ),
                            "volume_momentum_change": safe_float(
                                data2.get("volume_momentum_change", None)
                            ),
                            "volatility_1week": safe_float(
                                data2.get("volatility_1week", None)
                            ),
                            "momentum_1week": safe_float(
                                data2.get("momentum_1week", None)
                            ),
                            "momentum_change_1week": safe_float(
                                data2.get("momentum_change_1week", None)
                            ),
                            "volume_momentum_1week": safe_float(
                                data2.get("volume_momentum_1week", None)
                            ),
                            "volume_momentum_change_1week": safe_float(
                                data2.get("volume_momentum_change_1week", None)
                            ),
                            "volatility_1year": safe_float(
                                data2.get("volatility_1year", None)
                            ),
                            "momentum_1year": safe_float(
                                data2.get("momentum_1year", None)
                            ),
                            "momentum_change_1year": safe_float(
                                data2.get("momentum_change_1year", None)
                            ),
                            "volume_momentum_1year": safe_float(
                                data2.get("volume_momentum_1year", None)
                            ),
                            "volume_momentum_change_1year": safe_float(
                                data2.get("volume_momentum_change_1year", None)
                            ),
                            "volatility_ytd": safe_float(
                                data2.get("volatility_ytd", None)
                            ),
                            "momentum_ytd": safe_float(data2.get("momentum_ytd", None)),
                            "momentum_change_ytd": safe_float(
                                data2.get("momentum_change_ytd", None)
                            ),
                            "volume_momentum_ytd": safe_float(
                                data2.get("volume_momentum_ytd", None)
                            ),
                            "volume_momentum_change_ytd": safe_float(
                                data2.get("volume_momentum_change_ytd", None)
                            ),
                            "volatility_24hr": safe_float(
                                data2.get("volatility_24hr", None)
                            ),
                            "momentum_24hr": safe_float(
                                data2.get("momentum_24hr", None)
                            ),
                            "momentum_change_24hr": safe_float(
                                data2.get("momentum_change_24hr", None)
                            ),
                            "volume_momentum_24hr": safe_float(
                                data2.get("volume_momentum_24hr", None)
                            ),
                            "volume_momentum_change_24hr": safe_float(
                                data2.get("volume_momentum_change_24hr", None)
                            ),
                            "market_cap": safe_float(data2.get("market_cap", 0)),
                        }
                    else:
                        new_data = {
                            "datetime": data["datetime"],
                            "symbol": symbol,
                            "open": data["open"],
                            "high": data["high"],
                            "low": data["low"],
                            "close": data["close"],
                            "volume": data["volume"],
                            "change": data["change"],
                            "percentage_change": data["percent"],
                            "current_price": data["close"],
                            "volatility": 0,
                            "momentum": 0,
                            "momentum_change": 0,
                            "volume_momentum": 0,
                            "volume_momentum_change": 0,
                            "volatility_1week": 0,
                            "momentum_1week": 0,
                            "momentum_change_1week": 0,
                            "volume_momentum_1week": 0,
                            "volume_momentum_change_1week": 0,
                            "volatility_1year": 0,
                            "momentum_1year": 0,
                            "momentum_change_1year": 0,
                            "volume_momentum_1year": 0,
                            "volume_momentum_change_1year": 0,
                            "volatility_ytd": 0,
                            "momentum_ytd": 0,
                            "momentum_change_ytd": 0,
                            "volume_momentum_ytd": 0,
                            "volume_momentum_change_ytd": 0,
                            "volatility_24hr": 0,
                            "momentum_24hr": 0,
                            "momentum_change_24hr": 0,
                            "volume_momentum_24hr": 0,
                            "volume_momentum_change_24hr": 0,
                            "market_cap": 0,
                        }
                    combined[symbol] = new_data

            # Write merged data to MongoDB
            if combined:
                collection_merged = self.db.db_live["merged_live_price_test"]
                collection_merged.insert_one(combined)
                logger.info(
                    f"Successfully merged and wrote data for {len(combined)} symbols"
                )

                end_time = time.time()
                duration = end_time - start_time

                self.db.record_performance_metric(
                    "DataMerger", "merge_data", duration, len(combined)
                )

                self.db.update_service_status(
                    "DataMerger",
                    "success",
                    f"Merged {len(combined)} symbols in {duration:.2f} seconds",
                )

                return combined
            else:
                logger.warning("No data to merge")
                self.db.update_service_status(
                    "DataMerger", "warning", "No data to merge"
                )
                return None

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"Error merging data: {str(e)}"
            logger.error(error_msg)

            self.db.update_service_status("DataMerger", "error", error_msg)
            alert_manager.handle_error("DataMerger", "Failed to merge data", e)

            return None

    def run(self):
        """Run the data merging process if market is open."""
        if is_market_open():
            logger.info("Market is open, merging data")
            return self.merge_data()
        else:
            logger.info("Market is closed, skipping data merging")
            self.db.update_service_status("DataMerger", "idle", "Market is closed")
            return None


# Create a singleton instance
data_merger = DataMerger()

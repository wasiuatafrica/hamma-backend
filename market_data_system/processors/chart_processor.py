import pandas as pd
from datetime import datetime
import pytz
import time

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb
from common.db.postgres import postgres_db
from notifications.alert_manager import alert_manager

logger = get_logger(__name__)


class ChartProcessor:
    def __init__(self):
        self.db = mongodb

    def last_data(self, last_item, symbol):
        """Extract last data for a specific symbol from merged data."""
        try:
            if symbol not in last_item:
                return None

            data = last_item[symbol]

            # Convert datetime string to datetime object
            dt = datetime.strptime(data["datetime"], "%Y-%m-%d %H:%M:%S")
            timestamp = dt.timestamp()

            df = pd.DataFrame(
                {
                    "timestamp": [timestamp],
                    "open": [data["open"]],
                    "high": [data["high"]],
                    "low": [data["low"]],
                    "close": [data["close"]],
                    "volume": [data["volume"]],
                }
            )

            return df
        except Exception as e:
            logger.error(f"Error extracting data for {symbol}: {e}")
            return None

    def update_document(self, symbol, dbase, new_data):
        """Update a document in MongoDB with new data."""
        try:
            db = self.db.client[dbase]
            if symbol not in db.list_collection_names():
                db.create_collection(symbol)

            collection = db[symbol]

            # Find the document to update
            existing_document = collection.find_one()

            if existing_document:
                id = existing_document["_id"]
                # Update each list in the document with new values
                for key in ["t", "o", "h", "l", "c", "v"]:
                    if key in new_data:
                        if key in existing_document:
                            existing_document[key].extend(new_data[key])
                        else:
                            existing_document[key] = new_data[key]

                # Update the document in the collection
                collection.update_one({"_id": id}, {"$set": existing_document})
                logger.info(f"Updated {symbol} in {dbase}")
                return True
            else:
                # If no existing document found, insert the new data
                logger.info(f"Creating new document for {symbol} in {dbase}")
                collection.insert_one(new_data)
                return True
        except Exception as e:
            logger.error(f"Error updating document for {symbol} in {dbase}: {e}")
            return False

    def update_daily_charts(self):
        """Update daily chart data after market hours."""
        start_time = time.time()

        try:
            self.db.update_service_status(
                "ChartProcessor", "running", "Updating daily charts"
            )

            # Get active symbols
            stocks = postgres_db.get_active_stocks()
            symbols = [stock.symbol for stock in stocks]

            # Get the latest merged data
            last_item = self.db.db_live["merged_live_price"].find_one(
                sort=[("_id", -1)]
            )

            if not last_item:
                logger.warning("No merged data available for chart update")
                self.db.update_service_status(
                    "ChartProcessor", "warning", "No merged data available"
                )
                return None

            if "_id" in last_item:
                last_item.pop("_id")

            updated_symbols = []
            failed_symbols = []

            lagos_tz = pytz.timezone(settings.timezone)
            today = datetime.now(lagos_tz)

            for symbol in symbols:
                try:
                    df = self.last_data(last_item, symbol)
                    if df is None or df.empty:
                        logger.warning(f"No data available for {symbol} today")
                        continue

                    t = df["timestamp"].tolist()[-1]
                    o = df["open"].tolist()[-1]
                    h = df["high"].tolist()[-1]
                    l = df["low"].tolist()[-1]
                    c = df["close"].tolist()[-1]
                    v = df["volume"].tolist()[-1]

                    new_data = {
                        "t": [t],
                        "o": [o],
                        "h": [h],
                        "l": [l],
                        "c": [c],
                        "v": [v],
                    }

                    # Update 1D chart data
                    if self.update_document(symbol, "chartdata_1D", new_data):
                        updated_symbols.append(symbol)
                    else:
                        failed_symbols.append(symbol)

                    # Update 1W chart data on Fridays
                    if today.weekday() == 4:  # Friday
                        self.update_document(symbol, "chartdata_1W", new_data)
                        logger.info(f"Updated weekly chart for {symbol}")

                except Exception as e:
                    logger.error(f"Error updating charts for {symbol}: {e}")
                    failed_symbols.append(symbol)

            end_time = time.time()
            duration = end_time - start_time

            self.db.record_performance_metric(
                "ChartProcessor", "update_daily_charts", duration, len(updated_symbols)
            )

            status_message = (
                f"Updated {len(updated_symbols)} charts in {duration:.2f} seconds"
            )
            if failed_symbols:
                status_message += f" ({len(failed_symbols)} symbols failed)"

            self.db.update_service_status(
                "ChartProcessor",
                "success" if not failed_symbols else "partial_success",
                status_message,
            )

            # Send notification
            alert_manager.send_process_completion(
                "Chart Data Update",
                f"Updated {len(updated_symbols)} daily charts"
                + (", including weekly charts" if today.weekday() == 4 else ""),
            )

            if failed_symbols:
                alert_manager.handle_error(
                    "ChartProcessor",
                    f"Failed to update {len(failed_symbols)} charts",
                    data={"failed_symbols": failed_symbols},
                )

            return updated_symbols
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"Error updating daily charts: {str(e)}"
            logger.error(error_msg)

            self.db.update_service_status("ChartProcessor", "error", error_msg)
            alert_manager.handle_error(
                "ChartProcessor", "Failed to update daily charts", e
            )

            return None

    def update_minute_charts(self):
        """Update minute chart data after market hours."""
        start_time = time.time()

        try:
            self.db.update_service_status(
                "ChartProcessor", "running", "Updating minute charts"
            )

            # Get active symbols
            stocks = postgres_db.get_active_stocks()
            symbols = [stock.symbol for stock in stocks]

            # Get today's date
            lagos_tz = pytz.timezone(settings.timezone)
            today = datetime.now(lagos_tz).date()

            # Get today's collection
            today_str = today.strftime("%Y-%m-%d")
            collection_today = self.db.db_live[today_str]

            # Get all data for today
            cursor = collection_today.find().sort([("_id", 1)])
            data = list(cursor)

            if not data:
                logger.warning("No data available for minute chart update")
                self.db.update_service_status(
                    "ChartProcessor", "warning", "No data available for minute charts"
                )
                return None

            results = {symbol: [] for symbol in symbols}

            # Process each document
            for item in data:
                if "_id" in item:
                    item.pop("_id")

                for symbol in symbols:
                    if symbol in item:
                        symbol_data = item[symbol]
                        symbol_data["datetime"] = datetime.strptime(
                            symbol_data["datetime"], "%Y-%m-%d %H:%M:%S"
                        )
                        if symbol_data["datetime"].date() == today:
                            results[symbol].append(symbol_data)

            updated_symbols = []
            failed_symbols = []

            # Process each symbol's data
            for symbol, symbol_data in results.items():
                if symbol_data:
                    try:
                        df = pd.DataFrame(symbol_data)
                        df["timestamp"] = df["datetime"].apply(
                            lambda dt: dt.timestamp()
                        )
                        df_filtered = df.sort_values("timestamp")
                        df_filtered["volume_diff"] = df_filtered["volume"].diff()
                        df_filtered = df_filtered[df_filtered["volume_diff"] != 0]
                        df_filtered.dropna(inplace=True)

                        if df_filtered.empty:
                            logger.warning(f"No valid minute data for {symbol}")
                            continue

                        new_data = {
                            "t": df_filtered["timestamp"].tolist(),
                            "o": df_filtered["open"].tolist(),
                            "h": df_filtered["high"].tolist(),
                            "l": df_filtered["low"].tolist(),
                            "c": df_filtered["close"].tolist(),
                            "v": df_filtered["volume_diff"].tolist(),
                        }

                        if self.update_document(symbol, "chartdata_5", new_data):
                            updated_symbols.append(symbol)
                        else:
                            failed_symbols.append(symbol)
                    except Exception as e:
                        logger.error(f"Error processing minute data for {symbol}: {e}")
                        failed_symbols.append(symbol)

            end_time = time.time()
            duration = end_time - start_time

            self.db.record_performance_metric(
                "ChartProcessor", "update_minute_charts", duration, len(updated_symbols)
            )

            status_message = f"Updated {len(updated_symbols)} minute charts in {duration:.2f} seconds"
            if failed_symbols:
                status_message += f" ({len(failed_symbols)} symbols failed)"

            self.db.update_service_status(
                "ChartProcessor",
                "success" if not failed_symbols else "partial_success",
                status_message,
            )

            # Send notification
            alert_manager.send_process_completion(
                "Minute Chart Data Update",
                f"Updated {len(updated_symbols)} minute charts",
            )

            if failed_symbols:
                alert_manager.handle_error(
                    "ChartProcessor",
                    f"Failed to update {len(failed_symbols)} minute charts",
                    data={"failed_symbols": failed_symbols},
                )

            return updated_symbols
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"Error updating minute charts: {str(e)}"
            logger.error(error_msg)

            self.db.update_service_status("ChartProcessor", "error", error_msg)
            alert_manager.handle_error(
                "ChartProcessor", "Failed to update minute charts", e
            )

            return None


# Create a singleton instance
chart_processor = ChartProcessor()

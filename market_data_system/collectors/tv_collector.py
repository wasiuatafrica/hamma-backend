from tvDatafeed import TvDatafeed, Interval
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb
from common.db.postgres import postgres_db
from notifications.alert_manager import alert_manager
from common.utils.market_utils import is_market_open, get_current_time_lagos, safe_float

logger = get_logger(__name__)


class TradingViewDataCollector:
    def __init__(self):
        try:
            self.tv = TvDatafeed()
            self.db = mongodb
            self.active_symbols = []
            self.update_active_symbols()
            logger.info("TradingViewDataCollector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TradingViewDataCollector: {e}")
            alert_manager.handle_error(
                "TradingViewDataCollector", "Failed to initialize", e
            )

    def update_active_symbols(self):
        """Update the list of active symbols from the PostgreSQL database."""
        try:
            stocks = postgres_db.get_active_stocks()
            self.active_symbols = [stock.symbol for stock in stocks]
            logger.info(
                f"Updated active symbols list: {len(self.active_symbols)} symbols"
            )
        except Exception as e:
            logger.error(f"Failed to update active symbols: {e}")
            alert_manager.handle_error(
                "TradingViewDataCollector", "Failed to update active symbols", e
            )

    def calculate_volatility_momentum_24hr(self, symbol, data):
        """Calculate volatility and momentum metrics for the last 24 hours."""
        try:
            # Create a copy of the last 3 rows
            df = data.tail(3).copy()
            df = df.dropna(subset=["open", "close"])

            if df is None or df.empty or len(df) < 2:
                return None, None, None, None, None

            # Calculate returns using pct_change
            df["returns"] = df["close"].pct_change()

            volatility = df["returns"].std() * np.sqrt(252 / 2)

            # Use iloc for safer indexing
            start_price = df["close"].iloc[-2]
            end_price = df["close"].iloc[-1]
            momentum_change = end_price - start_price
            momentum = (momentum_change / start_price) * 100

            start_volume = df["volume"].iloc[-2]
            end_volume = df["volume"].iloc[-1]
            volume_momentum_change = end_volume - start_volume

            if start_volume == 0:
                volume_momentum = 0
            else:
                volume_momentum = (volume_momentum_change / start_volume) * 100

            return (
                round(volatility, 2),
                round(momentum, 2),
                round(momentum_change, 2),
                round(volume_momentum, 2),
                round(volume_momentum_change, 2),
            )
        except Exception as e:
            logger.error(f"Error calculating 24hr volatility for {symbol}: {e}")
            return None, None, None, None, None

    def calculate_volatility_momentum(self, data, period):
        """Calculate volatility and momentum metrics for a given period."""
        try:
            # Create a copy of the dataframe
            data = data.copy()
            now = datetime.now()

            # Ensure datetime index
            data["datetime"] = pd.to_datetime(data.index)

            if period in [30, 7]:
                filtered_data = data.tail(period).copy()
            else:
                filtered_data = data[
                    data["datetime"] >= (now - timedelta(days=period))
                ].copy()

            if len(filtered_data) < 3:
                return None, None, None, None, None

            # Handle NaN values
            filtered_data = filtered_data.fillna(method="ffill").fillna(method="bfill")

            # Calculate returns
            filtered_data["returns"] = filtered_data["close"].pct_change()
            filtered_data["returns"] = filtered_data["returns"].fillna(0)

            # Calculate annualized volatility
            volatility = filtered_data["returns"].std() * np.sqrt(252 / period)

            # Use iloc for safer indexing
            start_price = filtered_data["close"].iloc[0]
            end_price = filtered_data["close"].iloc[-1]
            momentum_change = end_price - start_price
            momentum = momentum_change / start_price * 100

            start_volume = filtered_data["volume"].iloc[0]
            end_volume = filtered_data["volume"].iloc[-1]
            volume_momentum_change = end_volume - start_volume

            # Handle potential division by zero for volume momentum calculation
            if start_volume == 0:
                volume_momentum = 0
            else:
                volume_momentum = (volume_momentum_change / start_volume) * 100

            return (
                round(volatility, 2),
                round(momentum, 2),
                round(momentum_change, 2),
                round(volume_momentum, 2),
                round(volume_momentum_change, 2),
            )
        except Exception as e:
            logger.error(f"Error calculating volatility for period {period}: {e}")
            return None, None, None, None, None

    def get_chart_data(self, symbol):
        """Get chart data for a specific symbol."""
        try:
            collection = self.db.db_chart_1d[symbol]
            symbol_data = collection.find_one(sort=[("_id", -1)])

            if not symbol_data:
                logger.warning(f"No chart data found for {symbol}")
                return None

            symbol_data.pop("_id", None)

            # Convert to DataFrame
            df = pd.DataFrame(
                {
                    "datetime": [
                        datetime.fromtimestamp(ts) for ts in symbol_data["t"][-31:]
                    ],
                    "open": symbol_data["o"][-31:],
                    "high": symbol_data["h"][-31:],
                    "low": symbol_data["l"][-31:],
                    "close": symbol_data["c"][-31:],
                    "volume": symbol_data["v"][-31:],
                }
            )

            # Calculate change and percentage change
            df["change"] = df["close"] - df["close"].shift(1)
            df["percentage_change"] = (df["change"] / df["close"].shift(1)) * 100

            df.dropna(inplace=True)
            df.set_index("datetime", inplace=True)

            return df
        except Exception as e:
            logger.error(f"Error getting chart data for {symbol}: {e}")
            return None

    def get_symbol_cap(self, symbol):
        """Get market cap data for a symbol."""
        try:
            collection = self.db.db_cap[symbol]
            data = collection.find_one()
            if data:
                return data.get("SharesOutstanding", 0)
            return 0
        except Exception as e:
            logger.warning(f"Error getting market cap for {symbol}: {e}")
            return 0

    def process_symbol(self, symbol):
        """Process a single symbol to calculate metrics."""
        try:
            data3 = {"symbol": symbol}

            # Get 1-year data
            data_full = self.tv.get_hist(
                symbol=symbol,
                exchange="NSENG",
                interval=Interval.in_daily,
                n_bars=365,
            )

            if data_full is not None:
                # Calculate 1-year volatility and momentum
                vol_mom_1year = self.calculate_volatility_momentum(data_full, 365)

                # Calculate year-to-date volatility and momentum
                current_year = datetime.now().year
                data_ytd = data_full[data_full.index.year == current_year]
                vol_mom_ytd = self.calculate_volatility_momentum(
                    data_ytd, len(data_ytd)
                )

                data3["volatility_1year"] = vol_mom_1year[0] if vol_mom_1year else None
                data3["momentum_1year"] = vol_mom_1year[1] if vol_mom_1year else None
                data3["momentum_change_1year"] = (
                    vol_mom_1year[2] if vol_mom_1year else None
                )
                data3["volume_momentum_1year"] = (
                    vol_mom_1year[3] if vol_mom_1year else None
                )
                data3["volume_momentum_change_1year"] = (
                    vol_mom_1year[4] if vol_mom_1year else None
                )

                data3["volatility_ytd"] = vol_mom_ytd[0] if vol_mom_ytd else None
                data3["momentum_ytd"] = vol_mom_ytd[1] if vol_mom_ytd else None
                data3["momentum_change_ytd"] = vol_mom_ytd[2] if vol_mom_ytd else None
                data3["volume_momentum_ytd"] = vol_mom_ytd[3] if vol_mom_ytd else None
                data3["volume_momentum_change_ytd"] = (
                    vol_mom_ytd[4] if vol_mom_ytd else None
                )
            else:
                data3["volatility_1year"] = None
                data3["momentum_1year"] = None
                data3["momentum_change_1year"] = None
                data3["volume_momentum_1year"] = None
                data3["volume_momentum_change_1year"] = None
                data3["volatility_ytd"] = None
                data3["momentum_ytd"] = None
                data3["momentum_change_ytd"] = None
                data3["volume_momentum_ytd"] = None
                data3["volume_momentum_change_ytd"] = None

            # Get daily chart data
            new_data = self.get_chart_data(symbol)
            if new_data is not None:
                # Calculate volatility and momentum for different periods
                vol_mom_1week = self.calculate_volatility_momentum(new_data, 7)
                vol_mom_1month = self.calculate_volatility_momentum(new_data, 30)
                vol_mom_24hr = self.calculate_volatility_momentum_24hr(symbol, new_data)

                data3["volatility_1week"] = vol_mom_1week[0] if vol_mom_1week else None
                data3["momentum_1week"] = vol_mom_1week[1] if vol_mom_1week else None
                data3["momentum_change_1week"] = (
                    vol_mom_1week[2] if vol_mom_1week else None
                )
                data3["volume_momentum_1week"] = (
                    vol_mom_1week[3] if vol_mom_1week else None
                )
                data3["volume_momentum_change_1week"] = (
                    vol_mom_1week[4] if vol_mom_1week else None
                )

                data3["volatility"] = vol_mom_1month[0] if vol_mom_1month else None
                data3["momentum"] = vol_mom_1month[1] if vol_mom_1month else None
                data3["momentum_change"] = vol_mom_1month[2] if vol_mom_1month else None
                data3["volume_momentum"] = vol_mom_1month[3] if vol_mom_1month else None
                data3["volume_momentum_change"] = (
                    vol_mom_1month[4] if vol_mom_1month else None
                )

                data3["volatility_24hr"] = vol_mom_24hr[0] if vol_mom_24hr else None
                data3["momentum_24hr"] = vol_mom_24hr[1] if vol_mom_24hr else None
                data3["momentum_change_24hr"] = (
                    vol_mom_24hr[2] if vol_mom_24hr else None
                )
                data3["volume_momentum_24hr"] = (
                    vol_mom_24hr[3] if vol_mom_24hr else None
                )
                data3["volume_momentum_change_24hr"] = (
                    vol_mom_24hr[4] if vol_mom_24hr else None
                )

                data3["current_price"] = new_data.iloc[-1]["close"]

                # Get market cap
                try:
                    data3["market_cap"] = (
                        self.get_symbol_cap(symbol) * data3["current_price"]
                    )
                except:
                    data3["market_cap"] = 0
            else:
                # Set default values if chart data is not available
                for metric in [
                    "volatility",
                    "momentum",
                    "momentum_change",
                    "volume_momentum",
                    "volume_momentum_change",
                    "volatility_1week",
                    "momentum_1week",
                    "momentum_change_1week",
                    "volume_momentum_1week",
                    "volume_momentum_change_1week",
                    "volatility_24hr",
                    "momentum_24hr",
                    "momentum_change_24hr",
                    "volume_momentum_24hr",
                    "volume_momentum_change_24hr",
                ]:
                    data3[metric] = None
                data3["current_price"] = 0
                data3["market_cap"] = 0

            return data3
        except Exception as e:
            logger.error(f"Error processing symbol {symbol}: {e}")
            alert_manager.handle_error(
                "TradingViewDataCollector", f"Failed to process symbol {symbol}", e
            )
            return {"symbol": symbol}

    def process_symbols(self):
        """Process all active symbols."""
        start_time = time.time()

        try:
            self.db.update_service_status(
                "TradingViewDataCollector", "running", "Processing symbols"
            )

            data1 = {}
            failed_symbols = []

            # Process each symbol
            for symbol in self.active_symbols:
                logger.info(f"Processing symbol: {symbol}")
                try:
                    data3 = self.process_symbol(symbol)
                    if data3:
                        data1[symbol] = data3
                        logger.info(f"Successfully processed {symbol}")
                except Exception as e:
                    logger.error(f"Failed to process {symbol}: {e}")
                    failed_symbols.append(symbol)

            # Write data to MongoDB
            if data1:
                collection = self.db.db_stock_prices["price_combined_test"]
                collection.insert_one(data1)
                logger.info(
                    f"Successfully wrote data for {len(data1)} symbols to MongoDB"
                )

            end_time = time.time()
            duration = end_time - start_time

            self.db.record_performance_metric(
                "TradingViewDataCollector", "process_symbols", duration, len(data1)
            )

            status_message = f"Processed {len(data1)} symbols in {duration:.2f} seconds"
            if failed_symbols:
                status_message += f" ({len(failed_symbols)} symbols failed)"

            self.db.update_service_status(
                "TradingViewDataCollector",
                "success" if not failed_symbols else "partial_success",
                status_message,
            )

            if failed_symbols:
                alert_manager.handle_error(
                    "TradingViewDataCollector",
                    f"Failed to process {len(failed_symbols)} symbols: {', '.join(failed_symbols)}",
                    data={"failed_symbols": failed_symbols},
                )

            return data1
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"Error in process_symbols: {str(e)}"
            logger.error(error_msg)

            self.db.update_service_status(
                "TradingViewDataCollector", "error", error_msg
            )
            alert_manager.handle_error(
                "TradingViewDataCollector", "Failed to process symbols", e
            )

            return None

    def run(self):
        """Run the data collection and processing if market is open."""
        if is_market_open():
            logger.info("Market is open, collecting TradingView data")
            return self.process_symbols()
        else:
            logger.info("Market is closed, skipping TradingView data collection")
            self.db.update_service_status(
                "TradingViewDataCollector", "idle", "Market is closed"
            )
            return None


# Create a singleton instance
tv_collector = TradingViewDataCollector()

import pandas as pd
import time
from datetime import datetime

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb
from common.db.postgres import postgres_db
from notifications.alert_manager import alert_manager
from common.utils.market_utils import is_market_open, get_current_time_lagos

logger = get_logger(__name__)


class AssetClassifier:
    def __init__(self):
        self.db = mongodb

    def classify_asset(self, asset_data):
        """Classify an asset based on volatility, momentum, etc."""

        # Helper functions
        def categorize_risk(volatility):
            if volatility:
                if volatility <= 0.02:
                    return "Very Low Risk"
                elif volatility <= 0.04:
                    return "Low Risk"
                elif volatility <= 0.06:
                    return "Moderate Risk"
                elif volatility <= 0.08:
                    return "High Risk"
                else:
                    return "Very High Risk"
            return "Unknown Risk"

        def categorize_momentum(momentum):
            if momentum:
                if momentum >= 15:
                    return "Strong Positive"
                elif momentum >= 5:
                    return "Positive"
                elif momentum >= -3:
                    return "Neutral"
                elif momentum >= -15:
                    return "Negative"
                else:
                    return "Strong Negative"
            return "Unknown Momentum"

        def categorize_volume_momentum(volume_momentum):
            if volume_momentum >= 100:
                return "High"
            elif volume_momentum >= 50:
                return "Medium"
            else:
                return "Low"

        def analyze_market_sentiment(data, period=""):
            suffix = f"_{period}" if period else ""

            momentum = data.get(f"momentum{suffix}", 0)
            volume_momentum = data.get(f"volume_momentum{suffix}", 0)
            momentum_change = data.get(f"momentum_change{suffix}", 0)

            if momentum > 5 and volume_momentum > 50 and momentum_change > 0:
                return "strongly_bullish"
            elif momentum > 3 and volume_momentum > 30:
                return "bullish"
            elif momentum < -3 and volume_momentum < -30:
                return "bearish"
            elif momentum < -5 and volume_momentum < -50 and momentum_change < 0:
                return "strongly_bearish"
            else:
                return "neutral"

        def classify_market_cap(cap):
            if cap <= 50_000_000_000:  # Below NGN 50 billion
                return "small-cap"
            elif cap <= 140_000_000_000:  # Between NGN 50 billion and NGN 200 billion
                return "mid-cap"
            else:  # NGN 200 billion and above
                return "large-cap"

        # Initialize classification dictionary
        classification = {
            "symbol": asset_data.get("symbol", "Unknown"),
        }

        # Process metrics for different time periods
        time_periods = ["24hr", "", "1week"]
        overall_risk = 0
        overall_momentum = 0

        for period in time_periods:
            suffix = f"_{period}" if period else ""
            period_name = period if period else "1_month"

            # Get period-specific metrics
            volatility = asset_data.get(f"volatility{suffix}", 0)
            momentum = asset_data.get(f"momentum{suffix}", 0)
            volume_momentum = asset_data.get(f"volume_momentum{suffix}", 0)
            market_cap = asset_data.get("market_cap", 0)

            # Classify metrics for this period
            classification[f"{period_name}_risk"] = categorize_risk(volatility)
            classification[f"{period_name}_momentum"] = categorize_momentum(momentum)
            classification[f"{period_name}_volume"] = categorize_volume_momentum(
                volume_momentum
            )
            classification[f"{period_name}_sentiment"] = analyze_market_sentiment(
                asset_data, period
            )

            # Accumulate overall metrics
            if volatility:
                overall_risk += volatility
            if momentum:
                overall_momentum += momentum
        # Calculate overall metrics
        classification["overall_risk"] = categorize_risk(
            overall_risk / len(time_periods)
        )
        classification["overall_momentum"] = categorize_momentum(
            overall_momentum / len(time_periods)
        )

        # Market cap classification
        current_price = asset_data.get("current_price", 0)
        classification["market_cap"] = classify_market_cap(market_cap)

        # Overall sentiment
        classification["overall_sentiment"] = analyze_market_sentiment(asset_data)

        return classification

    def classify_assets(self):
        """Classify all active assets based on the latest data."""
        start_time = time.time()

        try:
            self.db.update_service_status(
                "AssetClassifier", "running", "Classifying assets"
            )

            # Get active symbols
            stocks = postgres_db.get_active_stocks()
            active_symbols = [stock.symbol for stock in stocks]

            # Get the latest merged data
            collection = self.db.db_live["merged_live_price"]
            last_item = collection.find_one(sort=[("_id", -1)])

            if not last_item:
                logger.warning("No data available for classification")
                self.db.update_service_status(
                    "AssetClassifier", "warning", "No data available"
                )
                return None

            # Remove _id field
            if "_id" in last_item:
                last_item.pop("_id")

            classified_assets = {}
            lagos_now = get_current_time_lagos()

            # Classify each active symbol
            for symbol in active_symbols:
                if symbol in last_item:
                    logger.info(f"Classifying {symbol}")
                    data = last_item[symbol]
                    classification = self.classify_asset(data)
                    classified_assets[symbol] = classification
                else:
                    logger.warning(f"Symbol {symbol} not found in latest data")

            # Save classifications to MongoDB
            risk_collection = self.db.db_risk["risk_classification"]
            risk_collection.insert_one(classified_assets)

            end_time = time.time()
            duration = end_time - start_time

            self.db.record_performance_metric(
                "AssetClassifier", "classify_assets", duration, len(classified_assets)
            )

            self.db.update_service_status(
                "AssetClassifier",
                "success",
                f"Classified {len(classified_assets)} assets in {duration:.2f} seconds",
            )

            # Send notification
            alert_manager.send_process_completion(
                "Asset Classification", f"Classified {len(classified_assets)} assets"
            )

            return classified_assets

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"Error classifying assets: {str(e)}"
            logger.error(error_msg)

            self.db.update_service_status("AssetClassifier", "error", error_msg)
            alert_manager.handle_error(
                "AssetClassifier", "Failed to classify assets", e
            )

            return None

    def run(self):
        """Run the asset classification process if market is open."""
        if is_market_open():
            logger.info("Market is open, classifying assets")
            return self.classify_assets()
        else:
            logger.info("Market is closed, skipping asset classification")
            self.db.update_service_status("AssetClassifier", "idle", "Market is closed")
            return None


# Create a singleton instance
asset_classifier = AssetClassifier()

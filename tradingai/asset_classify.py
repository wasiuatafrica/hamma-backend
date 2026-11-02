from django.utils import timezone

from portfolio.models import Stock
from portfolio.utils import client

riskdb = client["stock_classification"]
risk_collection = riskdb["risk_classification"]

db_merged = client["livelake3"]
# collection = db_merged["merged_live_price"]
collection = db_merged["merged_live_price_trdv"]


def classify_asset(asset_data, symbol=None):
    # Helper functions
    def categorize_risk(volatility):
        if volatility is None:
            return "Very High Risk"  # Conservative approach for null values
        elif volatility <= 0.04:
            return "Very Low Risk"
        elif volatility <= 0.06:
            return "Low Risk"
        elif volatility <= 0.08:
            return "Moderate Risk"
        elif volatility <= 0.1:
            return "High Risk"
        else:
            return "Very High Risk"

    def categorize_momentum(momentum):
        if momentum is None:
            return "Strong Negative"  # Conservative approach for null values
        elif momentum >= 15:
            return "Strong Positive"
        elif momentum >= 5:
            return "Positive"
        elif momentum >= -3:
            return "Neutral"
        elif momentum >= -15:
            return "Negative"
        else:
            return "Strong Negative"

    def categorize_volume_momentum(volume_momentum):
        if volume_momentum is None:
            return "Low"  # Conservative approach for null values
        elif volume_momentum >= 100:
            return "High"
        elif volume_momentum >= 50:
            return "Medium"
        else:
            return "Low"

    def analyze_market_sentiment(data, period=""):
        suffix = f"_{period}" if period else ""

        momentum = data.get(f"momentum{suffix}")
        volume_momentum = data.get(f"volume_momentum{suffix}")
        momentum_change = data.get(f"momentum_change{suffix}")

        # Treat None as 0 for sentiment analysis
        momentum = 0 if momentum is None else momentum
        volume_momentum = 0 if volume_momentum is None else volume_momentum
        momentum_change = 0 if momentum_change is None else momentum_change

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
        if cap is None:
            return "small-cap"  # Default to small-cap if market cap is None
        elif cap <= 30_000_000_000:  # Below NGN 30 billion
            return "small-cap"
        elif cap <= 200_000_000_000:  # Between NGN 30 billion and NGN 200 billion
            return "mid-cap"
        else:  # NGN 200 billion and above
            return "large-cap"

    # Initialize classification dictionary
    classification = {
        "symbol": symbol or asset_data.get("symbol", ""),
    }

    # Process metrics for different time periods
    time_periods = ["24hr", "", "1week"]
    overall_risk = 0
    overall_momentum = 0
    risk_count = 0
    momentum_count = 0

    for period in time_periods:
        suffix = f"_{period}" if period else ""
        period_name = period if period else "1_month"

        # Get period-specific metrics (allow None values)
        volatility = asset_data.get(f"volatility{suffix}")
        momentum = asset_data.get(f"momentum{suffix}")
        volume_momentum = asset_data.get(f"volume_momentum{suffix}")

        classification[f"{period_name}_risk"] = categorize_risk(volatility)
        classification[f"{period_name}_momentum"] = categorize_momentum(momentum)
        classification[f"{period_name}_volume"] = categorize_volume_momentum(
            volume_momentum
        )
        classification[f"{period_name}_sentiment"] = analyze_market_sentiment(
            asset_data, period
        )

        # Accumulate overall metrics (only if not None)
        if volatility is not None:
            overall_risk += volatility
            risk_count += 1
        if momentum is not None:
            overall_momentum += momentum
            momentum_count += 1

    # Calculate overall metrics, avoid division by zero
    if risk_count > 0:
        classification["overall_risk"] = categorize_risk(overall_risk / risk_count)
    else:
        classification["overall_risk"] = categorize_risk(
            None
        )  # Will be "Very High Risk"

    if momentum_count > 0:
        classification["overall_momentum"] = categorize_momentum(
            overall_momentum / momentum_count
        )
    else:
        classification["overall_momentum"] = categorize_momentum(
            None
        )  # Will be "Strong Negative"

    # Market cap classification
    current_price = asset_data.get("current_price")
    classification["market_cap"] = classify_market_cap(asset_data.get("market_cap"))

    # Overall sentiment
    classification["overall_sentiment"] = analyze_market_sentiment(asset_data)

    return classification


def classify():
    active_symbols = [stock.symbol for stock in Stock.objects.filter(active=True)]
    last_item = collection.find_one(sort=[("_id", -1)])
    last_item.pop("_id")
    classified_assets = {}
    now = timezone.now()
    for symbol, data in last_item.items():
        if symbol in active_symbols:
            classification = classify_asset(data, symbol)
            # Always add classification since we now handle None values gracefully
            classified_assets[symbol] = classification

    if classified_assets:
        risk_collection.insert_one(classified_assets)

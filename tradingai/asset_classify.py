from portfolio.utils import client
from portfolio.models import Stock

riskdb = client["stock_classification"]
risk_collection = riskdb["risk_classification"]

db_merged = client["livelake3"]
collection = db_merged["merged_live_price"]


def classify_asset(asset_data):
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
        elif cap <= 200_000_000_000:  # Between NGN 50 billion and NGN 200 billion
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
    classification["overall_risk"] = categorize_risk(overall_risk / len(time_periods))
    classification["overall_momentum"] = categorize_momentum(
        overall_momentum / len(time_periods)
    )

    # Market cap classification
    current_price = asset_data.get("current_price", 0)
    classification["market_cap"] = classify_market_cap(market_cap)

    # Overall sentiment
    classification["overall_sentiment"] = analyze_market_sentiment(asset_data)

    return classification


def classify():
    active_symbols = [stock.symbol for stock in Stock.objects.filter(active=True)]
    last_item = collection.find_one(sort=[("_id", -1)])
    last_item.pop("_id")
    classified_assets = {}
    for symbol, data in last_item.items():
        if symbol in active_symbols:
            print(f"classifying {symbol}")
            classification = classify_asset(data)
            classified_assets[symbol] = classification

    risk_collection.insert_one(classified_assets)

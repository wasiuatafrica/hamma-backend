from portfolio.utils import client
from portfolio.models import Stock

riskdb = client["stock_classification"]
risk_collection = riskdb["risk_classification"]

db_merged = client["livelake3"]
collection = db_merged["merged_live_price"]


def classify_asset3(asset_data):
    def categorize_risk(volatility):
        if volatility:
            if volatility < 0.02:
                return "Very Low Risk"
            elif volatility < 0.04:
                return "Low Risk"
            elif volatility < 0.06:
                return "Moderate Risk"
            elif volatility < 0.08:
                return "High Risk"
            else:
                return "Very High Risk"

    def categorize_momentum(momentum):
        if momentum:
            if momentum > 10:
                return "Strong Positive"
            elif momentum > 3:
                return "Positive"
            elif momentum > -3:
                return "Neutral"
            elif momentum > -10:
                return "Negative"
            else:
                return "Strong Negative"

    def categorize_volume(volume):
        if volume > 10000000:
            return "High Volume"
        elif volume > 1000000:
            return "Medium Volume"
        else:
            return "Low Volume"

    # Extract basic data
    classification = {
        "company": asset_data.get("company", "Unknown"),
        "symbol": asset_data.get("symbol", "Unknown"),
    }
    time_periods = ["24hr", "", "1week"]
    overall_risk = 0
    overall_momentum = 0

    for period in time_periods:
        suffix = f"_{period}" if period else ""

        volatility = asset_data.get(f"volatility{suffix}", 0)
        momentum = asset_data.get(f"momentum{suffix}", 0)
        momentum_change = asset_data.get(f"momentum_change{suffix}", 0)
        volume_momentum = asset_data.get(f"volume_momentum{suffix}", 0)
        volume_momentum_change = asset_data.get(f"volume_momentum_change{suffix}", 0)

        period_name = period if period else "1_month"
        classification[f"{period_name}_risk"] = categorize_risk(volatility)
        classification[f"{period_name}_momentum"] = categorize_momentum(momentum)

        if volatility:
            overall_risk += volatility
        if momentum:
            overall_momentum += momentum

    # Classify overall volume
    classification["volume_category"] = categorize_volume(asset_data.get("volume", 0))

    # Calculate overall risk and momentum scores
    classification["overall_risk"] = categorize_risk(overall_risk / len(time_periods))
    classification["overall_momentum"] = categorize_momentum(
        overall_momentum / len(time_periods)
    )

    return classification


def classify():
    active_symbols = [stock.symbol for stock in Stock.objects.filter(active=True)]
    last_item = collection.find_one(sort=[("_id", -1)])
    last_item.pop("_id")
    classified_assets = {}
    for symbol, data in last_item.items():
        if symbol in active_symbols:
            print(f"classifying {symbol}")
            classification = classify_asset3(data)
            classified_assets[symbol] = classification

    risk_collection.insert_one(classified_assets)

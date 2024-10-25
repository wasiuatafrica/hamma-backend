from portfolio.utils import client
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from portfolio.models import Stock


riskdb = client["stock_classification"]
risk_collection = riskdb["risk_classification"]

signal_db = client["trade_signals"]
signal_collection = signal_db["signals"]


class TraderProfile:
    def __init__(
        self,
        trader_id,
        risk_tolerance,
        trading_style,
        preferred_stocks,
        avg_holding_time,
        trading_frequency,
    ):
        self.trader_id = trader_id
        self.risk_tolerance = risk_tolerance
        self.trading_style = trading_style
        self.preferred_stocks = preferred_stocks
        self.avg_holding_time = avg_holding_time
        self.trading_frequency = trading_frequency


class StockData:
    def __init__(self, classified_data):
        self.__dict__.update(classified_data)


def get_relevant_timeframe(trading_frequency):
    if trading_frequency == "daily":
        return "24hr"
    elif trading_frequency == "weekly":
        return "1week"
    else:  # monthly or longer
        return "1_month"


def rule_based_recommendation(trader, stocks):
    recommendations = []
    timeframe = get_relevant_timeframe(trader.trading_frequency)

    for stock in stocks:
        risk_key = f"{timeframe}_risk"
        momentum_key = f"{timeframe}_momentum"

        if trader.risk_tolerance == "high" and stock.__dict__[risk_key] in [
            "High Risk",
            "Very High Risk",
        ]:
            recommendations.append(
                (
                    stock.symbol,
                    f"Matches high risk tolerance ({stock.__dict__[risk_key]})",
                )
            )
        elif (
            trader.risk_tolerance == "medium"
            and stock.__dict__[risk_key] == "Moderate Risk"
        ):
            recommendations.append(
                (
                    stock.symbol,
                    f"Matches medium risk tolerance ({stock.__dict__[risk_key]})",
                )
            )

        if (
            trader.trading_style == "aggressive"
            and stock.__dict__[momentum_key] == "Positive"
        ):
            recommendations.append(
                (
                    stock.symbol,
                    f"Matches aggressive trading style ({stock.__dict__[momentum_key]} momentum)",
                )
            )

        if stock.symbol in trader.preferred_stocks:
            recommendations.append((stock.symbol, "Preferred stock"))

    return recommendations


def ml_based_recommendation(trader, stocks, model, le):
    recommendations = []
    timeframe = get_relevant_timeframe(trader.trading_frequency)

    # Create a custom LabelEncoder for each feature
    risk_le = LabelEncoder()
    style_le = LabelEncoder()
    stock_risk_le = LabelEncoder()
    momentum_le = LabelEncoder()
    volume_le = LabelEncoder()

    # Fit encoders with all possible values
    risk_le.fit(["low", "medium", "high"])
    style_le.fit(["conservative", "moderate", "aggressive"])
    stock_risk_le.fit(
        ["Very Low Risk", "Low Risk", "Moderate Risk", "High Risk", "Very High Risk"]
    )
    momentum_le.fit(
        ["Strong Negative", "Negative", "Neutral", "Positive", "Strong Positive"]
    )
    volume_le.fit(["Low Volume", "Medium Volume", "High Volume"])

    for stock in stocks:
        features = [
            risk_le.transform([trader.risk_tolerance])[0],
            style_le.transform([trader.trading_style])[0],
            stock_risk_le.transform([stock.__dict__[f"{timeframe}_risk"]])[0],
            momentum_le.transform([stock.__dict__[f"{timeframe}_momentum"]])[0],
            volume_le.transform([stock.volume_category])[0],
        ]

        # Add more features for better differentiation
        features.extend(
            [
                (
                    1 if stock.symbol in trader.preferred_stocks else 0
                ),  # Preferred stock indicator
                (
                    len(momentum_le.classes_) - 1
                    if stock.__dict__[f"{timeframe}_momentum"]
                    in ["Strong Positive", "Positive"]
                    else 0
                ),  # Momentum strength
                (
                    len(stock_risk_le.classes_) - 1
                    if stock.__dict__[f"{timeframe}_risk"]
                    in ["High Risk", "Very High Risk"]
                    else 0
                ),  # Risk strength
            ]
        )

        prediction = model.predict_proba([features])[0]
        confidence = prediction[1]  # Probability of success

        if confidence > 0.6:  # You can adjust this threshold
            recommendations.append(
                (
                    stock.symbol,
                    f"ML model recommendation (confidence: {confidence:.2f})",
                )
            )

    return recommendations


# def train_ml_model(historical_data):
#     X, y = prepare_historical_data(historical_data)

#     # Use a more sophisticated model configuration
#     model = RandomForestClassifier(
#         n_estimators=200,
#         max_depth=10,
#         min_samples_split=10,
#         min_samples_leaf=5,
#         class_weight='balanced',
#         random_state=42
#     )

#     model.fit(X, y)
#     return model, None  # We don't need the general LabelEncoder anymore

# def prepare_historical_data(historical_data):
#     X = []
#     y = []

#     # Create and fit separate encoders for each feature
#     risk_le = LabelEncoder()
#     style_le = LabelEncoder()
#     stock_risk_le = LabelEncoder()
#     momentum_le = LabelEncoder()
#     volume_le = LabelEncoder()

#     # Fit encoders with all possible values
#     risk_le.fit(['low', 'medium', 'high'])
#     style_le.fit(['conservative', 'moderate', 'aggressive'])
#     stock_risk_le.fit(['Very Low Risk', 'Low Risk', 'Moderate Risk', 'High Risk', 'Very High Risk'])
#     momentum_le.fit(['Strong Negative', 'Negative', 'Neutral', 'Positive', 'Strong Positive'])
#     volume_le.fit(['Low Volume', 'Medium Volume', 'High Volume'])

#     for data in historical_data:
#         trader = data['trader_profile']
#         stock = data['stock']
#         timeframe = get_relevant_timeframe(trader['trading_frequency'])

#         features = [
#             risk_le.transform([trader['risk_tolerance']])[0],
#             style_le.transform([trader['trading_style']])[0],
#             stock_risk_le.transform([stock.get(f'{timeframe}_risk', 'Moderate Risk')])[0],
#             momentum_le.transform([stock.get(f'{timeframe}_momentum', 'Neutral')])[0],
#             volume_le.transform([stock.get('volume_category', 'Low Volume')])[0],
#         ]

#         # Add additional features
#         features.extend([
#             1 if stock.get('symbol') in trader.get('preferred_stocks', []) else 0,
#             len(momentum_le.classes_) - 1 if stock.get(f'{timeframe}_momentum') in ['Strong Positive', 'Positive'] else 0,
#             len(stock_risk_le.classes_) - 1 if stock.get(f'{timeframe}_risk') in ['High Risk', 'Very High Risk'] else 0
#         ])

#         X.append(features)
#         y.append(data['successful'])

#     return np.array(X), np.array(y)


def get_stock_recommendations(trader, stocks, ml_model=None, le=None):
    rule_based_recs = rule_based_recommendation(trader, stocks)
    if ml_model and le:
        ml_based_recs = ml_based_recommendation(trader, stocks, ml_model, le)

        all_recs = list(set(rule_based_recs + ml_based_recs))
    else:
        all_recs = set(rule_based_recs)

    return {
        "trader_id": trader.trader_id,
        "recommended_stocks": [
            {"symbol": symbol, "reason": reason} for symbol, reason in all_recs
        ],
    }


def process_recommendation(
    trader_profile,
):
    last_item = risk_collection.find_one(sort=[("_id", -1)])
    signals_data = signal_collection.find_one(sort=[("_id", -1)])
    last_item.pop("_id")
    watchlisted_stocks = Stock.objects.filter(
        watchlisted_by__user=trader_profile.trader
    )
    watchlisted_stocks_symbols = [stock.symbol for stock in watchlisted_stocks]
    preferred_stocks = trader_profile.preferred_stocks + watchlisted_stocks_symbols
    stocks = [StockData(data) for symbol, data in last_item.items()]
    trader = TraderProfile(
        trader_profile.trader.id,
        trader_profile.risk_tolerance.lower(),
        trader_profile.trading_style.lower(),
        preferred_stocks,
        trader_profile.avg_time_on_trade,
        trader_profile.trading_frequency.lower(),
    )
    recommendations = get_stock_recommendations(trader, stocks)
    print(recommendations)
    recommended_symbols = [
        rec["symbol"] for rec in recommendations["recommended_stocks"]
    ]
    print(recommended_symbols, len(recommended_symbols))
    generated_signals = [
        {symbol: signals_data[symbol]} for symbol in set(recommended_symbols)
    ]
    return generated_signals

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from portfolio.models import Stock
import os
from pymongo import MongoClient

import time
from functools import wraps

client = MongoClient(
    os.environ.get("MONGO_STRING"), tls=True, tlsAllowInvalidCertificates=True
)

riskdb = client["stock_classification"]
risk_collection = riskdb["risk_classification"]

signal_db = client["trade_signals"]
signal_collection = signal_db["signals"]

# risk_collection.create_index([("_id", -1)])
# signal_collection.create_index([("_id", -1)])


class TraderProfile:
    def __init__(
        self,
        trader_id,
        risk_tolerance,
        trading_style,
        preferred_stocks,
        avg_holding_time,
        trading_frequency,
        market_sentiment1,
        preferred_asset_type,
    ):
        self.trader_id = trader_id
        self.risk_tolerance = risk_tolerance
        self.trading_style = trading_style
        self.preferred_stocks = preferred_stocks
        self.avg_holding_time = avg_holding_time
        self.trading_frequency = trading_frequency
        self.market_sentiment1 = market_sentiment1
        self.preferred_asset_type = preferred_asset_type


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


def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds to execute")
        return result

    return wrapper


RISK_PROFILES = {
    "low": {"Very Low Risk": 2, "Low Risk": 1},
    "medium": {"Low Risk": 1, "Moderate Risk": 2, "Medium Risk": 2, "High Risk": 1},
    "high": {"High Risk": 2, "Very High Risk": 2, "Moderate Risk": 1},
}

MOMENTUM_PROFILES = {
    "conservative": {
        "Neutral": 2,
        "Positive": 1,
        "Negative": 1,
    },
    "moderate": {"Positive": 1, "Neutral": 2, "Negative": 1},
    "aggressive": {
        "Strong Positive": 2,
        "Positive": 2,
        "Neutral": 1,
    },
}

VOLUME_PROFILES = {
    "conservative": {"High": 0, "Medium": 1, "Low": 2},
    "moderate": {"High": 1, "Medium": 2, "Low": 1},
    "aggressive": {"High": 2, "Medium": 1, "Low": 0},
}

SENTIMENT_PROFILES = {
    "conservative": {
        "strongly_bullish": 0,
        "bullish": 0,
        "neutral": 1,
        "bearish": 2,
        "strongly_bearish": 2,
    },
    "moderate": {
        "strongly_bullish": 1,
        "bullish": 1,
        "neutral": 2,
        "bearish": 1,
        "strongly_bearish": 1,
    },
    "aggressive": {
        "strongly_bullish": 2,
        "bullish": 2,
        "neutral": 1,
        "bearish": 0,
        "strongly_bearish": 0,
    },
}

MIN_SCORE_THRESHOLD = 6


def get_relevant_timeframe(trading_frequency):
    timeframe_map = {
        "daily": "24hr",
        "weekly": "1week",
        "monthly": "1_month",
        "occasionally": "1_month",
    }
    return timeframe_map.get(trading_frequency, "1_month")


def rule_based_recommendation(trader, stocks):
    # Get profile configurations
    risk_profile = RISK_PROFILES[trader.risk_tolerance]
    momentum_profile = MOMENTUM_PROFILES[trader.trading_style]
    volume_profile = VOLUME_PROFILES[trader.trading_style]
    sentiment_profile = SENTIMENT_PROFILES[trader.trading_style]

    # Get trader preferences
    # preferred_stocks_set = set(trader.preferred_stocks)
    preferred_asset_type = trader.preferred_asset_type
    timeframe = get_relevant_timeframe(trader.trading_frequency)
    trader_sentiment = trader.market_sentiment1

    recommendations = []

    for stock in stocks:
        stock_dict = stock.__dict__

        # Get metrics for the relevant timeframe
        risk_level = stock_dict[f"{timeframe}_risk"]
        momentum = stock_dict[f"{timeframe}_momentum"]
        volume = stock_dict[f"{timeframe}_volume"]
        sentiment = stock_dict[f"{timeframe}_sentiment"]
        market_cap = stock_dict["market_cap"]

        # Calculate individual scores
        risk_score = risk_profile.get(risk_level, 0)
        momentum_score = momentum_profile.get(momentum, 0)
        volume_score = volume_profile.get(volume, 0)
        sentiment_score = sentiment_profile.get(sentiment, 0)

        # Additional scores
        # preferred_bonus = 2 if stock.symbol in preferred_stocks_set else 0
        asset_type_score = 2 if market_cap == preferred_asset_type else 0
        sentiment_match_score = 1 if trader_sentiment == sentiment else 0

        # Calculate total score
        total_score = (
            risk_score
            + momentum_score
            + volume_score
            + sentiment_score
            +
            # preferred_bonus +
            asset_type_score
            + sentiment_match_score
        )

        # Build recommendation if score meets threshold
        if total_score >= MIN_SCORE_THRESHOLD:
            reason_parts = [
                f"Score: {total_score}",
                f"Risk: {risk_level} ({risk_score})",
                f"Momentum: {momentum} ({momentum_score})",
                f"Volume: {volume} ({volume_score})",
                f"Sentiment: {sentiment} ({sentiment_score})",
            ]

            # if preferred_bonus:
            #     reason_parts.append("Preferred stock (+2)")

            if asset_type_score:
                reason_parts.append(f"Matches preferred market cap: {market_cap} (+2)")

            if sentiment_match_score:
                reason_parts.append("Matches market sentiment (+1)")

            reason = " | ".join(reason_parts)

            # Current price and other key metrics
            metrics = {
                "current_price": stock_dict.get("current_price", "N/A"),
                "percent_change": stock_dict.get("percent_change", "N/A"),
                "volume": stock_dict.get("volume", "N/A"),
            }

            recommendations.append(
                {
                    "symbol": stock.symbol,
                    "reason": reason,
                    "score": total_score,
                    "metrics": metrics,
                }
            )

    # Sort recommendations by score
    if recommendations:
        recommendations.sort(key=lambda x: x["score"], reverse=True)

    return recommendations[:20]


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


# @timing_decorator
# def get_stock_recommendations(trader, stocks, ml_model=None, le=None):
#     rule_based_recs = rule_based_recommendation(trader, stocks)
#     if ml_model and le:
#         ml_based_recs = ml_based_recommendation(trader, stocks, ml_model, le)

#         all_recs = list(set(rule_based_recs + ml_based_recs))
#     else:
#         all_recs = set(rule_based_recs)

#     return {
#         "trader_id": trader.trader_id,
#         "recommended_stocks": [
#             {"symbol": symbol, "reason": reason} for symbol, reason in all_recs
#         ],
#     }


def get_stock_recommendations(trader, stocks):
    rule_based_recs = rule_based_recommendation(trader, stocks)

    all_recs = rule_based_recs
    print(len(all_recs))

    return {
        "trader_id": trader.trader_id,
        "recommended_stocks": [
            {
                "symbol": data["symbol"],
                "reason": data["reason"],
                "score": data["score"],
            }
            for data in all_recs
        ],
    }


@timing_decorator
def process_recommendation(
    trader_profile,
):
    start = time.time()
    last_item = risk_collection.find_one(sort=[("_id", -1)])

    signals_data = signal_collection.find_one(sort=[("_id", -1)])

    last_item.pop("_id")
    end = time.time()
    print(f"time taken for mongodb {end - start:.4f}s")
    watchlisted_stocks = Stock.objects.filter(
        watchlisted_by__user=trader_profile.trader
    ).values_list("symbol", flat=True)

    watchlisted_stocks_symbols = [symbol for symbol in watchlisted_stocks]
    # print(watchlisted_stocks_symbols)
    preferred_stocks = trader_profile.preferred_stocks + watchlisted_stocks_symbols
    stocks = [StockData(data) for symbol, data in last_item.items()]
    profile = (
        trader_profile.trader.id,
        trader_profile.risk_tolerance.lower(),
        trader_profile.trading_style.lower(),
        preferred_stocks,
        trader_profile.avg_time_on_trade,
        trader_profile.trading_frequency.lower(),
        trader_profile.market_sentiment1,
        trader_profile.preferred_asset_type.lower(),
    )
    # print(profile)
    trader = TraderProfile(
        trader_profile.trader.id,
        trader_profile.risk_tolerance.lower(),
        trader_profile.trading_style.lower(),
        preferred_stocks,
        trader_profile.avg_time_on_trade,
        trader_profile.trading_frequency.lower(),
        trader_profile.market_sentiment1,
        trader_profile.preferred_asset_type.split(" ")[0].lower(),
    )
    recommendations = get_stock_recommendations(trader, stocks)
    # print(recommendations)
    recommended_symbols = [
        rec["symbol"] for rec in recommendations["recommended_stocks"]
    ]
    # print(recommended_symbols, len(recommended_symbols))
    # generated_signals = [
    #     {symbol: signals_data[symbol]} for symbol in set(recommended_symbols)
    # ]

    generated_signals = []
    for symbol in set(recommended_symbols):
        if symbol in signals_data:
            generated_signals.append({symbol: signals_data[symbol]})
    return generated_signals

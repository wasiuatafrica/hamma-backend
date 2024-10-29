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


def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds to execute")
        return result

    return wrapper


# def rule_based_recommendation(trader, stocks):
#     recommendations = []
#     timeframe = get_relevant_timeframe(trader.trading_frequency)

#     for stock in stocks:
#         risk_key = f"{timeframe}_risk"
#         momentum_key = f"{timeframe}_momentum"

#         if trader.risk_tolerance == "high" and stock.__dict__[risk_key] in [
#             "High Risk",
#             "Very High Risk",
#         ]:
#             recommendations.append(
#                 (
#                     stock.symbol,
#                     f"Matches high risk tolerance ({stock.__dict__[risk_key]})",
#                 )
#             )
#         elif (
#             trader.risk_tolerance == "medium"
#             and stock.__dict__[risk_key] == "Moderate Risk"
#         ):
#             recommendations.append(
#                 (
#                     stock.symbol,
#                     f"Matches medium risk tolerance ({stock.__dict__[risk_key]})",
#                 )
#             )

#         if (
#             trader.trading_style == "aggressive"
#             and stock.__dict__[momentum_key] == "Positive"
#         ):
#             recommendations.append(
#                 (
#                     stock.symbol,
#                     f"Matches aggressive trading style ({stock.__dict__[momentum_key]} momentum)",
#                 )
#             )

#         if stock.symbol in trader.preferred_stocks:
#             recommendations.append((stock.symbol, "Preferred stock"))

#     return recommendations


# def rule_based_recommendation(trader, stocks):
#     """
#     Recommend stocks based on trader's risk tolerance and trading style.

#     Parameters:
#     - trader: An object with attributes:
#         - risk_tolerance (str): 'low', 'medium', or 'high'
#         - trading_style (str): 'conservative', 'moderate', or 'aggressive'
#         - trading_frequency (str): e.g., '1week', '1_month', '24hr'
#         - preferred_stocks (set or list): Symbols of preferred stocks
#     - stocks: A list of stock objects with attributes like 'symbol',
#               '1week_risk', '1week_momentum', etc.

#     Returns:
#     - recommendations: A list of tuples (stock_symbol, recommendation_message)
#     """

#     # Define risk profiles and trading styles
#     RISK_PROFILES = {
#         "low": ["Low Risk", "Very Low Risk"],
#         "medium": ["Moderate Risk", "Medium Risk"],
#         "high": ["High Risk", "Very High Risk"],
#     }

#     TRADING_STYLES = {
#         "conservative": {
#             "momentum": ["Neutral", "Slightly Positive"],
#             "risk": ["Low Risk", "Very Low Risk"],
#             "message": "conservative style",
#         },
#         "moderate": {
#             "momentum": ["Neutral", "Slightly Positive"],
#             "risk": ["Moderate Risk", "Medium Risk"],
#             "message": "moderate style",
#         },
#         "aggressive": {
#             "momentum": ["Positive", "Very Positive"],
#             "risk": ["High Risk", "Very High Risk"],
#             "message": "aggressive style",
#         },
#     }

#     recommendations = []
#     timeframe = get_relevant_timeframe(trader.trading_frequency)

#     # Retrieve style configuration; if invalid, return empty recommendations
#     style_config = TRADING_STYLES.get(trader.trading_style.lower())
#     if not style_config:
#         print(f"Unknown trading style: {trader.trading_style}")
#         return recommendations

#     # Get the list of acceptable risk levels based on trader's risk tolerance
#     trader_risk_levels = RISK_PROFILES.get(trader.risk_tolerance.lower(), [])

#     for stock in stocks:
#         # Safely retrieve risk_level and momentum for the relevant timeframe
#         risk_attr = f"{timeframe}_risk"
#         momentum_attr = f"{timeframe}_momentum"
#         risk_level = getattr(stock, risk_attr, None)
#         momentum = getattr(stock, momentum_attr, None)

#         # Skip stock if essential data is missing
#         if not risk_level or not momentum:
#             continue

#         # Check if the stock matches both risk tolerance and trading style
#         matches_risk_tolerance = risk_level in trader_risk_levels
#         matches_style_risk = risk_level in style_config["risk"]
#         matches_style_momentum = momentum in style_config["momentum"]

#         if matches_risk_tolerance and matches_style_risk and matches_style_momentum:
#             message = (
#                 f"Matches {trader.risk_tolerance.capitalize()} risk tolerance "
#                 f"({risk_level}) and {style_config['message']} with {momentum} momentum."
#             )
#             # Highlight preferred stocks
#             if stock.symbol in trader.preferred_stocks:
#                 message += " Preferred stock."
#             recommendations.append((stock.symbol, message))

#     return recommendations


# def rule_based_recommendation(trader, stocks):
#     # Define strategy configurations
#     RISK_PROFILES = {
#         "low": {"Very Low Risk": 2, "Low Risk": 1},
#         "medium": {"Low Risk": 1, "Moderate Risk": 2, "Medium Risk": 2, "High Risk": 1},
#         "high": {"High Risk": 2, "Very High Risk": 2, "Moderate Risk": 1},
#     }

#     MOMENTUM_PROFILES = {
#         "conservative": {"Neutral": 2, "Slightly Positive": 1},
#         "moderate": {"Slightly Positive": 2, "Positive": 1, "Neutral": 1},
#         "aggressive": {"Positive": 2, "Very Positive": 2, "Slightly Positive": 1},
#     }

#     # Minimum score threshold for recommendation
#     MIN_SCORE_THRESHOLD = 3

#     def calculate_stock_score(stock, timeframe):
#         score = 0
#         risk_level = stock.__dict__[f"{timeframe}_risk"]
#         momentum = stock.__dict__[f"{timeframe}_momentum"]

#         # Score based on risk profile
#         risk_score = RISK_PROFILES[trader.risk_tolerance].get(risk_level, 0)

#         # Score based on momentum profile
#         momentum_score = MOMENTUM_PROFILES[trader.trading_style].get(momentum, 0)

#         # Preferred stock bonus
#         preferred_bonus = 2 if stock.symbol in trader.preferred_stocks else 0

#         # Calculate total score
#         score = risk_score + momentum_score + preferred_bonus

#         return score, {
#             "risk_score": risk_score,
#             "momentum_score": momentum_score,
#             "preferred_bonus": preferred_bonus,
#         }

#     recommendations = []
#     timeframe = get_relevant_timeframe(trader.trading_frequency)

#     scored_stocks = []
#     for stock in stocks:
#         total_score, score_breakdown = calculate_stock_score(stock, timeframe)
#         if total_score >= MIN_SCORE_THRESHOLD:
#             scored_stocks.append(
#                 {
#                     "symbol": stock.symbol,
#                     "score": total_score,
#                     "risk": stock.__dict__[f"{timeframe}_risk"],
#                     "momentum": stock.__dict__[f"{timeframe}_momentum"],
#                     "breakdown": score_breakdown,
#                 }
#             )

#     # Sort recommendations by score
#     scored_stocks.sort(key=lambda x: x["score"], reverse=True)

#     # Format recommendations
#     for stock in scored_stocks:
#         reason = (
#             f"Score: {stock['score']} - "
#             f"Risk: {stock['risk']}, "
#             f"Momentum: {stock['momentum']}"
#         )
#         if stock["breakdown"]["preferred_bonus"] > 0:
#             reason += " (Preferred stock)"

#         recommendations.append((stock["symbol"], reason))

#     return recommendations

# Move these outside the function as module-level constants
RISK_PROFILES = {
    "low": {"Very Low Risk": 2, "Low Risk": 1},
    "medium": {"Low Risk": 1, "Moderate Risk": 2, "Medium Risk": 2, "High Risk": 1},
    "high": {"High Risk": 2, "Very High Risk": 2, "Moderate Risk": 1},
}

MOMENTUM_PROFILES = {
    "conservative": {"Neutral": 2, "Slightly Positive": 1},
    "moderate": {"Slightly Positive": 2, "Positive": 1, "Neutral": 1},
    "aggressive": {"Positive": 2, "Very Positive": 2, "Slightly Positive": 1},
}

MIN_SCORE_THRESHOLD = 3


@timing_decorator
def rule_based_recommendation(trader, stocks):
    # Get profile configurations once
    risk_profile = RISK_PROFILES[trader.risk_tolerance]
    momentum_profile = MOMENTUM_PROFILES[trader.trading_style]
    preferred_stocks_set = set(trader.preferred_stocks)
    timeframe = get_relevant_timeframe(trader.trading_frequency)

    # Pre-allocate list with estimated size
    recommendations = []
    recommendations_append = recommendations.append  # Local variable for faster append

    # Process stocks in a single pass
    risk_key = f"{timeframe}_risk"
    momentum_key = f"{timeframe}_momentum"

    for stock in stocks:
        # Direct dictionary access instead of __dict__
        stock_dict = stock.__dict__
        risk_level = stock_dict[risk_key]
        momentum = stock_dict[momentum_key]

        # Calculate scores using direct lookups
        risk_score = risk_profile.get(risk_level, 0)
        momentum_score = momentum_profile.get(momentum, 0)
        preferred_bonus = 2 if stock.symbol in preferred_stocks_set else 0

        total_score = risk_score + momentum_score + preferred_bonus

        if total_score >= MIN_SCORE_THRESHOLD:
            # Build reason string directly
            reason = f"Score: {total_score} - Risk: {risk_level}, Momentum: {momentum}"
            if preferred_bonus:
                reason += " (Preferred stock)"

            recommendations_append((stock.symbol, reason))

    # Sort only once at the end if needed
    if recommendations:
        recommendations.sort(
            key=lambda x: int(x[1].split(":")[1].split("-")[0]), reverse=True
        )

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


@timing_decorator
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

    watchlisted_stocks_symbols = [stock.symbol for stock in watchlisted_stocks]
    preferred_stocks = trader_profile.preferred_stocks + watchlisted_stocks_symbols
    stocks = [StockData(data) for symbol, data in last_item.items()]
    profile = (
        trader_profile.trader.id,
        trader_profile.risk_tolerance.lower(),
        trader_profile.trading_style.lower(),
        preferred_stocks,
        trader_profile.avg_time_on_trade,
        trader_profile.trading_frequency.lower(),
    )
    print(profile)
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

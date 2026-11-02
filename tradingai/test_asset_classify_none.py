# Test for classify_asset with None values
from tradingai.asset_classify import classify_asset


def test_classify_asset_with_none():
    sample_data = {
        "symbol": "ABBEYBDS",
        "datetime": "2025-09-15 12:05:46",
        "open": 6.8,
        "high": 6.8,
        "low": 6.8,
        "close": 6.8,
        "volume": 100000,
        "change": 0.3,
        "percentage_change": 4.62,
        "current_price": 6.8,
        "volatility": 0.91,
        "momentum": 29.03,
        "momentum_change": 1.53,
        "volume_momentum": -78.29,
        "volume_momentum_change": -360616.0,
        "volatility_1week": None,
        "momentum_1week": None,
        "momentum_change_1week": None,
        "volume_momentum_1week": None,
        "volume_momentum_change_1week": None,
        "volatility_1year": 0.78,
        "momentum_1year": 259.08,
        "momentum_change_1year": 4.91,
        "volume_momentum_1year": 415.35,
        "volume_momentum_change_1year": 80595.53,
        "volatility_ytd": 1.0,
        "momentum_ytd": 192.05,
        "momentum_change_ytd": 4.47,
        "volume_momentum_ytd": -44.24,
        "volume_momentum_change_ytd": -79334.13,
        "volatility_24hr": None,
        "momentum_24hr": None,
        "momentum_change_24hr": None,
        "volume_momentum_24hr": None,
        "volume_momentum_change_24hr": None,
        "market_cap": 69046153847.2,
    }
    result = classify_asset(sample_data)


if __name__ == "__main__":
    test_classify_asset_with_none()

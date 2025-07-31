#!/usr/bin/env python3
"""
Quick test script for the unified price system
"""
import os
import sys

# Set testing mode
os.environ["TESTING_MODE"] = "true"

# Add the directory to Python path
sys.path.append(os.path.dirname(__file__))

# Import and test individual functions
try:
    from unified_price_system import (
        get_live_data_from_tradingview,
        get_historical_data_for_period,
        calculate_comprehensive_metrics,
        is_market_open,
        symbols,
    )

    print("✓ All imports successful")

    # Test with one symbol
    test_symbol = "ZENITHBANK"

    print(f"\nTesting live data for {test_symbol}...")
    live_data = get_live_data_from_tradingview(test_symbol)
    if live_data:
        print(f"✓ Live data retrieved: {live_data['close']}")
    else:
        print("✗ No live data retrieved")

    print(f"\nTesting historical data for {test_symbol}...")
    hist_data = get_historical_data_for_period(test_symbol, 7)
    if hist_data is not None and not hist_data.empty:
        print(f"✓ Historical data retrieved: {len(hist_data)} rows")
        print(f"  Index type: {type(hist_data.index)}")
        print(f"  Index timezone: {hist_data.index.tz}")
    else:
        print("✗ No historical data retrieved")

    print(f"\nTesting comprehensive metrics for {test_symbol}...")
    metrics = calculate_comprehensive_metrics(test_symbol)
    if metrics:
        print(f"✓ Metrics calculated")
        print(f"  Current price: {metrics.get('current_price', 'N/A')}")
        print(f"  Volatility (1M): {metrics.get('volatility', 'N/A')}")
        print(f"  Market cap: {metrics.get('market_cap', 'N/A')}")
    else:
        print("✗ No metrics calculated")

    print(f"\nMarket status: {'Open' if is_market_open() else 'Closed'}")
    print(f"Testing mode: {os.environ.get('TESTING_MODE', 'false')}")

    print("\n✓ Basic tests completed")

except Exception as e:
    print(f"✗ Error during testing: {e}")
    import traceback

    traceback.print_exc()

#!/usr/bin/env python3
"""
Test script for the unified price system
Tests the new 15-minute price / 1-hour volatility scheduling
"""
import os
import sys
import time as module_time
from datetime import datetime

# Add the current directory to the path to import the unified system
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from unified_price_system import (
    create_merged_data,
    ensure_complete_dataset_for_merged_collection,
    format_next_update_time,
    get_all_live_data,
    is_market_open,
    log_system_status,
    symbols,
    validate_complete_dataset,
)


def test_data_completeness():
    """Test that we can ensure complete datasets"""
    print("🧪 Testing data completeness functions...")

    # Test with partial live data
    partial_live_data = {
        "MTNN": {"open": 100, "close": 105, "volume": 1000},
        "DANGCEM": {"open": 200, "close": 210, "volume": 2000},
        # Missing other symbols intentionally
    }

    partial_volatility_data = {
        "MTNN": {"volatility": 0.15, "momentum": 5.0},
        "UBA": {"volatility": 0.12, "momentum": 3.0},
        # Missing other symbols intentionally
    }

    print(f"Starting with {len(partial_live_data)} live data entries")
    print(f"Starting with {len(partial_volatility_data)} volatility data entries")

    # Test the completion function
    complete_live, complete_vol = ensure_complete_dataset_for_merged_collection(
        partial_live_data, partial_volatility_data
    )

    # Validate completeness
    live_complete = validate_complete_dataset(complete_live, "live data")
    vol_complete = validate_complete_dataset(complete_vol, "volatility data")

    if live_complete and vol_complete:
        print("✅ Data completion test PASSED")
        return True
    else:
        print("❌ Data completion test FAILED")
        return False


def test_time_formatting():
    """Test the time formatting function"""
    print("\n🧪 Testing time formatting...")

    test_cases = [
        (0, "now"),
        (30, "0m"),
        (60, "1m"),
        (90, "1m"),
        (3600, "1h 0m"),
        (3660, "1h 1m"),
        (7200, "2h 0m"),
        (7290, "2h 1m"),
    ]

    all_passed = True
    for seconds, expected in test_cases:
        result = format_next_update_time(seconds)
        if result == expected:
            print(f"✅ {seconds}s -> '{result}' (expected '{expected}')")
        else:
            print(f"❌ {seconds}s -> '{result}' (expected '{expected}')")
            all_passed = False

    if all_passed:
        print("✅ Time formatting test PASSED")
        return True
    else:
        print("❌ Time formatting test FAILED")
        return False


def test_market_status():
    """Test market status checking"""
    print("\n🧪 Testing market status...")

    market_open = is_market_open()
    print(f"Market currently open: {market_open}")

    current_time = datetime.now()
    print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        f"Current day: {current_time.strftime('%A')} (weekday: {current_time.weekday()})"
    )

    return True


def test_symbols_list():
    """Test that we have the expected number of symbols"""
    print(f"\n🧪 Testing symbols list...")
    print(f"Total symbols: {len(symbols)}")
    print(f"First 5 symbols: {symbols[:5]}")
    print(f"Last 5 symbols: {symbols[-5:]}")

    if len(symbols) > 0:
        print("✅ Symbols list test PASSED")
        return True
    else:
        print("❌ Symbols list test FAILED - no symbols found")
        return False


def run_quick_data_test():
    """Run a quick test to fetch some live data (only if market is open)"""
    print(f"\n🧪 Testing live data fetching...")

    if not is_market_open():
        print("⏰ Market is closed - skipping live data test")
        return True

    print("Market is open - testing live data fetch for first 3 symbols...")

    # Test with just first 3 symbols to avoid overwhelming the API
    test_symbols = symbols[:3]

    try:
        from unified_price_system import get_live_data_from_tradingview

        for symbol in test_symbols:
            print(f"Fetching data for {symbol}...")
            data = get_live_data_from_tradingview(symbol)
            if data:
                print(f"✅ Got data: close={data['close']}, volume={data['volume']}")
            else:
                print(f"⚠ No data for {symbol}")

            # Small delay to be respectful to the API
            module_time.sleep(2)

        print("✅ Live data test completed")
        return True

    except Exception as e:
        print(f"❌ Live data test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Running Unified Price System Tests")
    print("=" * 60)

    tests = [
        ("Symbols List", test_symbols_list),
        ("Time Formatting", test_time_formatting),
        ("Data Completeness", test_data_completeness),
        ("Market Status", test_market_status),
        ("Live Data Fetch", run_quick_data_test),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results[test_name] = False

    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = 0
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1

    print("=" * 60)
    print(f"Overall: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 ALL TESTS PASSED! System ready to run.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review before running the system.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

import requests
from dotenv import load_dotenv
import os
from tvDatafeed import TvDatafeed, Interval
from pymongo import MongoClient
import pandas as pd
from datetime import datetime, timedelta, time
import time as module_time
import math
import pytz
import numpy as np
import json
import pickle
from collections import defaultdict

# Load environment variables
load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")
client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

# Database collections - Using TradingView as primary data lake
db_stock_prices = client["stock_prices_trdv"]
collection_price_combined = db_stock_prices["price_combined_trdv"]

db_live = client["livelake3"]
collection_live = db_live["live_price_combined_trdv"]
collection_merged = db_live["merged_live_price_trdv"]

db_cap = client["ngxlistedcompanies"]

# TradingView data feed
tv = TvDatafeed()

# Lagos timezone
lagos_tz = pytz.timezone("Africa/Lagos")


# In-memory cache for reducing database queries
class DataCache:
    def __init__(self):
        self.live_data_cache = {}
        self.volatility_data_cache = {}
        self.market_cap_cache = {}
        self.last_db_fetch = {}
        self.cache_expiry = {
            "live": 60,  # 1 minute
            "volatility": 3600,  # 1 hour
            "market_cap": 86400,  # 24 hours
        }

    def is_cache_valid(self, cache_type, symbol=None):
        """Check if cache is still valid"""
        if cache_type not in self.last_db_fetch:
            return False

        if symbol:
            if symbol not in self.last_db_fetch[cache_type]:
                return False
            last_fetch = self.last_db_fetch[cache_type][symbol]
        else:
            last_fetch = self.last_db_fetch[cache_type]

        return (module_time.time() - last_fetch) < self.cache_expiry[cache_type]

    def update_cache_timestamp(self, cache_type, symbol=None):
        """Update cache timestamp"""
        if cache_type not in self.last_db_fetch:
            self.last_db_fetch[cache_type] = {}

        if symbol:
            self.last_db_fetch[cache_type][symbol] = module_time.time()
        else:
            self.last_db_fetch[cache_type] = module_time.time()

    def get_cached_live_data(self, symbol):
        """Get cached live data if valid"""
        if self.is_cache_valid("live", symbol):
            return self.live_data_cache.get(symbol)
        return None

    def cache_live_data(self, symbol, data):
        """Cache live data"""
        self.live_data_cache[symbol] = data
        self.update_cache_timestamp("live", symbol)

    def get_cached_volatility_data(self, symbol):
        """Get cached volatility data if valid and not fallback"""
        if (
            self.is_cache_valid("volatility", symbol)
            and symbol in self.volatility_data_cache
        ):
            cached_data = self.volatility_data_cache.get(symbol)
            # Only return if it's not fallback data
            if cached_data and not cached_data.get("is_fallback", False):
                return cached_data
        return None

    def cache_volatility_data(self, symbol, data):
        """Cache volatility data"""
        self.volatility_data_cache[symbol] = data
        self.update_cache_timestamp("volatility", symbol)

    def get_cached_market_cap(self, symbol):
        """Get cached market cap if valid"""
        if self.is_cache_valid("market_cap", symbol):
            return self.market_cap_cache.get(symbol)
        return None

    def cache_market_cap(self, symbol, data):
        """Cache market cap data"""
        self.market_cap_cache[symbol] = data
        self.update_cache_timestamp("market_cap", symbol)

    def should_use_fresh_api_call(self, cache_type, symbol):
        """Determine if a fresh API call should be made for a symbol"""
        # Always make fresh calls if no cache exists
        if cache_type not in self.last_db_fetch:
            return True

        if symbol not in self.last_db_fetch[cache_type]:
            return True

        # Always make fresh calls if cache is expired
        if not self.is_cache_valid(cache_type, symbol):
            return True

        # For volatility data, check if cached data is fallback
        if cache_type == "volatility":
            cached_data = self.volatility_data_cache.get(symbol)
            if cached_data and cached_data.get("is_fallback", False):
                return True

        return False


# Global cache instance
cache = DataCache()


# Batch operations manager
class BatchOperations:
    def __init__(self):
        self.pending_inserts = defaultdict(list)
        self.batch_size = 50  # Adjust based on document size
        self.last_flush = module_time.time()
        self.flush_interval = 30  # 30 seconds

    def add_document(self, collection_name, document):
        """Add document to batch queue"""
        self.pending_inserts[collection_name].append(document)

        # Auto-flush if batch is full
        if len(self.pending_inserts[collection_name]) >= self.batch_size:
            self.flush_collection(collection_name)

    def flush_collection(self, collection_name):
        """Flush pending inserts for a specific collection"""
        if (
            collection_name in self.pending_inserts
            and self.pending_inserts[collection_name]
        ):
            try:
                collection = self._get_collection(collection_name)
                collection.insert_many(self.pending_inserts[collection_name])
                count = len(self.pending_inserts[collection_name])
                self.pending_inserts[collection_name] = []
                print(f"Batch inserted {count} documents to {collection_name}")
                return True
            except Exception as e:
                print(f"Error in batch insert to {collection_name}: {e}")
                return False
        return True

    def flush_all(self):
        """Flush all pending operations"""
        for collection_name in list(self.pending_inserts.keys()):
            self.flush_collection(collection_name)
        self.last_flush = module_time.time()

    def _get_collection(self, collection_name):
        """Get MongoDB collection by name"""
        if collection_name == "live":
            return collection_live
        elif collection_name == "price_combined":
            return collection_price_combined
        elif collection_name == "merged":
            return collection_merged
        else:
            # Handle date-based collections
            return db_live[collection_name]

    def should_auto_flush(self):
        """Check if auto-flush is needed"""
        return (module_time.time() - self.last_flush) >= self.flush_interval


# Global batch operations instance
batch_ops = BatchOperations()


# Data change detection for selective updates
class ChangeDetector:
    def __init__(self):
        self.last_data_snapshot = {}

    def has_significant_change(self, symbol, new_data, threshold=0.01):
        """Check if data has changed significantly enough to warrant an update"""
        if symbol not in self.last_data_snapshot:
            self.last_data_snapshot[symbol] = new_data
            return True

        old_data = self.last_data_snapshot[symbol]

        # Check price change
        old_price = old_data.get("close", 0)
        new_price = new_data.get("close", 0)

        if old_price == 0:
            price_change = float("inf") if new_price != 0 else 0
        else:
            price_change = abs((new_price - old_price) / old_price)

        # Check volume change
        old_volume = old_data.get("volume", 0)
        new_volume = new_data.get("volume", 0)

        if old_volume == 0:
            volume_change = float("inf") if new_volume != 0 else 0
        else:
            volume_change = abs((new_volume - old_volume) / old_volume)

        # Update if significant change
        if price_change >= threshold or volume_change >= threshold:
            self.last_data_snapshot[symbol] = new_data
            return True

        return False


# Global change detector
change_detector = ChangeDetector()

# Stock symbols
symbols = [
    "ABBEYBDS",
    "ACADEMY",
    "ACCESSCORP",
    "AFRIPRUD",
    "AFRINSURE",
    "AFROMEDIA",
    "AIICO",
    "AIRTELAFRI",
    "ALEX",
    "ASOSAVINGS",
    "ABCTRANS",
    "AUSTINLAZ",
    "MANSARD",
    "BERGER",
    "BETAGLAS",
    "BAPLC",
    "BUACEMENT",
    "BUAFOODS",
    "CILEASING",
    "CADBURY",
    "CAP",
    "CAPOIL",
    "CAVERTON",
    "CHAMPION",
    "CHAMS",
    "CHELLARAM",
    "CONOIL",
    "CORNERST",
    "WAPIC",
    "CUSTODIAN",
    "CUTIX",
    "CWG",
    "DAARCOMM",
    "DANGCEM",
    "DANGSUGAR",
    "DEAPCAP",
    "DUNLOP",
    "ETRANZACT",
    "ETI",
    "EKOCORP",
    "ELLAHLAKES",
    "ETERNA",
    "EUNISELL",
    "FBNH",
    "FCMB",
    "FIDELITYBK",
    "FIDSON",
    "FLOURMILL",
    "FTNCOCOA",
    "GEREGU",
    "GOLDBREW",
    "GOLDINSURE",
    "VANLEER",
    "GTCO",
    "GUINEAINS",
    "GUINNESS",
    "HONYFLOUR",
    "IKEJAHOTEL",
    "IMG",
    "INFINITY",
    "INTBREW",
    "INTENEGINS",
    "JAIZBANK",
    "JAPAULGOLD",
    "JOHNHOLT",
    "JULI",
    "JBERGER",
    "WAPCO",
    "LASACO",
    "LEARNAFRCA",
    "LINKASSURE",
    "LIVESTOCK",
    "LIVINGTRUST",
    "MAYBAKER",
    "MCNICHOLS",
    "MEDVIEWAIR",
    "MEYER",
    "MORISON",
    "MRS",
    "MTNN",
    "MULTITREX",
    "MULTIVERSE",
    "MBENEFIT",
    "NNFM",
    "NASCON",
    "NCR",
    "NEIMETH",
    "NEM",
    "NESTLE",
    "NAHCO",
    "NB",
    "ENAMELWA",
    "NGXGROUP",
    "NOTORE",
    "NPFMCRFBK",
    "OANDO",
    "OKOMUOIL",
    "OMATEK",
    "PZ",
    "PHARMDEKO",
    "PREMPAINTS",
    "PRESCO",
    "PRESTIGE",
    "RTBRISCOE",
    "REDSTAREX",
    "REGALINS",
    "RONCHESS",
    "ROYALEX",
    "SCOA",
    "NSLTECH",
    "SEPLAT",
    "SFSREIT",
    "SKYAVN",
    "SMURFIT",
    "SOVRENINS",
    "STACO",
    "STANBIC",
    "STDINSURE",
    "STERLINGNG",
    "SUNUASSUR",
    "TANTALIZER",
    "TIP",
    "THOMASWY",
    "TOTAL",
    "TOURIST",
    "TRANSEXPR",
    "TRANSCOHOT",
    "TRANSCORP",
    "TRIPPLEG",
    "UACN",
    "UHOMREIT",
    "UNILEVER",
    "UBN",
    "UNIONDICON",
    "UNHOMES",
    "UBA",
    "UCAP",
    "UNITYBNK",
    "UNIVINSURE",
    "UPL",
    "UPDC",
    "UPDCREIT",
    "VERITASKAP",
    "VFDGROUP",
    "VITAFOAM",
    "WEMABANK",
    "ZENITHBANK",
]


def safe_float(value):
    """
    Returns a safe float value. Converts `inf` and `NaN` to None or a default value.
    """
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
    return value


def is_market_open():
    """Check if the Nigerian stock market is currently open"""
    try:
        lagos_timezone = pytz.timezone("Africa/Lagos")
        current_time_lagos = datetime.now(lagos_timezone).time()

        if datetime.today().weekday() < 5:  # Monday to Friday
            market_open_time = time(10, 2)
            market_close_time = time(14, 42)

            if market_open_time <= current_time_lagos <= market_close_time:
                return True

        return False

    except Exception as e:
        print(f"Error checking market hours: {e}")
        return False


def get_live_data_from_tradingview(symbol):
    """Get live data from TradingView for a specific symbol"""
    try:
        # Add retry logic for connection issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                data = tv.get_hist(
                    symbol=symbol,
                    exchange="NSENG",
                    interval=Interval.in_1_minute,
                    n_bars=2,
                )

                if data is not None and not data.empty:
                    data_reset = data.reset_index()
                    last_two_rows = data_reset.iloc[-2:]

                    # Get the latest data
                    latest_data = last_two_rows.iloc[-1]
                    previous_data = (
                        last_two_rows.iloc[-2]
                        if len(last_two_rows) > 1
                        else latest_data
                    )

                    # Calculate change and percentage change
                    close_change = latest_data["close"] - previous_data["close"]
                    percentage_change = (
                        (close_change / previous_data["close"]) * 100
                        if previous_data["close"] != 0
                        else 0
                    )

                    lagos_now = datetime.now(lagos_tz)

                    return {
                        "datetime": lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": float(latest_data["open"]),
                        "high": float(latest_data["high"]),
                        "low": float(latest_data["low"]),
                        "close": float(latest_data["close"]),
                        "volume": (
                            int(latest_data["volume"])
                            if not pd.isna(latest_data["volume"])
                            else 0
                        ),
                        "symbol": symbol,
                        "change": round(float(close_change), 2),
                        "percent": round(float(percentage_change), 2),
                    }
                else:
                    print(f"No data returned for {symbol} on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        module_time.sleep(1)  # Wait 1 second before retry
                        continue
                    else:
                        return None

            except Exception as retry_error:
                print(f"Attempt {attempt + 1} failed for {symbol}: {retry_error}")
                if attempt < max_retries - 1:
                    module_time.sleep(2)  # Wait 2 seconds before retry
                    continue
                else:
                    return None

    except Exception as e:
        print(f"Error getting live data for {symbol}: {e}")
        return None


def ensure_all_symbols_included(live_data, volatility_data, merged_data):
    """Ensure all symbols from the symbols list are included in the datasets"""
    try:
        # Check if any symbols are missing from live_data
        missing_from_live = [s for s in symbols if s not in live_data]
        for symbol in missing_from_live:
            print(f"Adding fallback live data for missing symbol: {symbol}")
            live_data[symbol] = get_last_available_live_data(symbol)

        # Check if any symbols are missing from volatility_data
        missing_from_volatility = [s for s in symbols if s not in volatility_data]
        for symbol in missing_from_volatility:
            print(f"Adding fallback volatility data for missing symbol: {symbol}")
            volatility_data[symbol] = get_last_available_volatility_data(symbol)

        # Recreate merged data to ensure consistency
        merged_data_updated = create_merged_data(live_data, volatility_data)

        return live_data, volatility_data, merged_data_updated

    except Exception as e:
        print(f"Error ensuring all symbols included: {e}")
        return live_data, volatility_data, merged_data


def get_last_available_live_data(symbol):
    """Get the last available live data for a symbol from cache or database"""
    try:
        # Check cache first
        cached_data = cache.get_cached_live_data(symbol)
        if cached_data:
            return cached_data

        # Try to get from merged collection first (most complete data)
        last_data = collection_merged.find_one(
            {"symbol": symbol},
            sort=[("_id", -1)],
            projection={
                "_id": 0,
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
                "change": 1,
                "percentage_change": 1,
            },
        )

        if last_data:
            # Update timestamp to current time but mark as fallback
            lagos_now = datetime.now(lagos_tz)
            fallback_data = {
                "datetime": lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
                "open": last_data.get("open", 0),
                "high": last_data.get("high", 0),
                "low": last_data.get("low", 0),
                "close": last_data.get("close", 0),
                "volume": last_data.get("volume", 0),
                "symbol": symbol,
                "change": last_data.get("change", 0),
                "percent": last_data.get("percentage_change", 0),
                "is_fallback": True,  # Mark as fallback data
            }

            # Cache the result
            cache.cache_live_data(symbol, fallback_data)
            return fallback_data

        # If no data in merged collection, try live collection
        last_live = collection_live.find_one(
            {symbol: {"$exists": True}},
            sort=[("_id", -1)],
            projection={"_id": 0, symbol: 1},
        )

        if last_live and symbol in last_live:
            data = last_live[symbol]
            lagos_now = datetime.now(lagos_tz)
            fallback_data = {
                "datetime": lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
                "open": data.get("open", 0),
                "high": data.get("high", 0),
                "low": data.get("low", 0),
                "close": data.get("close", 0),
                "volume": data.get("volume", 0),
                "symbol": symbol,
                "change": data.get("change", 0),
                "percent": data.get("percent", 0),
                "is_fallback": True,
            }

            # Cache the result
            cache.cache_live_data(symbol, fallback_data)
            return fallback_data

        # If still no data, return default values
        print(f"No historical data found for {symbol}, using defaults")
        lagos_now = datetime.now(lagos_tz)
        default_data = {
            "datetime": lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0,
            "symbol": symbol,
            "change": 0,
            "percent": 0,
            "is_fallback": True,
        }

        # Cache the default data
        cache.cache_live_data(symbol, default_data)
        return default_data

    except Exception as e:
        print(f"Error getting last available data for {symbol}: {e}")
        # Return default values
        lagos_now = datetime.now(lagos_tz)
        default_data = {
            "datetime": lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0,
            "symbol": symbol,
            "change": 0,
            "percent": 0,
            "is_fallback": True,
        }

        # Cache the default data
        cache.cache_live_data(symbol, default_data)
        return default_data


def get_last_available_volatility_data(symbol):
    """Get the last available volatility data for a symbol from cache or database"""
    try:
        # Check cache first
        cached_data = cache.get_cached_volatility_data(symbol)
        if cached_data:
            return cached_data

        # Try to get from price_combined collection
        last_data = collection_price_combined.find_one(
            {"symbol": symbol},
            sort=[("_id", -1)],
            projection={"_id": 0},  # Exclude MongoDB ID but get all other fields
        )

        if last_data:
            last_data.pop("_id", None)  # Remove MongoDB ID if it exists
            last_data["is_fallback"] = True

            # Cache the result
            cache.cache_volatility_data(symbol, last_data)
            return last_data

        # If no data found, return default structure
        print(f"No historical volatility data found for {symbol}, using defaults")
        default_volatility_data = {
            "symbol": symbol,
            "current_price": 0,
            "volatility": 0,
            "momentum": 0,
            "momentum_change": 0,
            "volume_momentum": 0,
            "volume_momentum_change": 0,
            "volatility_1week": 0,
            "momentum_1week": 0,
            "momentum_change_1week": 0,
            "volume_momentum_1week": 0,
            "volume_momentum_change_1week": 0,
            "volatility_1year": 0,
            "momentum_1year": 0,
            "momentum_change_1year": 0,
            "volume_momentum_1year": 0,
            "volume_momentum_change_1year": 0,
            "volatility_ytd": 0,
            "momentum_ytd": 0,
            "momentum_change_ytd": 0,
            "volume_momentum_ytd": 0,
            "volume_momentum_change_ytd": 0,
            "volatility_24hr": 0,
            "momentum_24hr": 0,
            "momentum_change_24hr": 0,
            "volume_momentum_24hr": 0,
            "volume_momentum_change_24hr": 0,
            "market_cap": 0,
            "is_fallback": True,
        }

        # Cache the default data
        cache.cache_volatility_data(symbol, default_volatility_data)
        return default_volatility_data

    except Exception as e:
        print(f"Error getting last available volatility data for {symbol}: {e}")
        # Return default structure
        default_volatility_data = {
            "symbol": symbol,
            "current_price": 0,
            "volatility": 0,
            "momentum": 0,
            "momentum_change": 0,
            "volume_momentum": 0,
            "volume_momentum_change": 0,
            "volatility_1week": 0,
            "momentum_1week": 0,
            "momentum_change_1week": 0,
            "volume_momentum_1week": 0,
            "volume_momentum_change_1week": 0,
            "volatility_1year": 0,
            "momentum_1year": 0,
            "momentum_change_1year": 0,
            "volume_momentum_1year": 0,
            "volume_momentum_change_1year": 0,
            "volatility_ytd": 0,
            "momentum_ytd": 0,
            "momentum_change_ytd": 0,
            "volume_momentum_ytd": 0,
            "volume_momentum_change_ytd": 0,
            "volatility_24hr": 0,
            "momentum_24hr": 0,
            "momentum_change_24hr": 0,
            "volume_momentum_24hr": 0,
            "volume_momentum_change_24hr": 0,
            "market_cap": 0,
            "is_fallback": True,
        }

        # Cache the default data
        cache.cache_volatility_data(symbol, default_volatility_data)
        return default_volatility_data


def get_all_live_data():
    """Get live data for all symbols from TradingView with fallback to last available data"""
    combined = {}
    failed_symbols = []

    for i, symbol in enumerate(symbols):
        print(f"Fetching live data for {symbol}")
        data = get_live_data_from_tradingview(symbol)
        if data:
            combined[symbol] = data
        else:
            print(f"Failed to get fresh data for {symbol}, using fallback")
            failed_symbols.append(symbol)
            fallback_data = get_last_available_live_data(symbol)
            combined[symbol] = fallback_data

        # Add small delay between requests to avoid overwhelming the API
        if i < len(symbols) - 1:  # Don't delay after the last symbol
            module_time.sleep(0.5)

    if failed_symbols:
        print(f"Used fallback data for {len(failed_symbols)} symbols: {failed_symbols}")

    return combined


def get_symbol_cap(symbol):
    """Get market cap data for a symbol with caching"""
    try:
        # Check cache first
        cached_cap = cache.get_cached_market_cap(symbol)
        if cached_cap is not None:
            return cached_cap

        collection = db_cap[symbol]
        data = collection.find_one({}, projection={"SharesOutstanding": 1, "_id": 0})
        shares_outstanding = data["SharesOutstanding"] if data else 0

        # Cache the result
        cache.cache_market_cap(symbol, shares_outstanding)
        return shares_outstanding
    except Exception as e:
        print(f"Error getting market cap for {symbol}: {e}")
        # Cache zero value to avoid repeated failed queries
        cache.cache_market_cap(symbol, 0)
        return 0


def get_historical_data_for_period(symbol, period_days):
    """Get historical data from TradingView for specified period"""
    try:
        # Determine appropriate interval and number of bars based on period
        if period_days == 1:  # 24 hours
            interval = Interval.in_1_hour
            n_bars = 30  # Last 30 hours to ensure we have enough data
        elif period_days <= 7:  # 1 week
            interval = Interval.in_1_hour
            n_bars = min(168, period_days * 24)  # 168 hours = 1 week
        elif period_days <= 30:  # 1 month
            interval = Interval.in_daily
            n_bars = min(30, period_days)
        elif period_days <= 365:  # 1 year
            interval = Interval.in_daily
            n_bars = min(365, period_days)
        else:  # More than 1 year
            interval = Interval.in_weekly
            n_bars = min(260, period_days // 7)  # Weekly data for longer periods

        # Add retry logic for connection issues
        max_retries = 2
        for attempt in range(max_retries):
            try:
                data = tv.get_hist(
                    symbol=symbol, exchange="NSENG", interval=interval, n_bars=n_bars
                )

                if data is not None and not data.empty:
                    # Ensure timezone consistency
                    if data.index.tz is None:
                        data.index = data.index.tz_localize(lagos_tz)
                    elif data.index.tz != lagos_tz:
                        data.index = data.index.tz_convert(lagos_tz)

                    # Add current live data point
                    live_data = get_live_data_from_tradingview(symbol)
                    if live_data:
                        # Convert live data to DataFrame row
                        lagos_now = datetime.now(lagos_tz)
                        new_row = pd.DataFrame(
                            [
                                {
                                    "open": live_data["open"],
                                    "high": live_data["high"],
                                    "low": live_data["low"],
                                    "close": live_data["close"],
                                    "volume": live_data["volume"],
                                }
                            ],
                            index=[lagos_now],
                        )

                        # Append to historical data
                        data = pd.concat([data, new_row])

                    return data
                else:
                    print(
                        f"No historical data for {symbol}, period {period_days} days, attempt {attempt + 1}"
                    )
                    if attempt < max_retries - 1:
                        module_time.sleep(2)
                        continue
                    else:
                        return None

            except Exception as retry_error:
                print(
                    f"Historical data attempt {attempt + 1} failed for {symbol}: {retry_error}"
                )
                if attempt < max_retries - 1:
                    module_time.sleep(3)
                    continue
                else:
                    return None

    except Exception as e:
        print(f"Error getting historical data for {symbol}, period {period_days}: {e}")
        return None


def filter_data_by_period(data, period_days):
    """Filter dataframe to specific period"""
    if data is None or data.empty:
        return None

    try:
        if period_days <= 7:
            # For short periods, use last N days
            # Make sure datetime comparison is timezone-aware
            cutoff_date = datetime.now(lagos_tz) - timedelta(days=period_days)
            # Convert index to timezone-aware if needed
            if data.index.tz is None:
                data.index = data.index.tz_localize(lagos_tz)
            elif data.index.tz != lagos_tz:
                data.index = data.index.tz_convert(lagos_tz)

            filtered_data = data[data.index >= cutoff_date]
        else:
            # For longer periods, use tail
            filtered_data = data.tail(period_days)

        return filtered_data if not filtered_data.empty else None
    except Exception as e:
        print(f"Error filtering data by period {period_days}: {e}")
        # Fallback to simple tail
        return data.tail(min(len(data), period_days * 24)) if not data.empty else None


def calculate_volatility_momentum_24hr(symbol, data):
    """Calculate 24-hour volatility and momentum"""
    try:
        if data is None or data.empty:
            return None, None, None, None, None

        # Filter to last 24 hours
        filtered_data = filter_data_by_period(data, 1)
        if filtered_data is None or len(filtered_data) < 2:
            return None, None, None, None, None

        df = filtered_data.copy()
        df = df.dropna(subset=["open", "close"])

        if len(df) < 2:
            return None, None, None, None, None

        df["returns"] = df["close"].pct_change()
        volatility = df["returns"].std() * np.sqrt(252)  # Annualized

        start_price = df["close"].iloc[0]
        end_price = df["close"].iloc[-1]
        momentum_change = end_price - start_price
        momentum = (momentum_change / start_price) * 100

        start_volume = df["volume"].iloc[0]
        end_volume = df["volume"].iloc[-1]
        volume_momentum_change = end_volume - start_volume

        if start_volume == 0:
            volume_momentum = 0
        else:
            volume_momentum = (volume_momentum_change / start_volume) * 100

        return (
            round(volatility, 2),
            round(momentum, 2),
            round(momentum_change, 2),
            round(volume_momentum, 2),
            round(volume_momentum_change, 2),
        )
    except Exception as e:
        print(f"Error calculating 24hr volatility/momentum for {symbol}: {e}")
        return None, None, None, None, None


def calculate_volatility_momentum(data, period):
    """Calculate volatility and momentum for different periods"""
    try:
        if data is None or data.empty:
            return None, None, None, None, None

        # Filter data to specific period
        filtered_data = filter_data_by_period(data, period)
        if filtered_data is None or len(filtered_data) < 3:
            return None, None, None, None, None

        # Handle NaN values
        filtered_data = filtered_data.ffill().bfill()

        # Calculate returns
        filtered_data = filtered_data.copy()
        filtered_data["returns"] = filtered_data["close"].pct_change()
        filtered_data["returns"] = filtered_data["returns"].fillna(0)

        # Calculate annualized volatility
        volatility = filtered_data["returns"].std() * np.sqrt(252)

        start_price = filtered_data["close"].iloc[0]
        end_price = filtered_data["close"].iloc[-1]
        momentum_change = end_price - start_price
        momentum = momentum_change / start_price * 100

        start_volume = filtered_data["volume"].iloc[0]
        end_volume = filtered_data["volume"].iloc[-1]
        volume_momentum_change = end_volume - start_volume

        if start_volume == 0:
            volume_momentum = 0
        else:
            volume_momentum = (volume_momentum_change / start_volume) * 100

        return (
            round(volatility, 2),
            round(momentum, 2),
            round(momentum_change, 2),
            round(volume_momentum, 2),
            round(volume_momentum_change, 2),
        )
    except Exception as e:
        print(f"Error calculating volatility/momentum: {e}")
        return None, None, None, None, None


def calculate_comprehensive_metrics(symbol):
    """Calculate all volatility and momentum metrics for a symbol using TradingView data"""
    data_metrics = {"symbol": symbol}

    try:
        # Get live data for current price
        live_data = get_live_data_from_tradingview(symbol)
        current_price = live_data["close"] if live_data else 0
        data_metrics["current_price"] = current_price

        # 1-year calculations using daily data
        data_1year = get_historical_data_for_period(symbol, 365)
        if data_1year is not None and not data_1year.empty:
            vol_mom_1year = calculate_volatility_momentum(data_1year, 365)
            data_metrics["volatility_1year"] = (
                vol_mom_1year[0] if vol_mom_1year else None
            )
            data_metrics["momentum_1year"] = vol_mom_1year[1] if vol_mom_1year else None
            data_metrics["momentum_change_1year"] = (
                vol_mom_1year[2] if vol_mom_1year else None
            )
            data_metrics["volume_momentum_1year"] = (
                vol_mom_1year[3] if vol_mom_1year else None
            )
            data_metrics["volume_momentum_change_1year"] = (
                vol_mom_1year[4] if vol_mom_1year else None
            )

            # Year-to-date calculations
            current_year = datetime.now().year
            try:
                # Convert index to datetime if needed and filter by year
                if hasattr(data_1year.index, "year"):
                    data_ytd = data_1year[data_1year.index.year == current_year]
                else:
                    # Convert to datetime if it's not already
                    datetime_index = pd.to_datetime(data_1year.index)
                    data_ytd = data_1year[datetime_index.year == current_year]

                if not data_ytd.empty:
                    ytd_days = (datetime.now() - datetime(current_year, 1, 1)).days
                    vol_mom_ytd = calculate_volatility_momentum(data_ytd, ytd_days)
                    data_metrics["volatility_ytd"] = (
                        vol_mom_ytd[0] if vol_mom_ytd else None
                    )
                    data_metrics["momentum_ytd"] = (
                        vol_mom_ytd[1] if vol_mom_ytd else None
                    )
                    data_metrics["momentum_change_ytd"] = (
                        vol_mom_ytd[2] if vol_mom_ytd else None
                    )
                    data_metrics["volume_momentum_ytd"] = (
                        vol_mom_ytd[3] if vol_mom_ytd else None
                    )
                    data_metrics["volume_momentum_change_ytd"] = (
                        vol_mom_ytd[4] if vol_mom_ytd else None
                    )
                else:
                    # Set YTD defaults
                    for metric in [
                        "volatility_ytd",
                        "momentum_ytd",
                        "momentum_change_ytd",
                        "volume_momentum_ytd",
                        "volume_momentum_change_ytd",
                    ]:
                        data_metrics[metric] = None
            except Exception as ytd_error:
                print(f"Error calculating YTD metrics for {symbol}: {ytd_error}")
                # Set YTD defaults
                for metric in [
                    "volatility_ytd",
                    "momentum_ytd",
                    "momentum_change_ytd",
                    "volume_momentum_ytd",
                    "volume_momentum_change_ytd",
                ]:
                    data_metrics[metric] = None
        else:
            # Set 1-year and YTD defaults
            for metric in [
                "volatility_1year",
                "momentum_1year",
                "momentum_change_1year",
                "volume_momentum_1year",
                "volume_momentum_change_1year",
                "volatility_ytd",
                "momentum_ytd",
                "momentum_change_ytd",
                "volume_momentum_ytd",
                "volume_momentum_change_ytd",
            ]:
                data_metrics[metric] = None

        # 1-month calculations using daily data
        data_1month = get_historical_data_for_period(symbol, 30)
        if data_1month is not None and not data_1month.empty:
            vol_mom_1month = calculate_volatility_momentum(data_1month, 30)
            data_metrics["volatility"] = vol_mom_1month[0] if vol_mom_1month else None
            data_metrics["momentum"] = vol_mom_1month[1] if vol_mom_1month else None
            data_metrics["momentum_change"] = (
                vol_mom_1month[2] if vol_mom_1month else None
            )
            data_metrics["volume_momentum"] = (
                vol_mom_1month[3] if vol_mom_1month else None
            )
            data_metrics["volume_momentum_change"] = (
                vol_mom_1month[4] if vol_mom_1month else None
            )
        else:
            # Set 1-month defaults
            for metric in [
                "volatility",
                "momentum",
                "momentum_change",
                "volume_momentum",
                "volume_momentum_change",
            ]:
                data_metrics[metric] = None

        # 1-week calculations using hourly data
        data_1week = get_historical_data_for_period(symbol, 7)
        if data_1week is not None and not data_1week.empty:
            vol_mom_1week = calculate_volatility_momentum(data_1week, 7)
            data_metrics["volatility_1week"] = (
                vol_mom_1week[0] if vol_mom_1week else None
            )
            data_metrics["momentum_1week"] = vol_mom_1week[1] if vol_mom_1week else None
            data_metrics["momentum_change_1week"] = (
                vol_mom_1week[2] if vol_mom_1week else None
            )
            data_metrics["volume_momentum_1week"] = (
                vol_mom_1week[3] if vol_mom_1week else None
            )
            data_metrics["volume_momentum_change_1week"] = (
                vol_mom_1week[4] if vol_mom_1week else None
            )
        else:
            # Set 1-week defaults
            for metric in [
                "volatility_1week",
                "momentum_1week",
                "momentum_change_1week",
                "volume_momentum_1week",
                "volume_momentum_change_1week",
            ]:
                data_metrics[metric] = None

        # 24-hour calculations using hourly data
        data_24hr = get_historical_data_for_period(symbol, 1)
        if data_24hr is not None and not data_24hr.empty:
            vol_mom_24hr = calculate_volatility_momentum_24hr(symbol, data_24hr)
            data_metrics["volatility_24hr"] = vol_mom_24hr[0] if vol_mom_24hr else None
            data_metrics["momentum_24hr"] = vol_mom_24hr[1] if vol_mom_24hr else None
            data_metrics["momentum_change_24hr"] = (
                vol_mom_24hr[2] if vol_mom_24hr else None
            )
            data_metrics["volume_momentum_24hr"] = (
                vol_mom_24hr[3] if vol_mom_24hr else None
            )
            data_metrics["volume_momentum_change_24hr"] = (
                vol_mom_24hr[4] if vol_mom_24hr else None
            )
        else:
            # Set 24-hour defaults
            for metric in [
                "volatility_24hr",
                "momentum_24hr",
                "momentum_change_24hr",
                "volume_momentum_24hr",
                "volume_momentum_change_24hr",
            ]:
                data_metrics[metric] = None

        # Market cap calculation
        try:
            data_metrics["market_cap"] = get_symbol_cap(symbol) * current_price
        except:
            data_metrics["market_cap"] = 0

        return data_metrics

    except Exception as e:
        print(f"Error calculating comprehensive metrics for {symbol}: {e}")
        return None


def create_merged_data(live_data, volatility_data):
    """Create merged data combining live prices with volatility metrics"""
    combined = {}

    for symbol, live_info in live_data.items():
        if symbol in volatility_data:
            vol_data = volatility_data[symbol]

            merged_data = {
                "datetime": live_info["datetime"],
                "symbol": symbol,
                "open": live_info["open"],
                "high": live_info["high"],
                "low": live_info["low"],
                "close": live_info["close"],
                "volume": live_info["volume"],
                "change": live_info["change"],
                "percentage_change": live_info["percent"],
                "current_price": live_info["close"],
                "volatility": safe_float(vol_data.get("volatility")),
                "momentum": safe_float(vol_data.get("momentum")),
                "momentum_change": safe_float(vol_data.get("momentum_change")),
                "volume_momentum": safe_float(vol_data.get("volume_momentum")),
                "volume_momentum_change": safe_float(
                    vol_data.get("volume_momentum_change")
                ),
                "volatility_1week": safe_float(vol_data.get("volatility_1week")),
                "momentum_1week": safe_float(vol_data.get("momentum_1week")),
                "momentum_change_1week": safe_float(
                    vol_data.get("momentum_change_1week")
                ),
                "volume_momentum_1week": safe_float(
                    vol_data.get("volume_momentum_1week")
                ),
                "volume_momentum_change_1week": safe_float(
                    vol_data.get("volume_momentum_change_1week")
                ),
                "volatility_1year": safe_float(vol_data.get("volatility_1year")),
                "momentum_1year": safe_float(vol_data.get("momentum_1year")),
                "momentum_change_1year": safe_float(
                    vol_data.get("momentum_change_1year")
                ),
                "volume_momentum_1year": safe_float(
                    vol_data.get("volume_momentum_1year")
                ),
                "volume_momentum_change_1year": safe_float(
                    vol_data.get("volume_momentum_change_1year")
                ),
                "volatility_ytd": safe_float(vol_data.get("volatility_ytd")),
                "momentum_ytd": safe_float(vol_data.get("momentum_ytd")),
                "momentum_change_ytd": safe_float(vol_data.get("momentum_change_ytd")),
                "volume_momentum_ytd": safe_float(vol_data.get("volume_momentum_ytd")),
                "volume_momentum_change_ytd": safe_float(
                    vol_data.get("volume_momentum_change_ytd")
                ),
                "volatility_24hr": safe_float(vol_data.get("volatility_24hr")),
                "momentum_24hr": safe_float(vol_data.get("momentum_24hr")),
                "momentum_change_24hr": safe_float(
                    vol_data.get("momentum_change_24hr")
                ),
                "volume_momentum_24hr": safe_float(
                    vol_data.get("volume_momentum_24hr")
                ),
                "volume_momentum_change_24hr": safe_float(
                    vol_data.get("volume_momentum_change_24hr")
                ),
                "market_cap": safe_float(vol_data.get("market_cap", 0)),
            }
        else:
            # If no volatility data, use defaults
            merged_data = {
                "datetime": live_info["datetime"],
                "symbol": symbol,
                "open": live_info["open"],
                "high": live_info["high"],
                "low": live_info["low"],
                "close": live_info["close"],
                "volume": live_info["volume"],
                "change": live_info["change"],
                "percentage_change": live_info["percent"],
                "current_price": live_info["close"],
                "volatility": 0,
                "momentum": 0,
                "momentum_change": 0,
                "volume_momentum": 0,
                "volume_momentum_change": 0,
                "volatility_1week": 0,
                "momentum_1week": 0,
                "momentum_change_1week": 0,
                "volume_momentum_1week": 0,
                "volume_momentum_change_1week": 0,
                "volatility_1year": 0,
                "momentum_1year": 0,
                "momentum_change_1year": 0,
                "volume_momentum_1year": 0,
                "volume_momentum_change_1year": 0,
                "volatility_ytd": 0,
                "momentum_ytd": 0,
                "momentum_change_ytd": 0,
                "volume_momentum_ytd": 0,
                "volume_momentum_change_ytd": 0,
                "volatility_24hr": 0,
                "momentum_24hr": 0,
                "momentum_change_24hr": 0,
                "volume_momentum_24hr": 0,
                "volume_momentum_change_24hr": 0,
                "market_cap": 0,
            }

        combined[symbol] = merged_data

    return combined


def save_data_optimized(live_data, volatility_data, merged_data):
    """Save data using batch operations and selective updates to reduce MongoDB transfer costs"""
    try:
        saved_counts = {"live": 0, "volatility": 0, "merged": 0}

        # Save live data with change detection
        if live_data:
            # Check if data has significantly changed before saving
            changed_symbols = []
            for symbol, data in live_data.items():
                if change_detector.has_significant_change(symbol, data):
                    changed_symbols.append(symbol)

            if changed_symbols:
                # Create filtered live data with only changed symbols
                filtered_live_data = {
                    symbol: live_data[symbol] for symbol in changed_symbols
                }

                # Add to batch operations
                batch_ops.add_document("live", filtered_live_data)

                # Also save to today's collection
                today_str = datetime.now().strftime("%Y-%m-%d")
                batch_ops.add_document(today_str, filtered_live_data)

                saved_counts["live"] = len(changed_symbols)
                print(f"Queued live data for {len(changed_symbols)} changed symbols")
            else:
                print("No significant changes in live data - skipping save")

        # Save volatility data (less frequent, but use batch)
        if volatility_data:
            volatility_documents = []
            for symbol, vol_data in volatility_data.items():
                if not vol_data.get("is_fallback", False):  # Only save fresh data
                    # Add timestamp for tracking and remove any existing _id to avoid duplicates
                    vol_data_with_timestamp = vol_data.copy()
                    vol_data_with_timestamp.pop(
                        "_id", None
                    )  # Remove existing _id if present
                    vol_data_with_timestamp["timestamp"] = datetime.now(
                        lagos_tz
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    volatility_documents.append(vol_data_with_timestamp)

            # Batch insert volatility data
            if volatility_documents:
                try:
                    collection_price_combined.insert_many(volatility_documents)
                    saved_counts["volatility"] = len(volatility_documents)
                    print(
                        f"Batch saved {len(volatility_documents)} fresh volatility records"
                    )
                except Exception as vol_error:
                    print(f"Error batch saving volatility data: {vol_error}")

        # Save merged data (single document with all symbols combined like merge_price4.py)
        if merged_data:
            # Check if any symbol has significant changes
            has_significant_changes = False
            for symbol, merged_info in merged_data.items():
                if not merged_info.get(
                    "is_fallback", False
                ) or change_detector.has_significant_change(symbol, merged_info):
                    has_significant_changes = True
                    break

            # Save as a single combined document with all symbols
            if has_significant_changes:
                try:
                    # Create the combined document like in merge_price4.py
                    combined_document = {}
                    for symbol, merged_info in merged_data.items():
                        # Remove symbol key from individual data since it becomes the key
                        symbol_data = merged_info.copy()
                        symbol_data.pop(
                            "symbol", None
                        )  # Remove symbol field as it's now the key
                        combined_document[symbol] = symbol_data

                    # Insert the single combined document
                    collection_merged.insert_one(combined_document)
                    saved_counts["merged"] = len(merged_data)
                    print(
                        f"Saved combined merged document with {len(merged_data)} symbols (like merge_price4.py format)"
                    )
                except Exception as merge_error:
                    print(f"Error saving combined merged data: {merge_error}")
                    saved_counts["merged"] = 0

        # Force flush if we have accumulated enough data or if it's been too long
        if batch_ops.should_auto_flush():
            batch_ops.flush_all()

        return saved_counts

    except Exception as e:
        print(f"Error in optimized save operation: {e}")
        return {"live": 0, "volatility": 0, "merged": 0}


def save_data(live_data, volatility_data, merged_data):
    """Legacy save function - now redirects to optimized version"""
    return save_data_optimized(live_data, volatility_data, merged_data)


def get_combined():
    """Get combined data similar to merge_price4.py format"""
    try:
        # Get latest volatility data from TradingView price combined collection
        volatile_data = collection_price_combined.find_one(sort=[("_id", -1)])
        print("volatile data gotten")

        # Get latest live data from TradingView live collection
        live_data = collection_live.find_one(sort=[("_id", -1)])
        print("live data gotten")

        if not live_data:
            print("No live data available")
            return {}

        # Combined data storage
        combined = {}

        # Process each symbol in live_data except '_id'
        for symbol, data in live_data.items():
            if symbol != "_id":
                # Find volatility data for this symbol
                data2 = None
                if volatile_data and symbol in volatile_data:
                    data2 = volatile_data[symbol]
                elif volatile_data:
                    # Look for symbol field in the volatile data structure
                    if (
                        isinstance(volatile_data, dict)
                        and "symbol" in volatile_data
                        and volatile_data["symbol"] == symbol
                    ):
                        data2 = volatile_data
                    else:
                        # Try to find symbol data in a different structure
                        for key, value in volatile_data.items():
                            if (
                                isinstance(value, dict)
                                and value.get("symbol") == symbol
                            ):
                                data2 = value
                                break

                if data2:
                    new_data = {
                        "datetime": data["datetime"],
                        "symbol": symbol,
                        "open": data["open"],
                        "high": data["high"],
                        "low": data["low"],
                        "close": data["close"],
                        "volume": data["volume"],
                        "change": data["change"],
                        "percentage_change": data["percent"],
                        "current_price": data["close"],
                        "volatility": safe_float(data2.get("volatility", None)),
                        "momentum": safe_float(data2.get("momentum", None)),
                        "momentum_change": safe_float(
                            data2.get("momentum_change", None)
                        ),
                        "volume_momentum": safe_float(
                            data2.get("volume_momentum", None)
                        ),
                        "volume_momentum_change": safe_float(
                            data2.get("volume_momentum_change", None)
                        ),
                        "volatility_1week": safe_float(
                            data2.get("volatility_1week", None)
                        ),
                        "momentum_1week": safe_float(data2.get("momentum_1week", None)),
                        "momentum_change_1week": safe_float(
                            data2.get("momentum_change_1week", None)
                        ),
                        "volume_momentum_1week": safe_float(
                            data2.get("volume_momentum_1week", None)
                        ),
                        "volume_momentum_change_1week": safe_float(
                            data2.get("volume_momentum_change_1week", None)
                        ),
                        "volatility_1year": safe_float(
                            data2.get("volatility_1year", None)
                        ),
                        "momentum_1year": safe_float(data2.get("momentum_1year", None)),
                        "momentum_change_1year": safe_float(
                            data2.get("momentum_change_1year", None)
                        ),
                        "volume_momentum_1year": safe_float(
                            data2.get("volume_momentum_1year", None)
                        ),
                        "volume_momentum_change_1year": safe_float(
                            data2.get("volume_momentum_change_1year", None)
                        ),
                        "volatility_ytd": safe_float(data2.get("volatility_ytd", None)),
                        "momentum_ytd": safe_float(data2.get("momentum_ytd", None)),
                        "momentum_change_ytd": safe_float(
                            data2.get("momentum_change_ytd", None)
                        ),
                        "volume_momentum_ytd": safe_float(
                            data2.get("volume_momentum_ytd", None)
                        ),
                        "volume_momentum_change_ytd": safe_float(
                            data2.get("volume_momentum_change_ytd", None)
                        ),
                        "volatility_24hr": safe_float(
                            data2.get("volatility_24hr", None)
                        ),
                        "momentum_24hr": safe_float(data2.get("momentum_24hr", None)),
                        "momentum_change_24hr": safe_float(
                            data2.get("momentum_change_24hr", None)
                        ),
                        "volume_momentum_24hr": safe_float(
                            data2.get("volume_momentum_24hr", None)
                        ),
                        "volume_momentum_change_24hr": safe_float(
                            data2.get("volume_momentum_change_24hr", None)
                        ),
                        "market_cap": safe_float(data2.get("market_cap", 0)),
                    }
                else:
                    new_data = {
                        "datetime": data["datetime"],
                        "symbol": symbol,
                        "open": data["open"],
                        "high": data["high"],
                        "low": data["low"],
                        "close": data["close"],
                        "volume": data["volume"],
                        "change": data["change"],
                        "percentage_change": data["percent"],
                        "current_price": data["close"],
                        "volatility": 0,
                        "momentum": 0,
                        "momentum_change": 0,
                        "volume_momentum": 0,
                        "volume_momentum_change": 0,
                        "volatility_1week": 0,
                        "momentum_1week": 0,
                        "momentum_change_1week": 0,
                        "volume_momentum_1week": 0,
                        "volume_momentum_change_1week": 0,
                        "volatility_1year": 0,
                        "momentum_1year": 0,
                        "momentum_change_1year": 0,
                        "volume_momentum_1year": 0,
                        "volume_momentum_change_1year": 0,
                        "volatility_ytd": 0,
                        "momentum_ytd": 0,
                        "momentum_change_ytd": 0,
                        "volume_momentum_ytd": 0,
                        "volume_momentum_change_ytd": 0,
                        "volatility_24hr": 0,
                        "momentum_24hr": 0,
                        "momentum_change_24hr": 0,
                        "volume_momentum_24hr": 0,
                        "volume_momentum_change_24hr": 0,
                        "market_cap": 0,
                    }
                combined[symbol] = new_data
        return combined
    except Exception as e:
        print(f"Error in get_combined: {e}")
        return {}


def write_to_mongodb(dbase, data):
    """Write combined data to MongoDB like merge_price4.py"""
    try:
        collection_merged.insert_one(data)
        print("Live Price merged")
    except Exception as e:
        print(f"Error writing to MongoDB: {e}")


def main_cycle():
    """Main execution cycle with optimized data operations"""
    if not is_market_open():
        print("Market closed")
        return

    print("Market is open - Starting optimized data collection")

    # Step 1: Get live data for all symbols with smart caching
    print("Step 1: Fetching live data from TradingView...")
    live_data = get_all_live_data()

    if not live_data:
        print("No live data retrieved")
        return

    # Step 2: Calculate volatility metrics with intelligent caching
    # Cache logic:
    # - Symbols in symbol list with no valid cache -> fresh API call
    # - Symbols with expired cache -> fresh API call
    # - Symbols with fallback cache -> fresh API call
    # - Only use cache for symbols with recent, valid, non-fallback data
    print(
        "Step 2: Calculating volatility and momentum metrics with intelligent caching..."
    )
    volatility_data = {}
    failed_volatility_symbols = []
    fresh_calculations = 0

    for i, symbol in enumerate(symbols):
        # Determine if we should make a fresh API call
        should_make_fresh_call = cache.should_use_fresh_api_call("volatility", symbol)

        if not should_make_fresh_call:
            # Use cached data if available and valid
            cached_vol_data = cache.get_cached_volatility_data(symbol)
            if cached_vol_data:
                volatility_data[symbol] = cached_vol_data
                print(f"Using cached volatility data for {symbol}")
                continue

        # Make fresh API call for symbols that need it
        print(
            f"Making fresh API call for {symbol} (symbol in list requires fresh data)"
        )
        metrics = calculate_comprehensive_metrics(symbol)
        if metrics:
            volatility_data[symbol] = metrics
            # Cache the fresh data
            cache.cache_volatility_data(symbol, metrics)
            fresh_calculations += 1
            print(f"Successfully calculated fresh metrics for {symbol}")
        else:
            print(f"API call failed for {symbol}, using fallback data")
            failed_volatility_symbols.append(symbol)
            fallback_metrics = get_last_available_volatility_data(symbol)
            volatility_data[symbol] = fallback_metrics

        # Add delay only for fresh calculations to avoid API overload
        if (
            i < len(symbols) - 1 and metrics
        ):  # Don't delay after the last symbol or for cached data
            module_time.sleep(2)  # Reduced delay due to fewer fresh calculations

    print(
        f"Fresh volatility calculations: {fresh_calculations}, Cached: {len(symbols) - fresh_calculations - len(failed_volatility_symbols)}"
    )

    if failed_volatility_symbols:
        print(
            f"Used fallback volatility data for {len(failed_volatility_symbols)} symbols: {failed_volatility_symbols}"
        )

    # Ensure all symbols from live_data have corresponding volatility data
    for symbol in live_data.keys():
        if symbol not in volatility_data:
            print(f"Adding fallback volatility data for missing symbol: {symbol}")
            volatility_data[symbol] = get_last_available_volatility_data(symbol)

    # Step 3: Create merged data
    print("Step 3: Merging data...")
    merged_data = create_merged_data(live_data, volatility_data)

    # Step 3.5: Ensure all symbols are included
    print("Step 3.5: Ensuring all symbols are included...")
    live_data, volatility_data, merged_data = ensure_all_symbols_included(
        live_data, volatility_data, merged_data
    )

    # Step 4: Save data using optimized batch operations
    print("Step 4: Saving data with optimizations...")
    saved_counts = save_data_optimized(live_data, volatility_data, merged_data)

    print(f"Data cycle completed successfully - {len(live_data)} symbols processed")
    print(
        f"Optimized saves - Live: {saved_counts['live']}, Volatility: {saved_counts['volatility']}, Merged: {saved_counts['merged']}"
    )

    # Summary statistics
    fresh_live_count = len(
        [s for s in live_data.values() if not s.get("is_fallback", False)]
    )
    fallback_live_count = len(
        [s for s in live_data.values() if s.get("is_fallback", False)]
    )
    fresh_vol_count = len(
        [s for s in volatility_data.values() if not s.get("is_fallback", False)]
    )
    fallback_vol_count = len(
        [s for s in volatility_data.values() if s.get("is_fallback", False)]
    )

    print(f"Live data - Fresh: {fresh_live_count}, Fallback: {fallback_live_count}")
    print(f"Volatility data - Fresh: {fresh_vol_count}, Fallback: {fallback_vol_count}")
    print(
        f"Total symbols expected: {len(symbols)}, Total symbols saved: {len(merged_data)}"
    )

    if len(merged_data) != len(symbols):
        missing_symbols = [s for s in symbols if s not in merged_data]
        print(f"WARNING: Missing symbols in final dataset: {missing_symbols}")

    # Cache statistics
    print(
        f"Cache hit rates - Live: {len([s for s in live_data.values() if 'cached' in str(s)])}"
    )

    # Periodic cache cleanup (every hour)
    if module_time.time() % 3600 < 60:  # Within first minute of each hour
        cache.live_data_cache.clear()
        print("Performed hourly cache cleanup")


def run_unified_system():
    """Run the unified price system using TradingView as data lake with MongoDB transfer optimizations"""
    print("Starting Optimized Unified Price System")
    print("Using TradingView as primary data lake with caching and batch operations")
    print(
        "Data will be saved in merge_price4.py format (combined document with all symbols)"
    )

    # Different update frequencies
    live_update_interval = 60  # 1 minute for live data
    volatility_update_interval = 3600  # 1 hour for volatility calculations
    cache_cleanup_interval = 1800  # 30 minutes for cache cleanup

    last_volatility_update = 0
    last_cache_cleanup = 0

    while True:
        try:
            current_time = module_time.time()
            today = datetime.today().weekday()

            if is_market_open() and today < 5:
                # Option 1: Use the simplified get_combined approach like merge_price4.py
                print("Using simplified merge approach like merge_price4.py")
                combined = get_combined()
                if combined:
                    write_to_mongodb("livelake3", combined)
                    print(f"Live Price merged - {len(combined)} symbols combined")
                else:
                    print("No data to merge")

                # Also run the full cycle less frequently for comprehensive metrics
                if current_time - last_volatility_update >= volatility_update_interval:
                    print("Also running full update cycle for comprehensive metrics")
                    main_cycle()
                    last_volatility_update = current_time

                # Periodic cache cleanup
                if current_time - last_cache_cleanup >= cache_cleanup_interval:
                    print("Performing cache cleanup...")
                    # Print cache stats before cleanup
                    print("Cache stats before cleanup:", get_cache_stats())
                    # Clear expired cache entries
                    cache.live_data_cache.clear()
                    last_cache_cleanup = current_time
                    print("Cache cleanup completed")

                # Force flush pending batch operations periodically
                if batch_ops.should_auto_flush():
                    print("Auto-flushing batch operations...")
                    batch_ops.flush_all()

                lagos_now = datetime.now(lagos_tz)
                print(
                    f"Next update in {live_update_interval} seconds - {lagos_now.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            else:
                print("Market closed - flushing any pending operations")
                # Flush any pending operations when market closes
                batch_ops.flush_all()

            module_time.sleep(live_update_interval)

        except KeyboardInterrupt:
            print("System stopped by user - flushing final operations")
            batch_ops.flush_all()
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            # Flush operations on error to avoid data loss
            try:
                batch_ops.flush_all()
            except:
                pass
            module_time.sleep(60)  # Wait 1 minute before retrying


def warm_up_cache():
    """Warm up cache with recent data to reduce initial database queries"""
    print("Warming up cache with recent data...")
    try:
        # Load recent volatility data for all symbols
        recent_vol_pipeline = [
            {"$match": {"symbol": {"$in": symbols}}},
            {"$sort": {"_id": -1}},
            {"$group": {"_id": "$symbol", "data": {"$first": "$$ROOT"}}},
            {
                "$project": {
                    "_id": 0,
                    "symbol": "$_id",
                    "data": {
                        "$mergeObjects": [
                            "$data",
                            {"_id": "$$REMOVE"},  # Remove the _id field
                        ]
                    },
                }
            },
        ]

        vol_results = list(collection_price_combined.aggregate(recent_vol_pipeline))
        for result in vol_results:
            symbol = result["symbol"]
            data = result["data"]
            cache.cache_volatility_data(symbol, data)

        print(f"Cached volatility data for {len(vol_results)} symbols")

        # Load recent merged data for change detection baseline
        recent_merged_pipeline = [
            {"$match": {"symbol": {"$in": symbols}}},
            {"$sort": {"_id": -1}},
            {"$group": {"_id": "$symbol", "data": {"$first": "$$ROOT"}}},
            {
                "$project": {
                    "_id": 0,
                    "symbol": "$_id",
                    "close": "$data.close",
                    "volume": "$data.volume",
                }
            },
        ]

        merged_results = list(collection_merged.aggregate(recent_merged_pipeline))
        for result in merged_results:
            symbol = result["symbol"]
            baseline_data = {
                "close": result.get("close", 0),
                "volume": result.get("volume", 0),
            }
            change_detector.last_data_snapshot[symbol] = baseline_data

        print(f"Set change detection baseline for {len(merged_results)} symbols")

        # Load market cap data
        for symbol in symbols:
            try:
                cap_data = get_symbol_cap(symbol)  # This will cache it automatically
            except:
                pass

        print("Cache warm-up completed")

    except Exception as e:
        print(f"Error during cache warm-up: {e}")


def get_cache_stats():
    """Get cache statistics for monitoring"""
    return {
        "live_cache_size": len(cache.live_data_cache),
        "volatility_cache_size": len(cache.volatility_data_cache),
        "market_cap_cache_size": len(cache.market_cap_cache),
        "pending_batch_operations": {
            collection: len(docs)
            for collection, docs in batch_ops.pending_inserts.items()
        },
        "change_detector_baseline_count": len(change_detector.last_data_snapshot),
    }


def optimize_database_indexes():
    """Create indexes to optimize database queries"""
    try:
        # Index for symbol queries (without _id as it's automatically indexed)
        collection_price_combined.create_index([("symbol", 1)])
        collection_merged.create_index([("symbol", 1)])

        # Create compound index for symbol and timestamp for efficient sorting
        collection_price_combined.create_index([("symbol", 1), ("timestamp", -1)])

        # Note: _id is automatically indexed by MongoDB, no need to create additional _id indexes

        print("Database indexes optimized")
        return True
    except Exception as e:
        print(f"Error optimizing database indexes: {e}")
        return False


if __name__ == "__main__":
    # Optimize database indexes first
    optimize_database_indexes()

    # Warm up cache before starting the main system
    warm_up_cache()

    # Print initial cache statistics
    print("Initial cache statistics:", get_cache_stats())

    run_unified_system()

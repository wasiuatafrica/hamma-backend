import json
import math
import os
import pickle
import re
import time as module_time
from collections import defaultdict
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import pytz
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from tvDatafeed import Interval, TvDatafeed

# Load environment variables
load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")
client = MongoClient(MONGO_URL, tls=True)

# Database collections - Using TradingView as primary data lake
# Note: Collections will be created automatically on first insert if they don't exist
db_stock_prices = client["stock_prices_trdv"]
collection_price_combined = db_stock_prices["price_combined_trdv"]

db_live = client["livelake3"]
collection_live = db_live["live_price_combined_trdv"]
collection_merged = db_live["merged_live_price_trdv"]

db_cap = client["ngxlistedcompanies"]

# One document per symbol with the last good (non-zero) price: {_id: symbol, ...}
collection_latest = db_live["latest_prices"]

# Active symbols come from the backend so delisted/renamed stocks drop out
# automatically (replaces the hard-coded list).
BACKEND_URL = os.environ.get(
    "BACKEND_URL", "https://api-hamma-f0bcaabf77ea.herokuapp.com"
).rstrip("/")
SYMBOLS_API_URL = f"{BACKEND_URL}/portfolio/collector-symbols/"
MARKET_STATUS_API_URL = f"{BACKEND_URL}/portfolio/market-status/"
SYMBOLS_CACHE_FILE = "symbols_cache.json"

# Snapshot/history documents older than this are deleted once a day after the close
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "90"))

# Spread 24hr metric refreshes across cycles instead of recomputing all at once
MAX_INTRADAY_REFRESH_PER_CYCLE = int(
    os.environ.get("MAX_INTRADAY_REFRESH_PER_CYCLE", "40")
)

# Collection schedule (Africa/Lagos), following NGX hours: continuous trading
# 09:30-15:50, closing auction to 16:00. Every 15 min from 09:30 to 15:45, plus
# one run after the 16:00 close to capture closing prices.
SLOT_MINUTES = 15
FIRST_SLOT = time(9, 30)
LAST_SLOT = time(15, 45)
CLOSE_RUN = time(16, 5)


def verify_mongodb_connection():
    """Verify MongoDB connection and log cluster status"""
    try:
        # Test connection
        client.admin.command("ping")
        print("✓ MongoDB connection successful")

        # Check if collections exist (optional - they'll be created on first insert)
        databases = client.list_database_names()
        print(f"✓ Connected to MongoDB cluster with {len(databases)} databases")

        # Check if our databases exist
        if "stock_prices_trdv" in databases:
            stock_collections = db_stock_prices.list_collection_names()
            print(
                f"  - stock_prices_trdv database exists ({len(stock_collections)} collections)"
            )
        else:
            print("  - stock_prices_trdv database will be created on first insert")

        if "livelake3" in databases:
            live_collections = db_live.list_collection_names()
            print(
                f"  - livelake3 database exists ({len(live_collections)} collections)"
            )
        else:
            print("  - livelake3 database will be created on first insert")

        if "ngxlistedcompanies" in databases:
            cap_collections = db_cap.list_collection_names()
            print(
                f"  - ngxlistedcompanies database exists ({len(cap_collections)} collections)"
            )
        else:
            print("  - ngxlistedcompanies database will be created when needed")

        print("✓ Script is ready to work with empty or populated MongoDB cluster")
        return True
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        print(
            "  Please check your MONGO_URL environment variable and network connectivity"
        )
        return False


# TradingView data feed
tv = TvDatafeed()

# Lagos timezone
lagos_tz = pytz.timezone("Africa/Lagos")


# Dual-TTL volatility cache:
# - Long-horizon metrics (1y / YTD / 1m / 1w): once per Lagos trading day
# - 24hr metrics: 90-minute cache
INTRADAY_CACHE_DURATION = 5400  # 90 minutes for 24hr metrics
# Backward-compatible alias
VOLATILITY_CACHE_DURATION = INTRADAY_CACHE_DURATION

DAILY_METRIC_KEYS = [
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
    "volatility",
    "momentum",
    "momentum_change",
    "volume_momentum",
    "volume_momentum_change",
    "volatility_1week",
    "momentum_1week",
    "momentum_change_1week",
    "volume_momentum_1week",
    "volume_momentum_change_1week",
]

INTRADAY_METRIC_KEYS = [
    "volatility_24hr",
    "momentum_24hr",
    "momentum_change_24hr",
    "volume_momentum_24hr",
    "volume_momentum_change_24hr",
]


class VolatilityCache:
    def __init__(self):
        self.cache = {}
        self.cache_file = "volatility_cache.pkl"
        self.load_cache()

    @staticmethod
    def lagos_today():
        return datetime.now(lagos_tz).date().isoformat()

    def _normalize_entry(self, entry):
        """Migrate legacy {data, timestamp} entries to dual-TTL shape."""
        if not isinstance(entry, dict):
            return None
        if "data" not in entry:
            return None

        if "daily_date" not in entry or "intraday_timestamp" not in entry:
            legacy_ts = entry.get("timestamp", 0) or 0
            if legacy_ts:
                legacy_dt = datetime.fromtimestamp(legacy_ts, tz=pytz.UTC).astimezone(
                    lagos_tz
                )
                entry.setdefault("daily_date", legacy_dt.date().isoformat())
                entry.setdefault("intraday_timestamp", legacy_ts)
            else:
                entry.setdefault("daily_date", None)
                entry.setdefault("intraday_timestamp", 0)
        return entry

    def load_cache(self):
        """Load cache from disk if it exists"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "rb") as f:
                    raw_cache = pickle.load(f)
                self.cache = {}
                for symbol, entry in raw_cache.items():
                    normalized = self._normalize_entry(entry)
                    if normalized:
                        self.cache[symbol] = normalized
                print(f"Loaded volatility cache with {len(self.cache)} entries")
            else:
                self.cache = {}
        except Exception as e:
            print(f"Error loading cache: {e}")
            self.cache = {}

    def save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.cache, f)
            print(f"Saved volatility cache with {len(self.cache)} entries")
        except Exception as e:
            print(f"Error saving cache: {e}")

    def is_daily_valid(self, symbol):
        """Long-horizon metrics valid for the current Lagos calendar day."""
        entry = self.cache.get(symbol)
        if not entry:
            return False
        entry = self._normalize_entry(entry)
        return entry.get("daily_date") == self.lagos_today()

    def is_intraday_valid(self, symbol):
        """24hr metrics valid for INTRADAY_CACHE_DURATION seconds."""
        entry = self.cache.get(symbol)
        if not entry:
            return False
        entry = self._normalize_entry(entry)
        cached_time = entry.get("intraday_timestamp", 0) or 0
        return (module_time.time() - cached_time) < INTRADAY_CACHE_DURATION

    def is_cache_valid(self, symbol):
        """Fully valid when both daily and 24hr layers are fresh."""
        return self.is_daily_valid(symbol) and self.is_intraday_valid(symbol)

    def get_refresh_needs(self, symbol):
        """Return which metric layers need recalculation and any existing data."""
        entry = self.cache.get(symbol)
        data = entry.get("data") if entry else None
        return {
            "need_daily": not self.is_daily_valid(symbol),
            "need_intraday": not self.is_intraday_valid(symbol),
            "data": data,
        }

    def get_cached_data(self, symbol):
        """Get cached volatility data when both layers are still valid."""
        if self.is_cache_valid(symbol):
            print(f"Using cached volatility data for {symbol}")
            return self.cache[symbol]["data"]
        return None

    def set_cached_data(
        self, symbol, data, updated_daily=False, updated_intraday=False
    ):
        """Cache volatility data, updating only the refreshed TTL layers."""
        entry = self.cache.get(symbol, {})
        entry = self._normalize_entry(entry) or {
            "daily_date": None,
            "intraday_timestamp": 0,
        }
        entry["data"] = data
        # Keep legacy timestamp for older readers
        entry["timestamp"] = module_time.time()
        if updated_daily:
            entry["daily_date"] = self.lagos_today()
        if updated_intraday:
            entry["intraday_timestamp"] = module_time.time()
        self.cache[symbol] = entry
        layers = []
        if updated_daily:
            layers.append("daily")
        if updated_intraday:
            layers.append("24hr")
        print(f"Cached volatility data for {symbol} ({'+'.join(layers) or 'metadata'})")
        if len(self.cache) % 10 == 0:
            self.save_cache()

    def clear_expired_cache(self):
        """Remove entries whose daily layer is from a previous Lagos day."""
        expired_symbols = []
        for symbol in list(self.cache.keys()):
            if not self.is_daily_valid(symbol):
                expired_symbols.append(symbol)
        for symbol in expired_symbols:
            del self.cache[symbol]
            print(f"Removed expired daily cache for {symbol}")
        if expired_symbols:
            self.save_cache()

    def get_cache_stats(self):
        """Get cache statistics for both TTL layers."""
        total = len(self.cache)
        daily_valid = sum(1 for symbol in self.cache if self.is_daily_valid(symbol))
        intraday_valid = sum(
            1 for symbol in self.cache if self.is_intraday_valid(symbol)
        )
        fully_valid = sum(1 for symbol in self.cache if self.is_cache_valid(symbol))

        return {
            "total_entries": total,
            "valid_entries": fully_valid,
            "expired_entries": total - fully_valid,
            "daily_valid": daily_valid,
            "intraday_valid": intraday_valid,
        }


# Global volatility cache instance
volatility_cache = VolatilityCache()


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

# Used only if the backend symbol API is unreachable and there is no cached copy.
# Active NGX stocks that TradingView carries, as of 2 Nov 2026.
FALLBACK_SYMBOLS = [
    "ABBEYBANK",
    "ABCTRANS",
    "ACADEMY",
    "ACCESSCORP",
    "AFRINSURE",
    "AFRIPRUD",
    "AFROMEDIA",
    "AIICO",
    "AIRTELAFRI",
    "ARADEL",
    "AUSTINLAZ",
    "AVACAP",
    "BERGER",
    "BETAGLAS",
    "BUACEMENT",
    "BUAFOODS",
    "CADBURY",
    "CAP",
    "CAVERTON",
    "CHAMPION",
    "CHAMS",
    "CHELLARAM",
    "CILEASING",
    "CMFC",
    "CNIF",
    "CONHALLPLC",
    "CONOIL",
    "CORNERST",
    "CUSTODIAN",
    "CUTIX",
    "CWG",
    "DAARCOMM",
    "DANGCEM",
    "DANGSUGAR",
    "EKOCORP",
    "ELLAHLAKES",
    "ENAMELWA",
    "ETERNA",
    "ETI",
    "ETRANZACT",
    "EUNISELL",
    "FCMB",
    "FIDELITYBK",
    "FIDSON",
    "FIRSTHOLDCO",
    "FTGINSURE",
    "FTNCOCOA",
    "GEREGU",
    "GOLDBREW",
    "GTCO",
    "GUINEAINS",
    "GUINNESS",
    "HBMNG",
    "HMCALL",
    "HONYFLOUR",
    "IKEJAHOTEL",
    "IMG",
    "INFINITY",
    "INTBREW",
    "INTENEGINS",
    "JAIZBANK",
    "JAPAULGOLD",
    "JBERGER",
    "JOHNHOLT",
    "JULI",
    "LASACO",
    "LEARNAFRCA",
    "LEGENDINT",
    "LINKASSURE",
    "LIVESTOCK",
    "LIVINGTRUST",
    "MANSARD",
    "MAYBAKER",
    "MBENEFIT",
    "MCNICHOLS",
    "MECURE",
    "MEYER",
    "MORISON",
    "MTNN",
    "MULTITREX",
    "MULTIVERSE",
    "NAHCO",
    "NASCON",
    "NB",
    "NCR",
    "NEIMETH",
    "NEM",
    "NESTLE",
    "NGXGROUP",
    "NIDF",
    "NNFM",
    "NPFMCRFBK",
    "NREIT",
    "NSLTECH",
    "OANDO",
    "OKOMUOIL",
    "OMATEK",
    "PREMPAINTS",
    "PRESCO",
    "PRESTIGE",
    "PZ",
    "REDSTAREX",
    "REGALINS",
    "ROYALEX",
    "RTBRISCOE",
    "SCOA",
    "SEPLAT",
    "SFSREIT",
    "SKYAVN",
    "SOVRENINS",
    "STANBIC",
    "STERLINGNG",
    "SUNUASSUR",
    "TANTALIZER",
    "THOMASWY",
    "TIP",
    "TOTAL",
    "TRANSCOHOT",
    "TRANSCORP",
    "TRANSEXPR",
    "TRANSPOWER",
    "TRIPPLEG",
    "UACN",
    "UBA",
    "UCAP",
    "UHREIT",
    "UNILEVER",
    "UNIONDICON",
    "UNITYBNK",
    "UPDC",
    "UPDCREIT",
    "UPL",
    "VERITASKAP",
    "VFDGROUP",
    "VITAFOAM",
    "WAPIC",
    "WEMABANK",
    "ZENITHBANK",
    "ZICHIS",
]

symbols = list(FALLBACK_SYMBOLS)
# Our symbol -> TradingView ticker on NSENG (identical unless TradingView lags a rename)
tv_tickers = {}
_symbols_loaded_for = None


def refresh_symbols():
    """Load active symbols from the backend once per Lagos day."""
    global symbols, tv_tickers, _symbols_loaded_for
    today = datetime.now(lagos_tz).date()
    if _symbols_loaded_for == today:
        return

    rows = None
    try:
        response = requests.get(SYMBOLS_API_URL, timeout=30)
        response.raise_for_status()
        rows = response.json()
        with open(SYMBOLS_CACHE_FILE, "w") as f:
            json.dump(rows, f)
    except Exception as e:
        print(f"Could not load symbols from backend ({e}); trying cached copy")
        try:
            with open(SYMBOLS_CACHE_FILE) as f:
                rows = json.load(f)
        except Exception:
            rows = None

    if rows:
        # Stocks without a TradingView symbol cannot be fetched; skip them
        priced = [row for row in rows if row.get("tv_symbol")]
        symbols = [row["symbol"] for row in priced]
        tv_tickers = {
            row["symbol"]: row["tv_symbol"].split(":", 1)[-1] for row in priced
        }
    else:
        print("Using built-in fallback symbol list")
        symbols = list(FALLBACK_SYMBOLS)
        tv_tickers = {}

    _symbols_loaded_for = today
    print(f"Tracking {len(symbols)} symbols")


def tv_ticker(symbol):
    return tv_tickers.get(symbol, symbol)



def safe_float(value):
    """
    Returns a safe float value. Converts `inf` and `NaN` to None or a default value.
    """
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
    return value


_trading_day_cache = {}


def is_trading_day(day):
    """Weekday and not an NGX holiday (holidays come from the backend; assume open on error)."""
    if day.weekday() >= 5:
        return False
    if day in _trading_day_cache:
        return _trading_day_cache[day]
    try:
        response = requests.get(MARKET_STATUS_API_URL, timeout=15)
        response.raise_for_status()
        status = response.json()
        trading = status.get("reason") != "holiday"
        _trading_day_cache[day] = trading
        return trading
    except Exception as e:
        print(f"Could not check market status ({e}); assuming trading day")
        return True


def is_market_open():
    """True inside the collection window (09:30 to just after the close run) on trading days."""
    try:
        now = datetime.now(lagos_tz)
        window_end = (
            datetime.combine(now.date(), CLOSE_RUN) + timedelta(minutes=5)
        ).time()
        return FIRST_SLOT <= now.time() <= window_end and is_trading_day(now.date())
    except Exception as e:
        print(f"Error checking market hours: {e}")
        return False


def get_live_data_from_tradingview(symbol):
    """
    Latest price from TradingView daily bars.

    change/percent are the latest daily bar against the one before it, as the
    TradingView chart shows them. If the stock has not traded today, that is
    the last session's change; volume is 0.
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            data = tv.get_hist(
                symbol=tv_ticker(symbol),
                exchange="NSENG",
                interval=Interval.in_daily,
                n_bars=2,
            )
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {symbol}: {e}")
            data = None

        if data is not None and not data.empty:
            bars = data.reset_index()
            latest = bars.iloc[-1]
            previous = bars.iloc[-2] if len(bars) > 1 else latest
            close = float(latest["close"])
            if close <= 0:
                return None

            lagos_now = datetime.now(lagos_tz)
            bar_date = pd.Timestamp(latest["datetime"]).date()
            traded_today = bar_date >= lagos_now.date()

            # Same as the TradingView chart: the latest bar against the bar
            # before it, even when the latest bar is from an earlier session.
            prev_close = float(previous["close"])
            if prev_close > 0 and len(bars) > 1:
                change = close - prev_close
                percent = change / prev_close * 100
            else:
                change = 0.0
                percent = 0.0
            # Volume stays today's only.
            if traded_today and not pd.isna(latest["volume"]):
                volume = int(latest["volume"])
            else:
                volume = 0

            stamp = lagos_now.strftime("%Y-%m-%d %H:%M:%S")
            return {
                "datetime": stamp,
                "as_of": stamp,
                "last_trade_date": bar_date.isoformat(),
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "close": close,
                "volume": volume,
                "symbol": symbol,
                "change": round(change, 2),
                "percent": round(percent, 2),
                "is_stale": False,
            }

        if attempt < max_retries - 1:
            module_time.sleep(1)

    return None


def ensure_all_symbols_included(live_data, volatility_data, merged_data):
    """Ensure all symbols from the symbols list are included in the datasets"""
    try:
        # Check if any symbols are missing from live_data
        missing_from_live = [s for s in symbols if s not in live_data]
        for symbol in missing_from_live:
            fallback = get_last_available_live_data(symbol)
            if fallback:
                print(f"Adding fallback live data for missing symbol: {symbol}")
                live_data[symbol] = fallback

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
    """
    Last good (non-zero) price for symbol, marked stale, or None.

    Never returns a 0 price. The carried-forward price gets change/percent 0 so
    an old move is not shown as today's.
    """
    try:
        doc = collection_latest.find_one({"_id": symbol})
        if not (doc and doc.get("close")):
            # Snapshots are keyed by symbol: {SYMBOL: {...}}
            snapshot = collection_merged.find_one(
                {f"{symbol}.current_price": {"$gt": 0}},
                sort=[("_id", -1)],
                projection={symbol: 1},
            )
            doc = (snapshot or {}).get(symbol)
            if doc:
                doc = dict(doc, close=doc.get("close") or doc.get("current_price"))
        if not (doc and doc.get("close")):
            return None

        lagos_now = datetime.now(lagos_tz)
        return {
            "datetime": lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
            "as_of": doc.get("as_of") or doc.get("datetime"),
            "last_trade_date": doc.get("last_trade_date"),
            "open": doc.get("open", doc["close"]),
            "high": doc.get("high", doc["close"]),
            "low": doc.get("low", doc["close"]),
            "close": doc["close"],
            "volume": 0,
            "symbol": symbol,
            "change": 0,
            "percent": 0,
            "is_fallback": True,
            "is_stale": True,
        }
    except Exception as e:
        print(f"Error getting last available data for {symbol}: {e}")
        return None


def get_last_available_volatility_data(symbol):
    """Get the last available volatility data for a symbol from database"""
    try:
        # Try to get from price_combined collection
        last_data = collection_price_combined.find_one(
            {"symbol": symbol},
            sort=[("_id", -1)],
            projection={"_id": 0},  # Exclude MongoDB ID but get all other fields
        )

        if last_data and isinstance(last_data, dict):
            last_data.pop("_id", None)  # Remove MongoDB ID if it exists
            last_data["is_fallback"] = True

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

        return default_volatility_data


_known_symbols = None


def is_first_entry(symbol):
    """True the first time we ever store a price for symbol (known set loaded once)."""
    global _known_symbols
    if _known_symbols is None:
        try:
            _known_symbols = set(collection_latest.distinct("_id"))
            latest = collection_merged.find_one(sort=[("_id", -1)]) or {}
            _known_symbols.update(k for k in latest if k != "_id")
        except Exception as e:
            print(f"Could not load known symbols: {e}")
            _known_symbols = set()
    first = symbol not in _known_symbols
    _known_symbols.add(symbol)
    return first


def get_all_live_data():
    """Get live data for all symbols from TradingView with fallback to last available data"""
    combined = {}
    failed_symbols = []
    first_time_symbols = []

    for i, symbol in enumerate(symbols):
        print(f"Fetching live data for {symbol}")
        data = get_live_data_from_tradingview(symbol)
        if data:
            # Check if this is the first entry for this symbol
            if is_first_entry(symbol):
                first_time_symbols.append(symbol)
                # For first entry, change/percent should be 0 since there's no previous value in our system
                # (TradingView's change is relative to their previous bar, but for our system it's the first)
                data["change"] = 0
                data["percent"] = 0
                data["is_first_entry"] = True
                print(
                    f"First entry detected for {symbol} - setting change/percent to 0"
                )
            combined[symbol] = data
        else:
            print(f"Failed to get fresh data for {symbol}, using fallback")
            failed_symbols.append(symbol)
            fallback_data = get_last_available_live_data(symbol)
            if fallback_data:
                combined[symbol] = fallback_data

        # Add small delay between requests to avoid overwhelming the API
        if i < len(symbols) - 1:  # Don't delay after the last symbol
            module_time.sleep(0.5)

    if failed_symbols:
        print(f"Used fallback data for {len(failed_symbols)} symbols: {failed_symbols}")

    if first_time_symbols:
        print(
            f"First-time entries detected for {len(first_time_symbols)} symbols: {first_time_symbols}"
        )

    return combined


_cap_cache = {"day": None, "values": {}}


def get_symbol_cap(symbol):
    """
    Shares outstanding for symbol. Loaded for all stocks once per day from the
    backend (CompanyProfile in Postgres); falls back to the old Mongo collection.
    """
    today = datetime.now(lagos_tz).date()
    if _cap_cache["day"] != today:
        _cap_cache["day"] = today
        _cap_cache["values"] = {}
        try:
            response = requests.get(f"{BACKEND_URL}/portfolio/shares-outstanding/", timeout=30)
            response.raise_for_status()
            _cap_cache["values"] = {
                key: float(value or 0) for key, value in response.json().items()
            }
        except Exception as e:
            print(f"Could not load shares outstanding from backend: {e}")
    if symbol in _cap_cache["values"]:
        return _cap_cache["values"][symbol]

    shares = 0
    try:
        data = db_cap[symbol].find_one({}, projection={"SharesOutstanding": 1, "_id": 0})
        if data and data.get("SharesOutstanding") is not None:
            shares = float(data["SharesOutstanding"])
    except Exception as e:
        print(f"Market cap data not available for {symbol}: {e}")
    _cap_cache["values"][symbol] = shares
    return shares


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
                    symbol=tv_ticker(symbol),
                    exchange="NSENG",
                    interval=interval,
                    n_bars=n_bars,
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


def _apply_vol_mom_tuple(data_metrics, keys, vol_mom):
    """Map a (vol, mom, mom_chg, vol_mom, vol_mom_chg) tuple onto metric keys."""
    for i, key in enumerate(keys):
        data_metrics[key] = vol_mom[i] if vol_mom else None


def calculate_daily_horizon_metrics(symbol, data_metrics):
    """Calculate once-per-day long-horizon volatility/momentum metrics."""
    daily_1y_keys = [
        "volatility_1year",
        "momentum_1year",
        "momentum_change_1year",
        "volume_momentum_1year",
        "volume_momentum_change_1year",
    ]
    daily_ytd_keys = [
        "volatility_ytd",
        "momentum_ytd",
        "momentum_change_ytd",
        "volume_momentum_ytd",
        "volume_momentum_change_ytd",
    ]
    daily_1m_keys = [
        "volatility",
        "momentum",
        "momentum_change",
        "volume_momentum",
        "volume_momentum_change",
    ]
    daily_1w_keys = [
        "volatility_1week",
        "momentum_1week",
        "momentum_change_1week",
        "volume_momentum_1week",
        "volume_momentum_change_1week",
    ]

    # 1-year calculations using daily data
    data_1year = get_historical_data_for_period(symbol, 365)
    if data_1year is not None and not data_1year.empty:
        vol_mom_1year = calculate_volatility_momentum(data_1year, 365)
        _apply_vol_mom_tuple(data_metrics, daily_1y_keys, vol_mom_1year)

        # Year-to-date calculations
        current_year = datetime.now().year
        try:
            if hasattr(data_1year.index, "year"):
                data_ytd = data_1year[data_1year.index.year == current_year]
            else:
                datetime_index = pd.to_datetime(data_1year.index)
                data_ytd = data_1year[datetime_index.year == current_year]

            if not data_ytd.empty:
                ytd_days = (datetime.now() - datetime(current_year, 1, 1)).days
                vol_mom_ytd = calculate_volatility_momentum(data_ytd, ytd_days)
                _apply_vol_mom_tuple(data_metrics, daily_ytd_keys, vol_mom_ytd)
            else:
                for metric in daily_ytd_keys:
                    data_metrics[metric] = None
        except Exception as ytd_error:
            print(f"Error calculating YTD metrics for {symbol}: {ytd_error}")
            for metric in daily_ytd_keys:
                data_metrics[metric] = None
    else:
        for metric in daily_1y_keys + daily_ytd_keys:
            data_metrics[metric] = None

    # 1-month calculations using daily data
    data_1month = get_historical_data_for_period(symbol, 30)
    if data_1month is not None and not data_1month.empty:
        vol_mom_1month = calculate_volatility_momentum(data_1month, 30)
        _apply_vol_mom_tuple(data_metrics, daily_1m_keys, vol_mom_1month)
    else:
        for metric in daily_1m_keys:
            data_metrics[metric] = None

    # 1-week calculations using hourly data
    data_1week = get_historical_data_for_period(symbol, 7)
    if data_1week is not None and not data_1week.empty:
        vol_mom_1week = calculate_volatility_momentum(data_1week, 7)
        _apply_vol_mom_tuple(data_metrics, daily_1w_keys, vol_mom_1week)
    else:
        for metric in daily_1w_keys:
            data_metrics[metric] = None


def calculate_24hr_metrics(symbol, data_metrics):
    """Calculate 24hr volatility/momentum metrics (intraday refresh cadence)."""
    data_24hr = get_historical_data_for_period(symbol, 1)
    if data_24hr is not None and not data_24hr.empty:
        vol_mom_24hr = calculate_volatility_momentum_24hr(symbol, data_24hr)
        _apply_vol_mom_tuple(data_metrics, INTRADAY_METRIC_KEYS, vol_mom_24hr)
    else:
        for metric in INTRADAY_METRIC_KEYS:
            data_metrics[metric] = None


def calculate_comprehensive_metrics(
    symbol, refresh_daily=True, refresh_intraday=True, existing=None
):
    """
    Calculate volatility/momentum metrics with dual-TTL refresh.

    - refresh_daily: recompute 1y / YTD / 1m / 1w (once per Lagos day)
    - refresh_intraday: recompute 24hr metrics (every 90 minutes)
    - existing: prior cached metrics to reuse for layers that are still valid
    """
    if existing and not refresh_daily and not refresh_intraday:
        data_metrics = dict(existing)
        live_data = get_live_data_from_tradingview(symbol)
        if live_data:
            data_metrics["current_price"] = live_data["close"]
            try:
                data_metrics["market_cap"] = get_symbol_cap(symbol) * live_data["close"]
            except Exception:
                data_metrics["market_cap"] = 0
        return data_metrics

    layers = []
    if refresh_daily:
        layers.append("daily")
    if refresh_intraday:
        layers.append("24hr")
    print(
        f"Calculating volatility metrics for {symbol} "
        f"({'+'.join(layers) or 'price-only'})"
    )

    data_metrics = dict(existing) if existing else {"symbol": symbol}
    data_metrics["symbol"] = symbol

    try:
        live_data = get_live_data_from_tradingview(symbol)
        current_price = live_data["close"] if live_data else 0
        data_metrics["current_price"] = current_price

        if refresh_daily:
            calculate_daily_horizon_metrics(symbol, data_metrics)

        if refresh_intraday:
            calculate_24hr_metrics(symbol, data_metrics)

        try:
            data_metrics["market_cap"] = get_symbol_cap(symbol) * current_price
        except Exception:
            data_metrics["market_cap"] = 0

        volatility_cache.set_cached_data(
            symbol,
            data_metrics,
            updated_daily=refresh_daily,
            updated_intraday=refresh_intraday,
        )
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

        merged_data["is_stale"] = bool(live_info.get("is_stale"))
        merged_data["as_of"] = live_info.get("as_of") or live_info["datetime"]
        merged_data["last_trade_date"] = live_info.get("last_trade_date")
        combined[symbol] = merged_data

    return combined


def save_data(live_data, volatility_data, merged_data):
    """Save data directly to database without batching or caching"""
    try:
        saved_counts = {"live": 0, "volatility": 0, "merged": 0}

        # Save live data directly
        if live_data and isinstance(live_data, dict) and len(live_data) > 0:
            # Filter out _id and check if there's actual data
            data_to_save = {k: v for k, v in live_data.items() if k != "_id"}
            if data_to_save:
                try:
                    collection_live.insert_one(data_to_save)
                    saved_counts["live"] = len(data_to_save)
                    print(f"Saved live data for {len(data_to_save)} symbols")
                    save_latest_prices(data_to_save)
                except Exception as live_error:
                    print(f"Error saving live data: {live_error}")

        # Save volatility data directly
        if (
            volatility_data
            and isinstance(volatility_data, dict)
            and len(volatility_data) > 0
        ):
            volatility_documents = []
            for symbol, vol_data in volatility_data.items():
                if isinstance(vol_data, dict) and not vol_data.get(
                    "is_fallback", False
                ):  # Only save fresh data
                    # Add timestamp for tracking and remove any existing _id to avoid duplicates
                    vol_data_with_timestamp = vol_data.copy()
                    vol_data_with_timestamp.pop(
                        "_id", None
                    )  # Remove existing _id if present
                    vol_data_with_timestamp["timestamp"] = datetime.now(
                        lagos_tz
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    volatility_documents.append(vol_data_with_timestamp)

            # Direct insert volatility data
            if volatility_documents:
                try:
                    collection_price_combined.insert_many(volatility_documents)
                    saved_counts["volatility"] = len(volatility_documents)
                    print(f"Saved {len(volatility_documents)} fresh volatility records")
                except Exception as vol_error:
                    print(f"Error saving volatility data: {vol_error}")

        # Save merged data directly
        if merged_data and isinstance(merged_data, dict) and len(merged_data) > 0:
            try:
                # Create the combined document like in merge_price4.py
                combined_document = {}
                for symbol, merged_info in merged_data.items():
                    if isinstance(merged_info, dict):
                        # Remove symbol key from individual data since it becomes the key
                        symbol_data = merged_info.copy()
                        symbol_data.pop(
                            "symbol", None
                        )  # Remove symbol field as it's now the key
                        combined_document[symbol] = symbol_data

                # Only insert if we have actual data
                if combined_document:
                    collection_merged.insert_one(combined_document)
                    saved_counts["merged"] = len(combined_document)
                    print(
                        f"Saved combined merged document with {len(combined_document)} symbols"
                    )
                else:
                    print("No valid merged data to save")
            except Exception as merge_error:
                print(f"Error saving combined merged data: {merge_error}")
                saved_counts["merged"] = 0

        return saved_counts

    except Exception as e:
        print(f"Error in save operation: {e}")
        return {"live": 0, "volatility": 0, "merged": 0}


def save_latest_prices(live_data):
    """Upsert one document per symbol with its latest fresh, non-zero price."""
    from pymongo import ReplaceOne

    operations = []
    for symbol, info in live_data.items():
        if not isinstance(info, dict) or info.get("is_stale") or not info.get("close"):
            continue
        doc = {
            "symbol": symbol,
            "current_price": info["close"],
            "close": info["close"],
            "open": info.get("open"),
            "high": info.get("high"),
            "low": info.get("low"),
            "volume": info.get("volume"),
            "change": info.get("change"),
            "percentage_change": info.get("percent"),
            "as_of": info.get("as_of") or info.get("datetime"),
            "last_trade_date": info.get("last_trade_date"),
        }
        operations.append(ReplaceOne({"_id": symbol}, doc, upsert=True))
    if operations:
        try:
            collection_latest.bulk_write(operations, ordered=False)
        except Exception as e:
            print(f"Error saving latest prices: {e}")


def apply_retention():
    """Delete snapshots/history older than RETENTION_DAYS and old per-day collections."""
    from bson import ObjectId

    cutoff = datetime.now(pytz.UTC) - timedelta(days=RETENTION_DAYS)
    cutoff_id = ObjectId.from_datetime(cutoff)
    for collection in (collection_live, collection_merged, collection_price_combined):
        try:
            result = collection.delete_many({"_id": {"$lt": cutoff_id}})
            print(f"Retention: removed {result.deleted_count} from {collection.name}")
        except Exception as e:
            print(f"Retention failed for {collection.name}: {e}")

    cutoff_name = cutoff.date().isoformat()
    for name in db_live.list_collection_names():
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", name) and name < cutoff_name:
            db_live.drop_collection(name)
            print(f"Retention: dropped per-day collection {name}")


def get_combined():
    """
    Get combined data similar to merge_price4.py format.

    Behavior with missing data:
    - If live_data is None/empty: returns empty dict {}
    - If volatile_data is None/empty: uses default values (0) for all volatility metrics
    - If symbol not in volatile_data: uses default values (0) for that symbol's volatility metrics
    - All missing data scenarios are handled gracefully without errors
    """
    try:
        # Get latest volatility data from TradingView price combined collection
        volatile_data = collection_price_combined.find_one(sort=[("_id", -1)])
        if volatile_data is None:
            print("No volatility data found in database (collection may be empty)")
        else:
            print("volatile data gotten")

        # Get latest live data from TradingView live collection
        live_data = collection_live.find_one(sort=[("_id", -1)])
        if live_data is None:
            print("No live data found in database (collection may be empty)")
        else:
            print("live data gotten")

        if not live_data or not isinstance(live_data, dict):
            print("No live data available or invalid format")
            return {}

        # Check if live_data is empty (only has _id or is truly empty)
        if len([k for k in live_data.keys() if k != "_id"]) == 0:
            print("Live data is empty (no symbols found)")
            return {}

        # Combined data storage
        combined = {}

        # Process each symbol in live_data except '_id'
        for symbol, data in live_data.items():
            if symbol != "_id" and isinstance(data, dict):
                # Find volatility data for this symbol
                data2 = None
                if volatile_data and isinstance(volatile_data, dict):
                    if symbol in volatile_data:
                        potential_data = volatile_data[symbol]
                        if isinstance(potential_data, dict):
                            data2 = potential_data
                    else:
                        # Look for symbol field in the volatile data structure
                        if (
                            "symbol" in volatile_data
                            and volatile_data["symbol"] == symbol
                        ):
                            data2 = volatile_data
                        else:
                            # Try to find symbol data in a different structure
                            for key, value in volatile_data.items():
                                if key == "_id":
                                    continue  # Skip ObjectId
                                if (
                                    isinstance(value, dict)
                                    and value.get("symbol") == symbol
                                ):
                                    data2 = value
                                    break

                if data2 and isinstance(data2, dict):
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
    """Main execution cycle - fresh live data; dual-TTL vol/momentum cache."""
    if not is_market_open():
        print("Market closed")
        return

    print(
        "Market is open - Starting data collection "
        "(live: fresh, daily metrics: once/day, 24hr metrics: 90min cache)"
    )

    refresh_symbols()

    # Clear entries from previous Lagos days
    volatility_cache.clear_expired_cache()

    # Get cache statistics
    cache_stats = volatility_cache.get_cache_stats()
    print(
        f"Cache status: {cache_stats['valid_entries']} fully valid, "
        f"{cache_stats['daily_valid']} daily valid, "
        f"{cache_stats['intraday_valid']} 24hr valid, "
        f"{cache_stats['total_entries']} total"
    )

    # Step 1: Get live data for all symbols - always fresh
    print("Step 1: Fetching live data from TradingView...")
    live_data = get_all_live_data()

    if not live_data or not isinstance(live_data, dict) or len(live_data) == 0:
        print("No live data retrieved or empty dataset")
        print("This could indicate:")
        print("  - TradingView API is unavailable")
        print("  - Network connectivity issues")
        print("  - All symbols failed to fetch")
        return

    # Step 2: Calculate volatility metrics with dual-TTL caching
    print(
        "Step 2: Calculating volatility and momentum metrics "
        "(daily once/day, 24hr every 90min)..."
    )
    volatility_data = {}
    failed_volatility_symbols = []
    full_cache_hits = 0
    daily_refreshes = 0
    intraday_only_refreshes = 0
    deferred_intraday = 0

    for i, symbol in enumerate(symbols):
        needs = volatility_cache.get_refresh_needs(symbol)
        need_daily = needs["need_daily"]
        need_intraday = needs["need_intraday"]
        existing = needs["data"]

        if not need_daily and not need_intraday and existing:
            full_cache_hits += 1
            volatility_data[symbol] = dict(existing)
            if symbol in live_data:
                volatility_data[symbol]["current_price"] = live_data[symbol]["close"]
                try:
                    volatility_data[symbol]["market_cap"] = (
                        get_symbol_cap(symbol) * live_data[symbol]["close"]
                    )
                except Exception:
                    volatility_data[symbol]["market_cap"] = 0
            print(f"Using fully cached metrics for {symbol}")
            continue

        if (
            not need_daily
            and existing
            and intraday_only_refreshes >= MAX_INTRADAY_REFRESH_PER_CYCLE
        ):
            # Defer: reuse the previous 24hr metrics; this symbol refreshes next cycle
            deferred_intraday += 1
            volatility_data[symbol] = dict(existing)
            if symbol in live_data:
                volatility_data[symbol]["current_price"] = live_data[symbol]["close"]
            continue

        if need_daily or existing is None:
            daily_refreshes += 1
            # Daily miss (or missing data) implies a full recompute including 24hr
            refresh_daily = True
            refresh_intraday = True
            print(f"Daily cache miss for {symbol} - recalculating all horizons")
        else:
            intraday_only_refreshes += 1
            refresh_daily = False
            refresh_intraday = True
            print(f"24hr cache miss for {symbol} - recalculating 24hr only")

        metrics = calculate_comprehensive_metrics(
            symbol,
            refresh_daily=refresh_daily,
            refresh_intraday=refresh_intraday,
            existing=existing,
        )
        if metrics:
            volatility_data[symbol] = metrics
            print(f"Successfully calculated metrics for {symbol}")
        else:
            print(f"API call failed for {symbol}, using fallback data")
            failed_volatility_symbols.append(symbol)
            fallback_metrics = get_last_available_volatility_data(symbol)
            volatility_data[symbol] = fallback_metrics

        # Delay only when we hit TradingView historical endpoints
        if i < len(symbols) - 1:
            module_time.sleep(2)

    total_lookups = full_cache_hits + daily_refreshes + intraday_only_refreshes
    hit_rate = (full_cache_hits / total_lookups * 100) if total_lookups else 0.0
    print(
        f"Cache performance: {full_cache_hits} full hits, "
        f"{daily_refreshes} daily refreshes, "
        f"{intraday_only_refreshes} 24hr-only refreshes "
        f"(full-hit rate: {hit_rate:.1f}%)"
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

    # Step 4: Save data using direct database operations
    print("Step 4: Saving data...")
    saved_counts = save_data(live_data, volatility_data, merged_data)

    # Step 5: Save cache to disk
    volatility_cache.save_cache()

    print(f"Data cycle completed successfully - {len(live_data)} symbols processed")
    print(
        f"Saved - Live: {saved_counts['live']}, Volatility: {saved_counts['volatility']}, Merged: {saved_counts['merged']}"
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
        f"Volatility cache: {full_cache_hits} full hits, "
        f"{daily_refreshes} daily, {intraday_only_refreshes} 24hr-only"
    )
    print(
        f"Total symbols expected: {len(symbols)}, Total symbols saved: {len(merged_data)}"
    )

    if len(merged_data) != len(symbols):
        missing_symbols = [s for s in symbols if s not in merged_data]
        print(f"WARNING: Missing symbols in final dataset: {missing_symbols}")


def _todays_slots(day):
    slots = []
    current = datetime.combine(day, FIRST_SLOT)
    last = datetime.combine(day, LAST_SLOT)
    while current <= last:
        slots.append(current.time())
        current += timedelta(minutes=SLOT_MINUTES)
    slots.append(CLOSE_RUN)
    return slots


def next_run_time(now):
    """Next scheduled slot (Lagos time) after now."""
    day = now.date()
    for _ in range(10):
        if day.weekday() >= 5:
            day += timedelta(days=1)
            continue
        for slot in _todays_slots(day):
            candidate = lagos_tz.localize(datetime.combine(day, slot))
            if candidate > now:
                return candidate
        day += timedelta(days=1)
    return now + timedelta(minutes=SLOT_MINUTES)


def run_unified_system():
    """Run collection on fixed Lagos-time slots on trading days."""
    print("=" * 80)
    print("Starting Unified Price System")
    print(
        f"Slots: every {SLOT_MINUTES} min {FIRST_SLOT:%H:%M}-{LAST_SLOT:%H:%M}, "
        f"close run {CLOSE_RUN:%H:%M} (Africa/Lagos); retention {RETENTION_DAYS} days"
    )
    print("=" * 80)

    if not verify_mongodb_connection():
        print("FATAL: Cannot proceed without MongoDB connection")
        return

    while True:
        try:
            run_at = next_run_time(datetime.now(lagos_tz))
            wait = (run_at - datetime.now(lagos_tz)).total_seconds()
            print(f"Next run at {run_at:%Y-%m-%d %H:%M} ({wait / 60:.0f} min)")
            if wait > 0:
                module_time.sleep(wait)

            if not is_trading_day(run_at.date()):
                print(f"{run_at:%Y-%m-%d} is not a trading day - skipping")
                continue

            lagos_now = datetime.now(lagos_tz)
            if (lagos_now - run_at).total_seconds() > SLOT_MINUTES * 60:
                print("Missed this slot (previous cycle overran) - skipping")
                continue

            print("=" * 60)
            print(f"Starting data fetch at {lagos_now:%Y-%m-%d %H:%M:%S}")
            main_cycle()
            print(f"Cycle finished at {datetime.now(lagos_tz):%H:%M:%S}")
            print("=" * 60)

            if run_at.time() == CLOSE_RUN:
                apply_retention()

        except KeyboardInterrupt:
            print("System stopped by user")
            volatility_cache.save_cache()
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            module_time.sleep(60)


def clear_volatility_cache():
    """Utility function to manually clear the volatility cache"""
    global volatility_cache
    volatility_cache.cache = {}
    volatility_cache.save_cache()
    print("Volatility cache cleared")


def get_cache_info():
    """Get detailed cache information"""
    stats = volatility_cache.get_cache_stats()
    print(f"Volatility Cache Information:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Fully valid entries: {stats['valid_entries']}")
    print(f"  Daily-valid entries: {stats['daily_valid']}")
    print(f"  24hr-valid entries: {stats['intraday_valid']}")
    print(f"  Expired / partial entries: {stats['expired_entries']}")
    print(
        f"  Daily TTL: until next Lagos calendar day "
        f"(today={VolatilityCache.lagos_today()})"
    )
    print(
        f"  24hr TTL: {INTRADAY_CACHE_DURATION/60:.0f} minutes "
        f"({INTRADAY_CACHE_DURATION/3600:.2f} hours)"
    )

    if stats["total_entries"] > 0:
        print(
            f"  Full-hit potential: {stats['valid_entries']/stats['total_entries']*100:.1f}%"
        )

    return stats


def force_cache_refresh(symbol=None):
    """Force refresh cache for a specific symbol or all symbols"""
    if symbol:
        if symbol in volatility_cache.cache:
            del volatility_cache.cache[symbol]
            print(f"Cleared cache for {symbol}")
        else:
            print(f"No cache entry found for {symbol}")
    else:
        volatility_cache.cache = {}
        print("Cleared all cache entries")

    volatility_cache.save_cache()


if __name__ == "__main__":
    run_unified_system()

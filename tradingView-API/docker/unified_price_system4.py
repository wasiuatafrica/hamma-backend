import json
import logging
import math
import os
import tempfile
import time as module_time
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import pytz
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from tvDatafeed import Interval, TvDatafeed

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment & MongoDB
# ---------------------------------------------------------------------------
load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")
client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

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

# Cache duration for volatility data
VOLATILITY_CACHE_DURATION = 5400  # 90 minutes in seconds

# How many days of data to keep in MongoDB (set to 0 to disable cleanup)
DATA_RETENTION_DAYS = 30


# ---------------------------------------------------------------------------
# MongoDB indexes & verification
# ---------------------------------------------------------------------------
def ensure_indexes():
    """Create indexes on MongoDB collections to speed up queries."""
    try:
        collection_merged.create_index([("symbol", ASCENDING)])
        collection_price_combined.create_index([("symbol", ASCENDING)])
        collection_price_combined.create_index([("timestamp", DESCENDING)])
        collection_live.create_index([("_id", DESCENDING)])
        logger.info("MongoDB indexes ensured")
    except Exception as e:
        logger.warning("Could not create indexes (non-fatal): %s", e)


def verify_mongodb_connection():
    """Verify MongoDB connection and log cluster status."""
    try:
        client.admin.command("ping")
        logger.info("MongoDB connection successful")
        databases = client.list_database_names()
        logger.info("Connected to MongoDB cluster with %d databases", len(databases))

        for db_name in ("stock_prices_trdv", "livelake3", "ngxlistedcompanies"):
            if db_name in databases:
                count = len(client[db_name].list_collection_names())
                logger.info("  - %s: %d collections", db_name, count)
            else:
                logger.info("  - %s: will be created on first insert", db_name)

        ensure_indexes()
        return True
    except Exception as e:
        logger.error("MongoDB connection failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# JSON-based volatility cache (replaces pickle)
# ---------------------------------------------------------------------------
class VolatilityCache:
    """Cache volatility metrics per symbol with a configurable TTL.

    Uses JSON for serialization (safe, human-readable, cross-version compatible).
    Writes are atomic via tempfile + os.replace to prevent corruption on crash.
    """

    def __init__(self):
        self.cache: dict = {}
        self.cache_file = "volatility_cache.json"
        self._load_cache()

    # -- persistence ----------------------------------------------------------

    def _load_cache(self):
        """Load cache from disk if it exists."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    self.cache = json.load(f)
                logger.info("Loaded volatility cache with %d entries", len(self.cache))
            else:
                self.cache = {}
        except Exception as e:
            logger.warning("Error loading cache, starting fresh: %s", e)
            self.cache = {}

    def save_cache(self):
        """Atomically save cache to disk (write tmp → rename)."""
        try:
            dir_name = os.path.dirname(os.path.abspath(self.cache_file))
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.cache, f)
                os.replace(tmp_path, self.cache_file)
            except BaseException:
                os.unlink(tmp_path)
                raise
            logger.debug("Saved volatility cache with %d entries", len(self.cache))
        except Exception as e:
            logger.warning("Error saving cache: %s", e)

    # -- read / write ---------------------------------------------------------

    def is_cache_valid(self, symbol):
        """Check if cached data is still valid (younger than VOLATILITY_CACHE_DURATION)."""
        if symbol not in self.cache:
            return False
        cached_time = self.cache[symbol].get("timestamp", 0)
        return (module_time.time() - cached_time) < VOLATILITY_CACHE_DURATION

    def get_cached_data(self, symbol):
        """Return cached volatility dict for *symbol*, or None if expired/missing."""
        if self.is_cache_valid(symbol):
            logger.debug("Cache HIT for %s", symbol)
            return self.cache[symbol]["data"]
        return None

    def set_cached_data(self, symbol, data):
        """Store volatility data for *symbol* with current timestamp."""
        self.cache[symbol] = {"data": data, "timestamp": module_time.time()}
        logger.debug("Cached volatility data for %s", symbol)

    # -- maintenance ----------------------------------------------------------

    def clear_expired(self):
        """Remove entries older than the cache duration."""
        now = module_time.time()
        expired = [
            s
            for s, entry in self.cache.items()
            if (now - entry.get("timestamp", 0)) >= VOLATILITY_CACHE_DURATION
        ]
        for s in expired:
            del self.cache[s]
        if expired:
            logger.info("Cleared %d expired cache entries", len(expired))
            self.save_cache()

    def get_stats(self):
        """Return dict with total / valid / expired counts."""
        total = len(self.cache)
        valid = sum(1 for s in self.cache if self.is_cache_valid(s))
        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
        }


# Global cache instance
volatility_cache = VolatilityCache()


# ---------------------------------------------------------------------------
# Stock symbols
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_float(value):
    """Return *value* unchanged unless it is inf/NaN, in which case return None."""
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    return value


def is_market_open():
    """Check if the NGX market is currently open (10:00 AM – 2:30 PM Lagos, weekdays)."""
    try:
        now = datetime.now(pytz.timezone("Africa/Lagos")).time()
        if datetime.today().weekday() < 5:
            return time(10, 0) <= now <= time(14, 36)
        return False
    except Exception as e:
        logger.error("Error checking market hours: %s", e)
        return False


# ---------------------------------------------------------------------------
# Batch MongoDB helpers (Phase 3)
# ---------------------------------------------------------------------------
def get_existing_symbols_batch():
    """Return the set of symbols that already have data in MongoDB.

    Replaces per-symbol ``is_first_entry()`` queries with two aggregation
    pipelines, reducing ~280 round-trips to 2.
    """
    existing: set = set()
    try:
        # Symbols present in merged collection
        pipeline = [{"$group": {"_id": "$symbol"}}, {"$project": {"_id": 1}}]
        for doc in collection_merged.aggregate(pipeline):
            if doc.get("_id"):
                existing.add(doc["_id"])

        # Symbols present as keys in live collection (keys vary per document)
        latest_live = collection_live.find_one(sort=[("_id", -1)])
        if latest_live and isinstance(latest_live, dict):
            existing.update(k for k in latest_live if k != "_id")
    except Exception as e:
        logger.warning("Could not batch-check existing symbols: %s", e)
    return existing


def get_all_symbol_caps():
    """Fetch SharesOutstanding for every symbol in one pass.

    Returns a dict ``{symbol: float}`` (0 if data unavailable).
    Each symbol has its own collection inside ``db_cap``, so we still do one
    ``find_one`` per collection, but we do it once per cycle and cache the result.
    """
    caps: dict = {}
    try:
        available_collections = set(db_cap.list_collection_names())
    except Exception:
        available_collections = set()

    for symbol in symbols:
        if symbol not in available_collections:
            caps[symbol] = 0
            continue
        try:
            doc = db_cap[symbol].find_one(
                {}, projection={"SharesOutstanding": 1, "_id": 0}
            )
            if (
                doc
                and isinstance(doc, dict)
                and doc.get("SharesOutstanding") is not None
            ):
                caps[symbol] = float(doc["SharesOutstanding"])
            else:
                caps[symbol] = 0
        except Exception:
            caps[symbol] = 0
    logger.info("Fetched market-cap shares for %d symbols", len(caps))
    return caps


# ---------------------------------------------------------------------------
# TradingView data fetching
# ---------------------------------------------------------------------------
def get_live_data_from_tradingview(symbol):
    """Fetch the latest 1-min bar from TradingView for *symbol*."""
    try:
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
                    last_two = data_reset.iloc[-2:]
                    latest = last_two.iloc[-1]
                    previous = last_two.iloc[-2] if len(last_two) > 1 else latest

                    close_change = latest["close"] - previous["close"]
                    pct_change = (
                        (close_change / previous["close"]) * 100
                        if previous["close"] != 0
                        else 0
                    )

                    return {
                        "datetime": datetime.now(lagos_tz).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "open": float(latest["open"]),
                        "high": float(latest["high"]),
                        "low": float(latest["low"]),
                        "close": float(latest["close"]),
                        "volume": (
                            int(latest["volume"])
                            if not pd.isna(latest["volume"])
                            else 0
                        ),
                        "symbol": symbol,
                        "change": round(float(close_change), 2),
                        "percent": round(float(pct_change), 2),
                    }
                else:
                    logger.debug("No data for %s on attempt %d", symbol, attempt + 1)
                    if attempt < max_retries - 1:
                        module_time.sleep(1)
            except Exception as retry_err:
                logger.debug(
                    "Attempt %d failed for %s: %s", attempt + 1, symbol, retry_err
                )
                if attempt < max_retries - 1:
                    module_time.sleep(2)
        return None
    except Exception as e:
        logger.error("Error getting live data for %s: %s", symbol, e)
        return None


def get_historical_data_for_period(symbol, period_days):
    """Fetch historical OHLCV data from TradingView for *symbol* over *period_days*.

    Unlike the original version this does NOT append a fresh live data point;
    the historical data from TradingView is already sufficiently recent and
    the extra API call per period was the biggest source of redundant requests.
    """
    try:
        if period_days == 1:
            interval, n_bars = Interval.in_1_hour, 30
        elif period_days <= 7:
            interval, n_bars = Interval.in_1_hour, min(168, period_days * 24)
        elif period_days <= 30:
            interval, n_bars = Interval.in_daily, min(30, period_days)
        elif period_days <= 365:
            interval, n_bars = Interval.in_daily, min(365, period_days)
        else:
            interval, n_bars = Interval.in_weekly, min(260, period_days // 7)

        max_retries = 2
        for attempt in range(max_retries):
            try:
                data = tv.get_hist(
                    symbol=symbol, exchange="NSENG", interval=interval, n_bars=n_bars
                )
                if data is not None and not data.empty:
                    if data.index.tz is None:
                        data.index = data.index.tz_localize(lagos_tz)
                    elif data.index.tz != lagos_tz:
                        data.index = data.index.tz_convert(lagos_tz)
                    return data
                else:
                    logger.debug(
                        "No historical data for %s (%dd), attempt %d",
                        symbol,
                        period_days,
                        attempt + 1,
                    )
                    if attempt < max_retries - 1:
                        module_time.sleep(2)
            except Exception as retry_err:
                logger.debug(
                    "Historical attempt %d failed for %s: %s",
                    attempt + 1,
                    symbol,
                    retry_err,
                )
                if attempt < max_retries - 1:
                    module_time.sleep(3)
        return None
    except Exception as e:
        logger.error(
            "Error getting historical data for %s (%dd): %s", symbol, period_days, e
        )
        return None


# ---------------------------------------------------------------------------
# Fallback data retrieval
# ---------------------------------------------------------------------------
def _default_live_data(symbol):
    """Return a zeroed-out live data dict marked as fallback."""
    return {
        "datetime": datetime.now(lagos_tz).strftime("%Y-%m-%d %H:%M:%S"),
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


def _default_volatility_data(symbol):
    """Return a zeroed-out volatility dict marked as fallback."""
    keys = [
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
        "volatility_24hr",
        "momentum_24hr",
        "momentum_change_24hr",
        "volume_momentum_24hr",
        "volume_momentum_change_24hr",
        "market_cap",
    ]
    data = {"symbol": symbol, "current_price": 0, "is_fallback": True}
    for k in keys:
        data[k] = 0
    return data


def get_last_available_live_data(symbol):
    """Retrieve the most recent live price for *symbol* from MongoDB, or return defaults."""
    try:
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
        if last_data and isinstance(last_data, dict):
            fb = _default_live_data(symbol)
            for field in ("open", "high", "low", "close", "volume", "change"):
                fb[field] = last_data.get(field, 0)
            fb["percent"] = last_data.get("percentage_change", 0)
            return fb

        last_live = collection_live.find_one(
            {symbol: {"$exists": True}},
            sort=[("_id", -1)],
            projection={"_id": 0, symbol: 1},
        )
        if (
            last_live
            and isinstance(last_live, dict)
            and isinstance(last_live.get(symbol), dict)
        ):
            d = last_live[symbol]
            fb = _default_live_data(symbol)
            for field in (
                "open",
                "high",
                "low",
                "close",
                "volume",
                "change",
                "percent",
            ):
                fb[field] = d.get(field, 0)
            return fb
    except Exception as e:
        logger.error("Error getting last available data for %s: %s", symbol, e)

    logger.info("No historical data for %s, using defaults", symbol)
    return _default_live_data(symbol)


def get_last_available_volatility_data(symbol):
    """Retrieve the most recent volatility record for *symbol* from MongoDB, or return defaults."""
    try:
        last_data = collection_price_combined.find_one(
            {"symbol": symbol},
            sort=[("_id", -1)],
            projection={"_id": 0},
        )
        if last_data and isinstance(last_data, dict):
            last_data.pop("_id", None)
            last_data["is_fallback"] = True
            return last_data
    except Exception as e:
        logger.error("Error getting last volatility data for %s: %s", symbol, e)

    logger.info("No historical volatility data for %s, using defaults", symbol)
    return _default_volatility_data(symbol)


# ---------------------------------------------------------------------------
# Live data collection
# ---------------------------------------------------------------------------
def get_all_live_data(existing_symbols_set):
    """Fetch live prices for every symbol, with fallback to DB for failures.

    *existing_symbols_set* is a pre-fetched set so we avoid per-symbol DB queries.
    """
    combined = {}
    failed_symbols = []
    first_time_symbols = []

    for i, symbol in enumerate(symbols):
        logger.debug("Fetching live data for %s", symbol)
        data = get_live_data_from_tradingview(symbol)
        if data:
            if symbol not in existing_symbols_set:
                first_time_symbols.append(symbol)
                data["change"] = 0
                data["percent"] = 0
                data["is_first_entry"] = True
                logger.debug("First entry for %s – change/percent zeroed", symbol)
            combined[symbol] = data
        else:
            failed_symbols.append(symbol)
            combined[symbol] = get_last_available_live_data(symbol)

        if i < len(symbols) - 1:
            module_time.sleep(0.5)

    if failed_symbols:
        logger.warning(
            "Fallback used for %d symbols: %s", len(failed_symbols), failed_symbols
        )
    if first_time_symbols:
        logger.info("First-time entries for %d symbols", len(first_time_symbols))
    return combined


# ---------------------------------------------------------------------------
# Volatility / momentum calculations
# ---------------------------------------------------------------------------
def filter_data_by_period(data, period_days):
    """Filter a DataFrame to the most recent *period_days* of data."""
    if data is None or data.empty:
        return None
    try:
        if period_days <= 7:
            cutoff = datetime.now(lagos_tz) - timedelta(days=period_days)
            if data.index.tz is None:
                data.index = data.index.tz_localize(lagos_tz)
            elif data.index.tz != lagos_tz:
                data.index = data.index.tz_convert(lagos_tz)
            filtered = data[data.index >= cutoff]
        else:
            filtered = data.tail(period_days)
        return filtered if not filtered.empty else None
    except Exception as e:
        logger.debug("Error filtering data (%dd): %s", period_days, e)
        return data.tail(min(len(data), period_days * 24)) if not data.empty else None


def _calc_vol_mom(data, period):
    """Core volatility/momentum calculation shared by all timeframes.

    Returns (volatility, momentum, momentum_change, volume_momentum,
    volume_momentum_change) or a 5-tuple of Nones on failure.
    """
    _none5 = (None, None, None, None, None)
    if data is None or data.empty:
        return _none5
    try:
        filtered = filter_data_by_period(data, period)
        if filtered is None or len(filtered) < 3:
            return _none5

        filtered = filtered.ffill().bfill().copy()
        filtered["returns"] = filtered["close"].pct_change().fillna(0)

        volatility = filtered["returns"].std() * np.sqrt(252)

        start_price = filtered["close"].iloc[0]
        end_price = filtered["close"].iloc[-1]
        mom_change = end_price - start_price
        momentum = (mom_change / start_price * 100) if start_price != 0 else 0

        start_vol = filtered["volume"].iloc[0]
        end_vol = filtered["volume"].iloc[-1]
        vol_mom_change = end_vol - start_vol
        vol_mom = (vol_mom_change / start_vol * 100) if start_vol != 0 else 0

        return (
            round(volatility, 2),
            round(momentum, 2),
            round(mom_change, 2),
            round(vol_mom, 2),
            round(vol_mom_change, 2),
        )
    except Exception as e:
        logger.debug("Error in _calc_vol_mom (period=%d): %s", period, e)
        return _none5


def _calc_vol_mom_24hr(symbol, data):
    """Calculate 24-hour volatility and momentum."""
    _none5 = (None, None, None, None, None)
    if data is None or data.empty:
        return _none5
    try:
        filtered = filter_data_by_period(data, 1)
        if filtered is None or len(filtered) < 2:
            return _none5

        df = filtered.dropna(subset=["open", "close"]).copy()
        if len(df) < 2:
            return _none5

        df["returns"] = df["close"].pct_change()
        volatility = df["returns"].std() * np.sqrt(252)

        s_price, e_price = df["close"].iloc[0], df["close"].iloc[-1]
        mom_change = e_price - s_price
        momentum = (mom_change / s_price * 100) if s_price != 0 else 0

        s_vol, e_vol = df["volume"].iloc[0], df["volume"].iloc[-1]
        vol_mom_change = e_vol - s_vol
        vol_mom = (vol_mom_change / s_vol * 100) if s_vol != 0 else 0

        return (
            round(volatility, 2),
            round(momentum, 2),
            round(mom_change, 2),
            round(vol_mom, 2),
            round(vol_mom_change, 2),
        )
    except Exception as e:
        logger.debug("Error in 24hr vol/mom for %s: %s", symbol, e)
        return _none5


def calculate_comprehensive_metrics(symbol, *, live_price=None, shares_outstanding=0):
    """Calculate multi-timeframe volatility & momentum for *symbol*.

    Parameters
    ----------
    symbol : str
    live_price : float | None
        Pre-fetched close price from the live-data step.  Avoids a redundant
        TradingView API call.
    shares_outstanding : float
        Pre-fetched shares outstanding for market-cap computation.

    Returns
    -------
    dict | None
    """
    # --- cache hit path (no API calls needed) --------------------------------
    cached = volatility_cache.get_cached_data(symbol)
    if cached:
        if live_price is not None:
            cached["current_price"] = live_price
            cached["market_cap"] = shares_outstanding * live_price
        return cached

    # --- cache miss: calculate fresh -----------------------------------------
    logger.info("Calculating fresh metrics for %s (cache miss)", symbol)
    current_price = live_price if live_price is not None else 0
    dm = {"symbol": symbol, "current_price": current_price}

    try:
        # 1-year (daily)
        data_1y = get_historical_data_for_period(symbol, 365)
        if data_1y is not None and not data_1y.empty:
            v = _calc_vol_mom(data_1y, 365)
            dm["volatility_1year"] = v[0]
            dm["momentum_1year"] = v[1]
            dm["momentum_change_1year"] = v[2]
            dm["volume_momentum_1year"] = v[3]
            dm["volume_momentum_change_1year"] = v[4]

            # YTD
            try:
                cur_year = datetime.now().year
                if hasattr(data_1y.index, "year"):
                    data_ytd = data_1y[data_1y.index.year == cur_year]
                else:
                    data_ytd = data_1y[pd.to_datetime(data_1y.index).year == cur_year]
                if not data_ytd.empty:
                    ytd_days = (datetime.now() - datetime(cur_year, 1, 1)).days
                    vy = _calc_vol_mom(data_ytd, ytd_days)
                    dm["volatility_ytd"] = vy[0]
                    dm["momentum_ytd"] = vy[1]
                    dm["momentum_change_ytd"] = vy[2]
                    dm["volume_momentum_ytd"] = vy[3]
                    dm["volume_momentum_change_ytd"] = vy[4]
                else:
                    for m in (
                        "volatility_ytd",
                        "momentum_ytd",
                        "momentum_change_ytd",
                        "volume_momentum_ytd",
                        "volume_momentum_change_ytd",
                    ):
                        dm[m] = None
            except Exception:
                for m in (
                    "volatility_ytd",
                    "momentum_ytd",
                    "momentum_change_ytd",
                    "volume_momentum_ytd",
                    "volume_momentum_change_ytd",
                ):
                    dm[m] = None
        else:
            for m in (
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
            ):
                dm[m] = None

        # 1-month delay between API calls
        module_time.sleep(0.3)

        # 1-month (daily)
        data_1m = get_historical_data_for_period(symbol, 30)
        if data_1m is not None and not data_1m.empty:
            v = _calc_vol_mom(data_1m, 30)
            dm["volatility"] = v[0]
            dm["momentum"] = v[1]
            dm["momentum_change"] = v[2]
            dm["volume_momentum"] = v[3]
            dm["volume_momentum_change"] = v[4]
        else:
            for m in (
                "volatility",
                "momentum",
                "momentum_change",
                "volume_momentum",
                "volume_momentum_change",
            ):
                dm[m] = None

        module_time.sleep(0.3)

        # 1-week (hourly)
        data_1w = get_historical_data_for_period(symbol, 7)
        if data_1w is not None and not data_1w.empty:
            v = _calc_vol_mom(data_1w, 7)
            dm["volatility_1week"] = v[0]
            dm["momentum_1week"] = v[1]
            dm["momentum_change_1week"] = v[2]
            dm["volume_momentum_1week"] = v[3]
            dm["volume_momentum_change_1week"] = v[4]
        else:
            for m in (
                "volatility_1week",
                "momentum_1week",
                "momentum_change_1week",
                "volume_momentum_1week",
                "volume_momentum_change_1week",
            ):
                dm[m] = None

        module_time.sleep(0.3)

        # 24-hour (hourly)
        data_24h = get_historical_data_for_period(symbol, 1)
        if data_24h is not None and not data_24h.empty:
            v = _calc_vol_mom_24hr(symbol, data_24h)
            dm["volatility_24hr"] = v[0]
            dm["momentum_24hr"] = v[1]
            dm["momentum_change_24hr"] = v[2]
            dm["volume_momentum_24hr"] = v[3]
            dm["volume_momentum_change_24hr"] = v[4]
        else:
            for m in (
                "volatility_24hr",
                "momentum_24hr",
                "momentum_change_24hr",
                "volume_momentum_24hr",
                "volume_momentum_change_24hr",
            ):
                dm[m] = None

        # Market cap
        dm["market_cap"] = shares_outstanding * current_price

        volatility_cache.set_cached_data(symbol, dm)
        return dm

    except Exception as e:
        logger.error("Error calculating metrics for %s: %s", symbol, e)
        return None


# ---------------------------------------------------------------------------
# Merge & save
# ---------------------------------------------------------------------------
_VOL_FIELDS = [
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
    "volatility_24hr",
    "momentum_24hr",
    "momentum_change_24hr",
    "volume_momentum_24hr",
    "volume_momentum_change_24hr",
    "market_cap",
]


def create_merged_data(live_data, volatility_data):
    """Combine live prices with volatility metrics into one dict per symbol."""
    combined = {}
    for symbol, live_info in live_data.items():
        vol = volatility_data.get(symbol)
        merged = {
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
        }
        if vol and isinstance(vol, dict):
            for f in _VOL_FIELDS:
                merged[f] = safe_float(vol.get(f))
        else:
            for f in _VOL_FIELDS:
                merged[f] = 0
        combined[symbol] = merged
    return combined


def ensure_all_symbols_included(live_data, volatility_data, merged_data):
    """Backfill any symbols missing from the fetched datasets."""
    try:
        for symbol in symbols:
            if symbol not in live_data:
                logger.debug("Adding fallback live data for %s", symbol)
                live_data[symbol] = get_last_available_live_data(symbol)
            if symbol not in volatility_data:
                logger.debug("Adding fallback volatility data for %s", symbol)
                volatility_data[symbol] = get_last_available_volatility_data(symbol)

        merged_data = create_merged_data(live_data, volatility_data)
        return live_data, volatility_data, merged_data
    except Exception as e:
        logger.error("Error ensuring all symbols included: %s", e)
        return live_data, volatility_data, merged_data


def save_data(live_data, volatility_data, merged_data):
    """Persist live, volatility, and merged data to MongoDB."""
    saved = {"live": 0, "volatility": 0, "merged": 0}
    try:
        # Live data
        if live_data:
            data_to_save = {k: v for k, v in live_data.items() if k != "_id"}
            if data_to_save:
                try:
                    collection_live.insert_one(data_to_save)
                    saved["live"] = len(data_to_save)
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    db_live[today_str].insert_one(data_to_save)
                except Exception as e:
                    logger.error("Error saving live data: %s", e)

        # Volatility data (only fresh, non-fallback records)
        if volatility_data:
            docs = []
            for _sym, vd in volatility_data.items():
                if isinstance(vd, dict) and not vd.get("is_fallback", False):
                    d = vd.copy()
                    d.pop("_id", None)
                    d["timestamp"] = datetime.now(lagos_tz).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    docs.append(d)
            if docs:
                try:
                    collection_price_combined.insert_many(docs)
                    saved["volatility"] = len(docs)
                except Exception as e:
                    logger.error("Error saving volatility data: %s", e)

        # Merged data
        if merged_data:
            try:
                combined_doc = {}
                for sym, info in merged_data.items():
                    if isinstance(info, dict):
                        sd = info.copy()
                        sd.pop("symbol", None)
                        combined_doc[sym] = sd
                if combined_doc:
                    collection_merged.insert_one(combined_doc)
                    saved["merged"] = len(combined_doc)
            except Exception as e:
                logger.error("Error saving merged data: %s", e)
    except Exception as e:
        logger.error("Error in save operation: %s", e)

    logger.info(
        "Saved — live: %d, volatility: %d, merged: %d",
        saved["live"],
        saved["volatility"],
        saved["merged"],
    )
    return saved


# ---------------------------------------------------------------------------
# Data cleanup (Phase 5)
# ---------------------------------------------------------------------------
def cleanup_old_data():
    """Remove documents older than DATA_RETENTION_DAYS from growing collections.

    Only runs if DATA_RETENTION_DAYS > 0.  Uses ObjectId timestamp extraction
    so no extra date field is needed.
    """
    if DATA_RETENTION_DAYS <= 0:
        return

    from bson import ObjectId

    cutoff = datetime.utcnow() - timedelta(days=DATA_RETENTION_DAYS)
    # ObjectId encodes its creation timestamp in the first 4 bytes
    cutoff_id = ObjectId.from_datetime(cutoff)

    for coll, name in [
        (collection_live, "live"),
        (collection_price_combined, "volatility"),
        (collection_merged, "merged"),
    ]:
        try:
            result = coll.delete_many({"_id": {"$lt": cutoff_id}})
            if result.deleted_count:
                logger.info(
                    "Cleaned up %d old %s documents", result.deleted_count, name
                )
        except Exception as e:
            logger.warning("Cleanup failed for %s: %s", name, e)

    # Clean up date-keyed daily collections
    try:
        cutoff_date_str = cutoff.strftime("%Y-%m-%d")
        for coll_name in db_live.list_collection_names():
            # Date-formatted collection names look like "2025-03-01"
            if len(coll_name) == 10 and coll_name[4] == "-" and coll_name[7] == "-":
                if coll_name < cutoff_date_str:
                    db_live.drop_collection(coll_name)
                    logger.info("Dropped old daily collection: %s", coll_name)
    except Exception as e:
        logger.warning("Daily collection cleanup error: %s", e)


# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------
def main_cycle():
    """Execute one full data-collection cycle.

    - Live data: always fetched fresh (sequential to avoid rate limits).
    - Volatility data: served from 90-min cache when available; fresh API
      calls only on cache miss.
    - Market-cap shares and first-entry checks are batched at the start.
    """
    if not is_market_open():
        logger.info("Market closed")
        return

    logger.info("Market open — starting data collection")

    # ----- pre-fetch batched data -------------------------------------------
    volatility_cache.clear_expired()
    cache_stats = volatility_cache.get_stats()
    logger.info(
        "Cache: %d valid, %d expired, %d total",
        cache_stats["valid_entries"],
        cache_stats["expired_entries"],
        cache_stats["total_entries"],
    )

    existing_symbols = get_existing_symbols_batch()
    symbol_caps = get_all_symbol_caps()

    # ----- Step 1: live data -------------------------------------------------
    logger.info("Step 1: Fetching live data from TradingView…")
    live_data = get_all_live_data(existing_symbols)

    if not live_data:
        logger.error("No live data retrieved — aborting cycle")
        return

    # ----- Step 2: volatility metrics ----------------------------------------
    logger.info("Step 2: Calculating volatility metrics (90-min cache)…")
    volatility_data = {}
    failed_vol = []
    cache_hits = cache_misses = 0

    for i, symbol in enumerate(symbols):
        live_price = live_data[symbol]["close"] if symbol in live_data else None
        shares = symbol_caps.get(symbol, 0)

        cached = volatility_cache.get_cached_data(symbol)
        if cached:
            cache_hits += 1
            if live_price is not None:
                cached["current_price"] = live_price
                cached["market_cap"] = shares * live_price
            volatility_data[symbol] = cached
        else:
            cache_misses += 1
            metrics = calculate_comprehensive_metrics(
                symbol,
                live_price=live_price,
                shares_outstanding=shares,
            )
            if metrics:
                volatility_data[symbol] = metrics
            else:
                failed_vol.append(symbol)
                volatility_data[symbol] = get_last_available_volatility_data(symbol)

            # Delay only on fresh API calls to stay under rate limits
            if i < len(symbols) - 1:
                module_time.sleep(2)

    hit_rate = (cache_hits / max(cache_hits + cache_misses, 1)) * 100
    logger.info(
        "Cache: %d hits, %d misses (%.1f%% hit rate)",
        cache_hits,
        cache_misses,
        hit_rate,
    )
    if failed_vol:
        logger.warning(
            "Fallback volatility for %d symbols: %s", len(failed_vol), failed_vol
        )

    # Fill gaps
    for symbol in live_data:
        if symbol not in volatility_data:
            volatility_data[symbol] = get_last_available_volatility_data(symbol)

    # ----- Step 3: merge -----------------------------------------------------
    logger.info("Step 3: Merging data…")
    merged_data = create_merged_data(live_data, volatility_data)

    logger.info("Step 3.5: Ensuring all symbols present…")
    live_data, volatility_data, merged_data = ensure_all_symbols_included(
        live_data,
        volatility_data,
        merged_data,
    )

    # ----- Step 4: save ------------------------------------------------------
    logger.info("Step 4: Saving to MongoDB…")
    save_data(live_data, volatility_data, merged_data)

    # ----- Step 5: persist cache ---------------------------------------------
    volatility_cache.save_cache()

    # ----- summary -----------------------------------------------------------
    fresh_live = sum(1 for v in live_data.values() if not v.get("is_fallback"))
    fb_live = len(live_data) - fresh_live
    fresh_vol = sum(1 for v in volatility_data.values() if not v.get("is_fallback"))
    fb_vol = len(volatility_data) - fresh_vol

    logger.info(
        "Cycle done — %d symbols | Live fresh/fb: %d/%d | Vol fresh/fb: %d/%d",
        len(merged_data),
        fresh_live,
        fb_live,
        fresh_vol,
        fb_vol,
    )
    if len(merged_data) != len(symbols):
        missing = [s for s in symbols if s not in merged_data]
        logger.warning("Missing symbols: %s", missing)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
# Update interval: 20 minutes
UPDATE_INTERVAL_SECONDS = 1200


def run_unified_system():
    """Run the unified price system in a loop during market hours."""
    logger.info("=" * 70)
    logger.info("Unified Price System v4 — optimised (no parallelisation)")
    logger.info("=" * 70)

    if not verify_mongodb_connection():
        logger.critical("Cannot proceed without MongoDB — exiting")
        return

    logger.info(
        "Live data: fetched every %d min during market hours",
        UPDATE_INTERVAL_SECONDS // 60,
    )
    logger.info("Volatility data: 90-min cache, fresh on miss")
    logger.info("Data retention: %d days", DATA_RETENTION_DAYS)
    logger.info("=" * 70)

    # Run cleanup once on startup
    cleanup_old_data()

    while True:
        try:
            if is_market_open() and datetime.today().weekday() < 5:
                logger.info("-" * 50)
                main_cycle()
                next_run = datetime.now(lagos_tz) + timedelta(
                    seconds=UPDATE_INTERVAL_SECONDS
                )
                logger.info("Next run at %s", next_run.strftime("%H:%M:%S"))
                logger.info("-" * 50)
            else:
                logger.debug("Market closed — sleeping")

            module_time.sleep(UPDATE_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Stopped by user")
            volatility_cache.save_cache()
            break
        except Exception as e:
            logger.error("Error in main loop: %s", e)
            module_time.sleep(60)


# ---------------------------------------------------------------------------
# Utility helpers (callable from shell / REPL)
# ---------------------------------------------------------------------------
def clear_volatility_cache():
    """Manually clear the entire volatility cache."""
    volatility_cache.cache = {}
    volatility_cache.save_cache()
    logger.info("Volatility cache cleared")


def get_cache_info():
    """Print and return detailed cache statistics."""
    stats = volatility_cache.get_stats()
    logger.info(
        "Cache — total: %d, valid: %d, expired: %d",
        stats["total_entries"],
        stats["valid_entries"],
        stats["expired_entries"],
    )
    return stats


def force_cache_refresh(symbol=None):
    """Force-expire cache for a single symbol or all symbols."""
    if symbol:
        if symbol in volatility_cache.cache:
            del volatility_cache.cache[symbol]
            logger.info("Cleared cache for %s", symbol)
        else:
            logger.info("No cache entry for %s", symbol)
    else:
        volatility_cache.cache = {}
        logger.info("Cleared all cache entries")
    volatility_cache.save_cache()


if __name__ == "__main__":
    run_unified_system()

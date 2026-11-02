"""
Single place to read stock prices written by the price collector.

- The latest merged snapshot (one Mongo document keyed by symbol) is cached
  per process for SNAPSHOT_TTL seconds, so a request or task that prices many
  stocks costs one Mongo read instead of one per stock.
- A price of 0/None or a missing symbol is "unavailable": get_price() raises
  PriceUnavailable (a KeyError, so existing `except KeyError` still works) and
  get_price_info() returns price_status="unavailable" with null prices.
- Renamed stocks fall back to their previous tickers (Stock.previous_symbols),
  then to the last good price in livelake3.latest_prices (marked stale).
"""

import math
import threading
import time

SNAPSHOT_TTL = 30  # seconds
ALIASES_TTL = 300

_lock = threading.Lock()
_snapshot = {"data": None, "last_good": {}, "at": 0.0}
_aliases = {"data": None, "at": 0.0}


class PriceUnavailable(KeyError):
    """No usable (non-zero) price is available for the symbol."""

    def __init__(self, symbol):
        super().__init__(symbol)
        self.symbol = symbol

    def __str__(self):
        return f"No price available for {self.symbol}"


def _db():
    from .utils import db_merged

    return db_merged


def _load():
    """Latest snapshot and last-good prices, cached together for SNAPSHOT_TTL seconds."""
    now = time.monotonic()
    with _lock:
        if _snapshot["data"] is not None and now - _snapshot["at"] < SNAPSHOT_TTL:
            return _snapshot["data"], _snapshot["last_good"]
    doc = _db()["merged_live_price_trdv"].find_one(sort=[("_id", -1)]) or {}
    doc.pop("_id", None)
    last_good = {}
    for row in _db()["latest_prices"].find({}):
        if _usable(row):
            row = _normalised(row)
            last_good[row.pop("_id")] = dict(row, is_stale=True)
    with _lock:
        _snapshot.update(data=doc, last_good=last_good, at=now)
    return doc, last_good


def get_snapshot():
    """Latest merged snapshot {symbol: {...}}, cached for SNAPSHOT_TTL seconds."""
    return _load()[0]


def _alias_map():
    """{symbol: [previous symbols]} for renamed stocks, cached."""
    now = time.monotonic()
    with _lock:
        if _aliases["data"] is not None and now - _aliases["at"] < ALIASES_TTL:
            return _aliases["data"]
    from .models import Stock

    data = {
        symbol: previous
        for symbol, previous in Stock.objects.exclude(previous_symbols=[]).values_list(
            "symbol", "previous_symbols"
        )
    }
    with _lock:
        _aliases["data"] = data
        _aliases["at"] = now
    return data


def _clean_price(value):
    """A finite price above 0 as float (numeric strings accepted), else None."""
    if isinstance(value, bool):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 0 else None


def _usable(entry):
    return isinstance(entry, dict) and _clean_price(entry.get("current_price")) is not None


def _normalised(entry):
    """Copy of a usable entry with current_price as a clean float."""
    entry = dict(entry)
    entry["current_price"] = _clean_price(entry["current_price"])
    return entry


def _last_good(symbol):
    """Last non-zero price the collector saw for symbol, marked stale."""
    entry = _load()[1].get(symbol)
    return dict(entry) if entry else None


def _find_entry(symbol):
    snapshot = get_snapshot()
    candidates = [symbol, *_alias_map().get(symbol, [])]
    for candidate in candidates:
        entry = snapshot.get(candidate)
        if _usable(entry):
            return _normalised(entry)
    for candidate in candidates:
        entry = _last_good(candidate)
        if entry:
            return entry
    return None


def get_price(symbol):
    """Snapshot entry for symbol with a non-zero current_price, or raise PriceUnavailable."""
    entry = _find_entry(symbol)
    if entry is None:
        raise PriceUnavailable(symbol)
    entry["price_status"] = "stale" if entry.get("is_stale") else "live"
    entry.setdefault("as_of", entry.get("datetime"))
    return entry


def get_price_info(symbol):
    """Like get_price() but never raises; unavailable prices come back as None."""
    try:
        return get_price(symbol)
    except PriceUnavailable:
        return {
            "current_price": None,
            "change": None,
            "percentage_change": None,
            "price_status": "unavailable",
            "as_of": None,
        }


def get_prices_map():
    """
    {symbol: entry} for every symbol with a usable price: the latest snapshot,
    then the last good price (stale). Renamed stocks are also reachable under
    their current ticker. Symbols with no usable price are absent, so callers
    must handle a missing key. Matches what get_price() returns per symbol.
    """
    snapshot, last_good = _load()
    prices = {
        symbol: _normalised(entry)
        for symbol, entry in snapshot.items()
        if _usable(entry)
    }
    for symbol, previous in _alias_map().items():
        if symbol in prices:
            continue
        for old in previous:
            if old in prices:
                prices[symbol] = prices[old]
                break
    for symbol, entry in last_good.items():
        prices.setdefault(symbol, dict(entry))
    for symbol, previous in _alias_map().items():
        if symbol in prices:
            continue
        for old in previous:
            if old in last_good:
                prices[symbol] = dict(last_good[old])
                break
    return prices


def price_from_map(prices, symbol, default=None):
    """current_price for symbol from a get_prices_map() result, or default."""
    entry = prices.get(symbol)
    return entry["current_price"] if entry else default


def is_price_usable(price):
    return price is not None and price > 0


def price_unavailable_message(symbol):
    # No apostrophes: the dashboard parses error strings with ' -> " JSON replacement.
    return (
        f"Trading in {symbol} is unavailable right now because we do not have "
        "a current price for it. Please try again later."
    )


def api_exception_handler(exc, context):
    """DRF exception handler: PriceUnavailable becomes a friendly 400, not a 500."""
    from rest_framework import status
    from rest_framework.response import Response
    from rest_framework.views import exception_handler

    if isinstance(exc, PriceUnavailable):
        message = price_unavailable_message(exc.symbol)
        # Same shape as str(ValidationError(...)), which the dashboard already parses
        return Response({"error": str([message])}, status=status.HTTP_400_BAD_REQUEST)
    return exception_handler(exc, context)

"""
Automatic sync of the Stock table with the NGX company directory.

Run weekdays after the close by the `portfolio.tasks.sync_ngx_stocks` Celery task
(scheduled by migration 0081), or by hand with `manage.py sync_ngx_stocks`.

Stocks are matched on ISIN, which survives ticker changes:
- same ISIN, new ticker      -> renamed, applied (old ticker kept in previous_symbols)
- ISIN we do not have        -> new listing, applied (profile + logo backfilled)
- active stock not on NGX    -> counted; delisted on the 2nd run in a row. Stocks with
                                open/pending positions wait for approval in admin.
- ngx_status flag changed    -> applied
- ticker clash / ISIN clash / likely successor company -> logged for review, not applied

Safety: a short NGX response, or too many delistings at once, aborts the run.
Every applied run is stored as a StockSyncRun with its StockChange rows, and a
summary is emailed to settings.STOCK_SYNC_EMAILS.
"""

import difflib
import io
import logging
import re
from dataclasses import dataclass, field

import requests
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from .models import Stock, StockChange, StockSyncRun

logger = logging.getLogger(__name__)

NGX_DIRECTORY_URL = (
    "https://doclib.ngxgroup.com/REST/api/issuers/companydirectory"
    "?$orderby=CompanyName"
)
TV_SCANNER_URL = "https://scanner.tradingview.com/nigeria/scan"

MIN_LISTED = 120  # fewer NGX rows than this means a bad response
MIN_TV_TICKERS = 100  # fewer means TradingView is unreliable; keep tv_symbol as is
MISSING_RUNS_TO_DELIST = 2
MAX_DELISTS_PER_RUN = 10  # more at once is more likely bad data than a real event
SUCCESSOR_SIMILARITY = 0.6

# (model, filter) pairs that count as someone holding a stock. Positions block an
# automatic delisting; alerts and watchlist entries are only reported.
HOLDER_QUERIES = [
    ("execution.Position", {"status__in": ["open", "pending"]}, True),
    ("execution.DemoPosition", {"status__in": ["open", "pending"]}, True),
    ("competition.CompetitionPosition", {"status__in": ["open", "pending"]}, True),
    ("hackathon.CompetitionPosition", {"status__in": ["open", "pending"]}, True),
    ("portfolio.Alert", {"trigerred": False}, False),
    ("portfolio.StockWatchlist", {}, False),
]


class SyncAborted(Exception):
    pass


# --- fetching and parsing -------------------------------------------------


def fetch_directory():
    response = requests.get(NGX_DIRECTORY_URL, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_tradingview_tickers():
    """Tickers TradingView carries for Nigeria, or None if the scanner looks broken."""
    try:
        response = requests.post(
            TV_SCANNER_URL, json={"columns": ["name"], "range": [0, 1000]}, timeout=30
        )
        response.raise_for_status()
        tickers = {row["d"][0] for row in response.json()["data"]}
    except Exception:
        logger.exception("TradingView scanner request failed")
        return None
    return tickers if len(tickers) >= MIN_TV_TICKERS else None


def parse_status(ls_std):
    """'[MRF],[BLS],' -> 'MRF,BLS' (fits the 10-char field); '' -> None."""
    joined = ""
    for flag in re.findall(r"\[(\w+)\]", ls_std or ""):
        candidate = f"{joined},{flag}" if joined else flag
        if len(candidate) > 10:
            break
        joined = candidate
    return joined or None


def parse_directory(raw, tv_tickers):
    rows, seen = [], set()
    for record in raw:
        symbol = (record.get("Symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        rows.append(
            {
                "symbol": symbol,
                "isin": (record.get("InternationSecIN") or "").strip() or None,
                "company": (record.get("CompanyName") or symbol).strip()[:200],
                "sector": (record.get("Sector") or "").strip()[:50] or None,
                "listing_date": (record.get("DateListed") or "")[:10] or None,
                "incorporation_date": (record.get("DateOfIncorporation") or "")[:10]
                or None,
                "ngx_status": parse_status(record.get("LS_STD")),
                "tradingview": None if tv_tickers is None else symbol in tv_tickers,
            }
        )
    return rows


# --- planning -------------------------------------------------------------


@dataclass
class Change:
    kind: str
    status: str
    symbol: str
    old_value: str = ""
    new_value: str = ""
    isin: str = ""
    note: str = ""
    holders: dict = field(default_factory=dict)
    stock: Stock | None = None


@dataclass
class Plan:
    rows: list
    changes: list = field(default_factory=list)
    creates: list = field(default_factory=list)
    updates: dict = field(default_factory=dict)  # stock pk -> {field: value}
    missing_once: list = field(default_factory=list)


def holders(stock):
    """{label: count} of open positions/orders, alerts and watchlist entries."""
    counts = {}
    for label, filters, _ in HOLDER_QUERIES:
        try:
            model = apps.get_model(label)
        except LookupError:
            continue
        count = model.objects.filter(stock=stock, **filters).count()
        if count:
            counts[label] = count
    return counts


def has_open_positions(counts):
    blocking = {label for label, _, blocks in HOLDER_QUERIES if blocks}
    return any(label in blocking for label in counts)


def _name_key(name):
    name = re.sub(r"\[.*?\]", " ", name.upper())
    name = re.sub(r"[^A-Z0-9 ]", " ", name)
    words = [w for w in name.split() if w not in {"PLC", "NIG", "NIGERIA", "LTD", "THE"}]
    return " ".join(words)


def _similar(a, b):
    return difflib.SequenceMatcher(None, _name_key(a), _name_key(b)).ratio()


def build_plan(rows, max_delists=MAX_DELISTS_PER_RUN, tv_tickers=None):
    plan = Plan(rows=rows)
    tv_known = all(row["tradingview"] is not None for row in rows)
    stocks = list(Stock.objects.all())
    by_isin = {s.isin: s for s in stocks if s.isin}
    by_symbol = {s.symbol: s for s in stocks}
    pending_delists = set(
        StockChange.objects.filter(
            kind=StockChange.DELISTED,
            status__in=[StockChange.PENDING, StockChange.REJECTED],
        ).values_list("stock_id", flat=True)
    )
    logged_reviews = set(
        StockChange.objects.filter(kind=StockChange.REVIEW).values_list(
            "symbol", "new_value"
        )
    )
    seen = set()

    def review(symbol, new_value, note, stock=None, isin=""):
        if (symbol, new_value) in logged_reviews:
            return
        logged_reviews.add((symbol, new_value))
        plan.changes.append(
            Change(
                StockChange.REVIEW,
                StockChange.PENDING,
                symbol,
                new_value=new_value,
                isin=isin or "",
                note=note,
                stock=stock,
            )
        )

    for row in rows:
        symbol, isin = row["symbol"], row["isin"]
        stock = by_isin.get(isin) if isin else None
        if stock is None:
            same_symbol = by_symbol.get(symbol)
            if same_symbol and same_symbol.isin and isin and same_symbol.isin != isin:
                seen.add(same_symbol.pk)
                review(
                    symbol,
                    isin,
                    f"NGX lists {symbol} with ISIN {isin}, but our {symbol} has "
                    f"{same_symbol.isin}. Either the ticker now belongs to another "
                    "security or NGX corrected the ISIN. Nothing was changed.",
                    stock=same_symbol,
                    isin=isin,
                )
                continue
            stock = same_symbol  # a stock without an ISIN yet adopts NGX's

        if stock is None:
            plan.creates.append(row)
            plan.changes.append(
                Change(
                    StockChange.LISTED,
                    StockChange.APPLIED,
                    symbol,
                    new_value=row["company"],
                    isin=isin or "",
                    note="" if row["tradingview"] else "No TradingView data yet",
                )
            )
            continue

        seen.add(stock.pk)
        update = {}
        renamed = stock.symbol != symbol
        if renamed:
            clash = by_symbol.get(symbol)
            if clash and clash.pk != stock.pk:
                review(
                    symbol,
                    stock.symbol,
                    f"NGX renamed {stock.symbol} to {symbol} (ISIN {isin}), but "
                    f"{symbol} is already a different stock here. Nothing was changed.",
                    stock=stock,
                    isin=isin,
                )
                continue
            update["symbol"] = symbol
            update["previous_symbols"] = list(
                dict.fromkeys([*(stock.previous_symbols or []), stock.symbol])
            )
            plan.changes.append(
                Change(
                    StockChange.RENAMED,
                    StockChange.APPLIED,
                    symbol,
                    old_value=stock.symbol,
                    new_value=symbol,
                    isin=isin or "",
                    note=f"{stock.company} -> {row['company']}",
                    stock=stock,
                )
            )
        if isin and stock.isin != isin:
            update["isin"] = isin
        if row["company"] != stock.company:
            update["company"] = row["company"]
        if not stock.active:
            update["active"] = True
            plan.changes.append(
                Change(
                    StockChange.RELISTED,
                    StockChange.APPLIED,
                    symbol,
                    isin=isin or "",
                    stock=stock,
                )
            )
        if stock.ngx_missing_runs:
            update["ngx_missing_runs"] = 0
        if stock.ngx_status != row["ngx_status"]:
            update["ngx_status"] = row["ngx_status"]
            plan.changes.append(
                Change(
                    StockChange.STATUS_CHANGED,
                    StockChange.APPLIED,
                    symbol,
                    old_value=stock.ngx_status or "",
                    new_value=row["ngx_status"] or "",
                    isin=isin or "",
                    stock=stock,
                )
            )
        if tv_known:
            # NGX often renames before TradingView does; keep pricing under the
            # old ticker until TradingView catches up.
            tv_ticker = symbol if row["tradingview"] else next(
                (
                    old
                    for old in [stock.symbol, *(stock.previous_symbols or [])]
                    if tv_tickers and old in tv_tickers
                ),
                None,
            )
            tv_symbol = f"NSENG:{tv_ticker}" if tv_ticker else None
            if stock.tv_symbol != tv_symbol:
                update["tv_symbol"] = tv_symbol
        elif renamed and stock.tv_symbol:
            update["tv_symbol"] = f"NSENG:{symbol}"
        if update:
            plan.updates[stock.pk] = update

    missing = [s for s in stocks if s.active and s.pk not in seen]
    delist_count = 0
    for stock in missing:
        runs = stock.ngx_missing_runs + 1
        plan.updates[stock.pk] = {"ngx_missing_runs": runs}
        if runs < MISSING_RUNS_TO_DELIST:
            plan.missing_once.append(stock.symbol)
            continue
        if stock.pk in pending_delists:
            continue  # already waiting for (or refused) approval
        counts = holders(stock)
        delist_count += 1
        if has_open_positions(counts):
            status, note = (
                StockChange.PENDING,
                "Users hold this stock. Decide how to settle their positions, "
                "then approve to deactivate it.",
            )
        else:
            status, note = StockChange.APPLIED, ""
            plan.updates[stock.pk].update(active=False, tv_symbol=None)
        plan.changes.append(
            Change(
                StockChange.DELISTED,
                status,
                stock.symbol,
                old_value=stock.company,
                isin=stock.isin or "",
                note=note,
                holders=counts,
                stock=stock,
            )
        )

    if max_delists is not None and delist_count > max_delists:
        raise SyncAborted(
            f"{delist_count} stocks would be delisted at once (limit "
            f"{max_delists}). Check the NGX data, then rerun with --force."
        )

    # A restructure can give the company a new ISIN (CHIPLC -> CONHALLPLC): it then
    # looks like an unrelated delisting plus a new listing. Flag likely pairs.
    for row in plan.creates:
        for stock in missing:
            if _similar(row["company"], stock.company) >= SUCCESSOR_SIMILARITY:
                review(
                    row["symbol"],
                    stock.symbol,
                    f"New listing {row['symbol']} ({row['company']}) may succeed "
                    f"{stock.symbol} ({stock.company}), which NGX no longer lists. "
                    "If so, decide how holders of the old stock carry over.",
                    stock=stock,
                    isin=row["isin"] or "",
                )
    return plan


# --- applying -------------------------------------------------------------


def apply_plan(plan, run):
    created = {}
    with transaction.atomic():
        for pk, update in plan.updates.items():
            Stock.objects.filter(pk=pk).update(**update)
        for row in plan.creates:
            created[row["symbol"]] = Stock.objects.create(
                symbol=row["symbol"],
                company=row["company"],
                sector=row["sector"],
                listing_date=row["listing_date"],
                incorporation_date=row["incorporation_date"],
                isin=row["isin"],
                tv_symbol=f"NSENG:{row['symbol']}" if row["tradingview"] else None,
                ngx_status=row["ngx_status"],
                active=True,
            )
        for change in plan.changes:
            stock = change.stock or created.get(change.symbol)
            StockChange.objects.create(
                run=run,
                stock=stock,
                kind=change.kind,
                status=change.status,
                symbol=change.symbol,
                old_value=change.old_value[:200],
                new_value=change.new_value[:200],
                isin=change.isin,
                note=change.note,
                holders=change.holders,
            )
    return created


def run_followups(plan, created, raw):
    """Mongo key renames, then profile + logo for new listings. Returns errors."""
    from .company_profile import upsert_from_ngx_data

    errors = []
    if any(c.kind == StockChange.RENAMED for c in plan.changes):
        try:
            call_command("rename_stock_mongo_keys", apply=True, stdout=io.StringIO())
        except Exception as exc:
            errors.append(f"rename_stock_mongo_keys: {exc}")
    if created:
        raw_by_symbol = {(r.get("Symbol") or "").strip().upper(): r for r in raw}
        for symbol in created:
            try:
                upsert_from_ngx_data({**raw_by_symbol[symbol], "Symbol": symbol})
            except Exception as exc:
                errors.append(f"profile {symbol}: {exc}")
        try:
            call_command(
                "backfill_stock_details",
                symbols=list(created),
                skip_profiles=True,
                stdout=io.StringIO(),
            )
        except Exception as exc:
            errors.append(f"backfill_stock_details: {exc}")
    return errors


def summarise(plan):
    by_kind = {}
    for change in plan.changes:
        label = change.symbol
        if change.kind == StockChange.RENAMED:
            label = f"{change.old_value} -> {change.new_value}"
        elif change.kind == StockChange.STATUS_CHANGED:
            label = f"{change.symbol} ({change.old_value or '-'} -> {change.new_value or '-'})"
        elif change.kind == StockChange.REVIEW:
            label = f"{change.symbol}: {change.note}"
        if change.status == StockChange.PENDING:
            label += " [needs approval]"
        by_kind.setdefault(change.kind, []).append(label)
    return {
        "listed": len(plan.rows),
        "changes": by_kind,
        "missing_once": plan.missing_once,
    }


def _email(subject, body):
    recipients = getattr(settings, "STOCK_SYNC_EMAILS", [])
    if not recipients:
        return
    try:
        send_mail(subject, body, "Hamma <hello@gohamma.com>", recipients)
    except Exception:
        logger.exception("Could not email the NGX sync summary")


def format_summary(summary, errors=()):
    titles = dict(StockChange.KIND_CHOICES)
    lines = [f"NGX lists {summary['listed']} stocks."]
    for kind, items in summary["changes"].items():
        lines.append(f"\n{titles[kind]} ({len(items)}):")
        lines += [f"  - {item}" for item in items]
    if summary["missing_once"]:
        lines.append(
            "\nMissing from NGX for the first time (delisted if still missing next run): "
            + ", ".join(summary["missing_once"])
        )
    if not summary["changes"] and not summary["missing_once"]:
        lines.append("No changes.")
    if errors:
        lines.append("\nFollow-up errors:")
        lines += [f"  - {e}" for e in errors]
    if any(
        "[needs approval]" in item for items in summary["changes"].values() for item in items
    ) or "review" in summary["changes"]:
        lines.append(
            "\nReview pending items in Django admin -> Portfolio -> Stock changes "
            "(filter: Waiting for approval)."
        )
    return "\n".join(lines)


def run_sync(apply=False, raw=None, tv_tickers=None, force=False, followups=True, notify=True):
    """Fetch, plan and (if apply) apply. Returns (plan, summary, errors)."""
    run = StockSyncRun(applied=apply)
    try:
        if raw is None:
            raw = fetch_directory()
            tv_tickers = fetch_tradingview_tickers()
        rows = parse_directory(raw, tv_tickers)
        if len(rows) < MIN_LISTED:
            raise SyncAborted(
                f"NGX returned only {len(rows)} stocks (expected at least {MIN_LISTED})."
            )
        plan = build_plan(
            rows,
            max_delists=None if force else MAX_DELISTS_PER_RUN,
            tv_tickers=tv_tickers,
        )
    except Exception as exc:
        if apply:
            run.error = str(exc)
            run.finished = timezone.now()
            run.save()
            if notify:
                _email("NGX stock sync aborted", f"Nothing was changed.\n\n{exc}")
        raise

    summary = summarise(plan)
    errors = []
    if apply:
        run.listed_count = len(rows)
        run.rows = rows
        run.summary = summary
        run.save()
        try:
            created = apply_plan(plan, run)
        except Exception as exc:
            run.error = f"Applying changes failed (rolled back): {exc}"
            run.finished = timezone.now()
            run.save(update_fields=["error", "finished"])
            if notify:
                _email("NGX stock sync failed", run.error)
            raise
        if followups:
            errors = run_followups(plan, created, raw)
        run.error = "\n".join(errors)
        run.finished = timezone.now()
        run.save(update_fields=["error", "finished"])
        if notify and (plan.changes or plan.missing_once or errors):
            needs_action = errors or any(
                c.status == StockChange.PENDING for c in plan.changes
            )
            subject = (
                "NGX stock sync: action needed"
                if needs_action
                else "NGX stock sync: changes applied"
            )
            _email(subject, format_summary(summary, errors))
    return plan, summary, errors

"""
One-off sync of the Stock table with the NGX company directory (2 Nov 2026).

- Renames tickers that NGX changed (matched by ISIN); keeps the old ticker in
  previous_symbols. All FKs point at the Stock row, so links are preserved.
- Creates listed companies we did not have and (re)activates every listed one.
- Deactivates stocks that are no longer on the NGX list (delisted).
- Fills isin, tv_symbol (only where TradingView carries the stock) and ngx_status.
- Seeds Nigerian public holidays for the next 12 months (see HOLIDAYS).

Mongo collections/fields keyed by the old tickers are migrated separately with
`python manage.py rename_stock_mongo_keys --apply`.
"""

import json
from datetime import date
from pathlib import Path

from django.db import migrations

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "ngx_directory_2026-11-02.json"

# old ticker -> new ticker (same ISIN)
RENAMES = {
    "ABBEYBDS": "ABBEYBANK",
    "FBNH": "FIRSTHOLDCO",
    "DEAPCAP": "CMFC",
    "STDINSURE": "FTGINSURE",
    "WAPCO": "HBMNG",
    "UHOMREIT": "UHREIT",
}

# Nigerian public holidays, 2 Nov 2026 - 2 Nov 2027, from the `holidays` package
# (same source as `manage.py sync_market_holidays`). Islamic dates are estimates;
# confirm them in admin when the Federal Government announces them.
HOLIDAYS = [
    (date(2026, 12, 25), "Christmas Day"),
    (date(2026, 12, 26), "Boxing Day"),
    (date(2026, 12, 28), "Boxing Day (observed)"),
    (date(2027, 1, 1), "New Year's Day"),
    (date(2027, 3, 10), "Id el Fitr (estimated)"),
    (date(2027, 3, 11), "Id el Fitr Holiday (estimated)"),
    (date(2027, 3, 26), "Good Friday"),
    (date(2027, 3, 29), "Easter Monday"),
    (date(2027, 5, 1), "Workers' Day"),
    (date(2027, 5, 3), "Workers' Day (observed)"),
    (date(2027, 5, 17), "Id el Kabir (estimated)"),
    (date(2027, 5, 18), "Id el Kabir Holiday (estimated)"),
    (date(2027, 5, 29), "Presidential Inauguration Day"),
    (date(2027, 6, 12), "Democracy Day"),
    (date(2027, 6, 14), "Democracy Day (observed)"),
    (date(2027, 8, 15), "Id el Maulud (estimated)"),
    (date(2027, 8, 16), "Id el Maulud (observed, estimated)"),
    (date(2027, 10, 1), "National Day"),
]


def _parse_date(value):
    return date.fromisoformat(value) if value else None


def sync_stocks(apps, schema_editor):
    Stock = apps.get_model("portfolio", "Stock")
    MarketHoliday = apps.get_model("portfolio", "MarketHoliday")

    rows = json.loads(SEED_FILE.read_text())
    new_to_old = {new: old for old, new in RENAMES.items()}
    listed_ids = set()

    for row in rows:
        symbol = row["symbol"]
        stock = Stock.objects.filter(symbol=symbol).first()

        old = new_to_old.get(symbol)
        if stock is None and old:
            stock = Stock.objects.filter(symbol=old).first()
            if stock is not None:
                stock.previous_symbols = list(
                    dict.fromkeys([*(stock.previous_symbols or []), old])
                )
                stock.symbol = symbol
                stock.company = row["company"]

        if stock is None:
            stock = Stock(
                symbol=symbol,
                company=row["company"],
                sector=row["sector"],
                listing_date=_parse_date(row["listing_date"]),
                incorporation_date=_parse_date(row["incorporation_date"]),
            )

        stock.isin = row["isin"]
        stock.tv_symbol = f"NSENG:{symbol}" if row["tradingview"] else None
        stock.ngx_status = row["ngx_status"]
        stock.active = True
        stock.save()
        listed_ids.add(stock.pk)

    Stock.objects.exclude(pk__in=listed_ids).update(active=False, tv_symbol=None)

    for day, name in HOLIDAYS:
        MarketHoliday.objects.get_or_create(date=day, defaults={"name": name})


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0078_stock_isin_tv_symbol_marketholiday"),
    ]

    # Not reversible: renames and (de)activations would need the old state.
    operations = [
        migrations.RunPython(sync_stocks, migrations.RunPython.noop),
    ]

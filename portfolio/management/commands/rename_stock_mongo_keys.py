"""
Move Mongo data keyed by old tickers to the new tickers after a stock rename.

Renames come from Stock.previous_symbols (set by migration 0079). For every
(old -> new) pair this command:
  - renames per-symbol collections named after the old ticker, in any database
    (e.g. ngxfundamentals.FBNH -> ngxfundamentals.FIRSTHOLDCO), unless the new
    collection already exists;
  - rewrites the `symbol` field in stock_prices_trdv.price_combined_trdv.

Snapshot documents in livelake3 (keyed by ticker) are history and are left as
they are; the price service falls back to previous_symbols when reading them.

Dry run by default; pass --apply to make changes.
"""

from django.core.management.base import BaseCommand

from portfolio.models import Stock
from portfolio.utils import client

SYSTEM_DBS = {"admin", "local", "config"}
SYMBOL_FIELD_COLLECTIONS = [("stock_prices_trdv", "price_combined_trdv")]


class Command(BaseCommand):
    help = "Rename Mongo collections/fields from old stock tickers to new ones"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Make the changes (default: dry run)"
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        pairs = [
            (old, stock.symbol)
            for stock in Stock.objects.exclude(previous_symbols=[])
            for old in stock.previous_symbols
            if old != stock.symbol
        ]
        if not pairs:
            self.stdout.write("No renamed stocks found.")
            return

        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(f"[{mode}] {len(pairs)} renames: {pairs}")

        for db_name in client.list_database_names():
            if db_name in SYSTEM_DBS:
                continue
            db = client[db_name]
            collections = set(db.list_collection_names())
            for old, new in pairs:
                if old not in collections:
                    continue
                if new in collections:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  skip {db_name}.{old}: {db_name}.{new} already exists"
                        )
                    )
                    continue
                self.stdout.write(f"  rename collection {db_name}.{old} -> {new}")
                if apply:
                    db[old].rename(new)

        for db_name, coll_name in SYMBOL_FIELD_COLLECTIONS:
            coll = client[db_name][coll_name]
            for old, new in pairs:
                count = coll.count_documents({"symbol": old})
                if not count:
                    continue
                self.stdout.write(
                    f"  {db_name}.{coll_name}: symbol {old} -> {new} ({count} docs)"
                )
                if apply:
                    coll.update_many({"symbol": old}, {"$set": {"symbol": new}})

        if not apply:
            self.stdout.write("Dry run only. Re-run with --apply to make changes.")

import os

from django.core.management.base import BaseCommand
from pymongo import MongoClient

from portfolio.company_profile import upsert_from_ngx_data


class Command(BaseCommand):
    help = (
        "One-time import of ngxlistedcompanies Mongo data into PostgreSQL CompanyProfile"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--mongo-db",
            default="ngxlistedcompanies",
            help="Mongo database name (default: ngxlistedcompanies)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List symbols that would be migrated without writing to Postgres",
        )

    def handle(self, *args, **options):
        mongo_db_name = options["mongo_db"]
        dry_run = options["dry_run"]

        client = MongoClient(
            os.environ.get("MONGO_STRING"),
            tls=True,
            tlsAllowInvalidCertificates=True,
        )
        db = client[mongo_db_name]
        collection_names = db.list_collection_names()

        self.stdout.write(
            f"Found {len(collection_names)} collections in Mongo '{mongo_db_name}'"
        )

        migrated = 0
        empty = 0
        failed: list[str] = []
        for symbol in sorted(collection_names):
            doc = db[symbol].find_one({})
            if not doc:
                empty += 1
                continue
            doc.pop("_id", None)
            if "Symbol" not in doc:
                doc["Symbol"] = symbol
            if dry_run:
                self.stdout.write(f"Would migrate {symbol}")
                migrated += 1
                continue
            try:
                upsert_from_ngx_data(doc)
                migrated += 1
                self.stdout.write(f"Migrated {symbol}")
            except Exception as exc:
                failed.append(f"{symbol}: {exc}")
                self.stderr.write(self.style.ERROR(f"Failed {symbol}: {exc}"))

        suffix = " (dry run)" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Finished{suffix}: processed {migrated}, "
                f"empty collections {empty}, failed {len(failed)}."
            )
        )
        if failed:
            self.stderr.write(self.style.WARNING("Failures:\n" + "\n".join(failed)))

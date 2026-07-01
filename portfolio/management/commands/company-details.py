import json

import requests
from django.core.management.base import BaseCommand

from portfolio.company_profile import upsert_from_ngx_data
from portfolio.models import Stock

NGX_COMPANY_DIRECTORY_URL = (
    "https://doclib.ngxgroup.com/REST/api/issuers/companydirectory"
    "?$orderby=CompanyName"
)


class Command(BaseCommand):
    help = "Sync NGX company directory data into PostgreSQL CompanyProfile records"

    def handle(self, *args, **options):
        stocks = Stock.objects.filter(active=True)
        symbols = {stock.symbol for stock in stocks}
        self.stdout.write(f"Active symbols in Postgres: {len(symbols)}")

        response = requests.get(NGX_COMPANY_DIRECTORY_URL, timeout=60)
        response.raise_for_status()
        json_data = json.loads(response.text)

        created_or_updated = 0
        skipped = 0
        for entry in json_data:
            symbol = entry.get("Symbol")
            if symbol not in symbols:
                skipped += 1
                continue
            upsert_from_ngx_data(entry)
            created_or_updated += 1
            self.stdout.write(f"Synced profile for {symbol}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Synced {created_or_updated} profiles, skipped {skipped}."
            )
        )

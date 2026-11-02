"""
Fill in details for stocks that have none yet (e.g. new NGX listings):

- Company profile (CompanyProfile, incl. shares outstanding used for market cap)
  from the NGX company directory snapshot in portfolio/data/.
- Logo: TradingView's SVG logo for the symbol, converted to PNG and uploaded to
  S3 at new_stock_images/image_<SYMBOL>.png (same as existing logos); sets
  logo_url and email_logo_url.

Prices need no backfill: the collector picks up every active stock with a
tv_symbol on its next run and computes 1y/YTD/1m/1w metrics from TradingView
history on its first pass.

    python manage.py backfill_stock_details --dry-run
    python manage.py backfill_stock_details                  # stocks missing a logo or profile
    python manage.py backfill_stock_details --symbols ARADEL HMCALL --force
"""

import json
from io import BytesIO
from pathlib import Path

import boto3
import cairosvg
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from portfolio.company_profile import upsert_from_ngx_data
from portfolio.models import CompanyProfile, Stock

NGX_RAW_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "ngx_directory_2026-11-02_raw.json"
)
TV_SCANNER_URL = "https://scanner.tradingview.com/nigeria/scan"
TV_LOGO_URL = "https://s3-symbol-logo.tradingview.com/{logoid}.svg"
LOGO_KEY = "new_stock_images/image_{symbol}.png"


def load_ngx_records():
    records = json.loads(NGX_RAW_FILE.read_text())
    by_symbol = {}
    for record in records:
        record["Symbol"] = record["Symbol"].strip()
        by_symbol[record["Symbol"]] = record
    return by_symbol


def load_tradingview_logo_ids():
    """{ticker: logoid} for every Nigerian stock TradingView lists."""
    response = requests.post(
        TV_SCANNER_URL,
        json={"columns": ["name", "logoid"], "range": [0, 1000]},
        timeout=30,
    )
    response.raise_for_status()
    return {row["d"][0]: row["d"][1] for row in response.json()["data"] if row["d"][1]}


def upload_logo(symbol, logoid):
    svg = requests.get(TV_LOGO_URL.format(logoid=logoid), timeout=30)
    svg.raise_for_status()
    png = BytesIO()
    cairosvg.svg2png(bytestring=svg.content, write_to=png, output_width=256)
    png.seek(0)

    bucket = settings.AWS_STORAGE_BUCKET_NAME
    region = settings.AWS_S3_REGION_NAME
    key = LOGO_KEY.format(symbol=symbol)
    boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=region,
    ).upload_fileobj(png, bucket, key, ExtraArgs={"ContentType": "image/png"})
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


class Command(BaseCommand):
    help = "Backfill company profiles and logos for stocks that lack them"

    def add_arguments(self, parser):
        parser.add_argument("--symbols", nargs="+", help="Only these symbols")
        parser.add_argument(
            "--force", action="store_true", help="Redo even if already present"
        )
        parser.add_argument("--skip-logos", action="store_true")
        parser.add_argument("--skip-profiles", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        stocks = Stock.objects.filter(active=True).order_by("symbol")
        if options["symbols"]:
            stocks = stocks.filter(symbol__in=[s.upper() for s in options["symbols"]])
        force = options["force"]
        dry_run = options["dry_run"]

        with_profile = set(
            CompanyProfile.objects.values_list("stock_id", flat=True)
        )
        need_profile = [
            s for s in stocks if force or s.pk not in with_profile
        ] if not options["skip_profiles"] else []
        need_logo = [
            s for s in stocks if force or not s.logo_url
        ] if not options["skip_logos"] else []

        self.stdout.write(
            f"{len(need_profile)} stocks need a profile, {len(need_logo)} need a logo"
            + (" (dry run)" if dry_run else "")
        )

        if need_profile:
            records = load_ngx_records()
            for stock in need_profile:
                record = records.get(stock.symbol)
                if record is None:
                    self.stdout.write(
                        self.style.WARNING(f"  profile {stock.symbol}: not in NGX data")
                    )
                    continue
                if not dry_run:
                    upsert_from_ngx_data(record)
                self.stdout.write(f"  profile {stock.symbol}: ok")

        if need_logo:
            logo_ids = load_tradingview_logo_ids()
            for stock in need_logo:
                ticker = (stock.tv_symbol or stock.symbol).split(":")[-1]
                logoid = logo_ids.get(ticker)
                if not logoid:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  logo {stock.symbol}: TradingView has no logo"
                        )
                    )
                    continue
                if dry_run:
                    self.stdout.write(f"  logo {stock.symbol}: would use {logoid}")
                    continue
                try:
                    url = upload_logo(stock.symbol, logoid)
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(f"  logo {stock.symbol}: failed ({exc})")
                    )
                    continue
                stock.logo_url = url
                stock.email_logo_url = url
                stock.converted_png = True
                stock.save(update_fields=["logo_url", "email_logo_url", "converted_png"])
                self.stdout.write(f"  logo {stock.symbol}: {url}")

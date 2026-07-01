from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from portfolio.models import Stock


def _rewrite_logo_url(url: str) -> str:
    """
    Rewrite anyon3 bucket/host marker to anyon31.
    Only the first occurrence is replaced to avoid unexpected changes.
    """
    return url.replace("anyon3", "anyon31", 1)


class Command(BaseCommand):
    help = 'Fix Stock.logo_url values by replacing "anyon3" with "anyon31".'

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would change, without writing.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Only process at most N rows (0 = no limit).",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=1000,
            help="How many rows to bulk update per batch.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = options["limit"] or 0
        chunk_size: int = options["chunk_size"] or 1000

        qs = (
            Stock.objects.filter(logo_url__isnull=False, logo_url__contains="anyon3")
            .only("id", "symbol", "logo_url")
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]

        scanned = 0
        would_change = 0
        to_update: list[Stock] = []

        def flush_updates():
            nonlocal to_update
            if not to_update:
                return 0
            Stock.objects.bulk_update(to_update, ["logo_url"], batch_size=chunk_size)
            updated = len(to_update)
            to_update = []
            return updated

        total_updated = 0
        with transaction.atomic():
            for stock in qs.iterator(chunk_size=chunk_size):
                scanned += 1
                if not stock.logo_url:
                    continue

                new_url = _rewrite_logo_url(stock.logo_url)
                if new_url == stock.logo_url:
                    continue

                would_change += 1
                if dry_run:
                    continue

                stock.logo_url = new_url
                to_update.append(stock)

                if len(to_update) >= chunk_size:
                    total_updated += flush_updates()

            if dry_run:
                # No writes; safe to exit the transaction.
                pass
            else:
                total_updated += flush_updates()

            if dry_run:
                # Ensure absolutely no accidental writes in dry-run.
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: scanned={scanned} would_change={would_change}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done: scanned={scanned} updated={total_updated} unchanged={scanned - total_updated}"
                )
            )

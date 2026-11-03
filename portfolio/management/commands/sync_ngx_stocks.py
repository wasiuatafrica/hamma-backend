"""
Sync the Stock table with the NGX company directory (see portfolio/ngx_sync.py).

    python manage.py sync_ngx_stocks                 # dry run: show what would change
    python manage.py sync_ngx_stocks --apply         # apply, run follow-ups, email summary
    python manage.py sync_ngx_stocks --file portfolio/data/ngx_directory_2026-11-02_raw.json

Runs automatically on weekdays at 17:00 Lagos time (portfolio.tasks.sync_ngx_stocks).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from portfolio.ngx_sync import (
    SyncAborted,
    fetch_tradingview_tickers,
    format_summary,
    run_sync,
)


class Command(BaseCommand):
    help = "Sync stocks with the NGX directory: renames, new listings, delistings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Make the changes (default: dry run)"
        )
        parser.add_argument(
            "--file", help="Use a saved NGX directory JSON instead of fetching it"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow more delistings in one run than the safety limit",
        )
        parser.add_argument(
            "--skip-followups",
            action="store_true",
            help="Skip Mongo renames and profile/logo backfill",
        )
        parser.add_argument("--no-email", action="store_true")

    def handle(self, *args, **options):
        raw = tv_tickers = None
        if options["file"]:
            raw = json.loads(Path(options["file"]).read_text())
            tv_tickers = fetch_tradingview_tickers()

        try:
            plan, summary, errors = run_sync(
                apply=options["apply"],
                raw=raw,
                tv_tickers=tv_tickers,
                force=options["force"],
                followups=not options["skip_followups"],
                notify=not options["no_email"],
            )
        except SyncAborted as exc:
            raise CommandError(f"Aborted, nothing changed: {exc}")

        mode = "APPLIED" if options["apply"] else "DRY RUN"
        self.stdout.write(f"[{mode}]")
        self.stdout.write(format_summary(summary, errors))
        if not options["apply"] and (plan.changes or plan.updates):
            self.stdout.write(
                f"\n{len(plan.updates)} stock rows and {len(plan.creates)} new stocks "
                "would be written. Rerun with --apply."
            )

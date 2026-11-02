"""
Add Nigerian public holidays to MarketHoliday for the coming year.

Uses the `holidays` package (country NG), which includes weekend "observed"
days and *estimated* Islamic holidays (Eid el Fitr, Eid el Kabir, Eid el Maulud).
The Federal Government confirms those dates shortly before each holiday, so
check them in Django admin when they are announced.

Existing rows are updated by date, never deleted, so manual additions in admin
(e.g. a one-off declared holiday) are kept.

    python manage.py sync_market_holidays            # next 365 days
    python manage.py sync_market_holidays --days 730
    python manage.py sync_market_holidays --dry-run
"""

from datetime import timedelta

import holidays
from django.core.management.base import BaseCommand
from django.utils import timezone

from portfolio.market_hours import LAGOS_TZ
from portfolio.models import MarketHoliday


class Command(BaseCommand):
    help = "Add Nigerian public holidays for the coming period to MarketHoliday"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        start = timezone.now().astimezone(LAGOS_TZ).date()
        end = start + timedelta(days=options["days"])
        calendar = holidays.country_holidays(
            "NG", years=range(start.year, end.year + 1)
        )

        created = updated = 0
        for day, name in sorted(calendar.items()):
            if not start <= day <= end:
                continue
            if options["dry_run"]:
                self.stdout.write(f"{day} {day:%a}  {name}")
                continue
            _, was_created = MarketHoliday.objects.update_or_create(
                date=day, defaults={"name": name}
            )
            created += was_created
            updated += not was_created

        if options["dry_run"]:
            self.stdout.write("Dry run only; nothing saved.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Holidays {start} to {end}: {created} added, {updated} updated."
                )
            )

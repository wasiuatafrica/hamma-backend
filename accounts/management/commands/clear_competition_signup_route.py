from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Set signup_route to null for users with signup_route 'competition' and signed up after April 1, 2025."

    def handle(self, *args, **options):
        # April 1, 2025
        cutoff_date = datetime(2025, 4, 1, tzinfo=timezone.get_current_timezone())
        users = CustomUser.objects.filter(
            signup_route="competition", date_joined__gt=cutoff_date
        )
        count = users.count()
        users.update(signup_route=None)
        self.stdout.write(
            self.style.SUCCESS(f"Updated {count} users' signup_route to null.")
        )

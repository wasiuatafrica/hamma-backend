# myapp/management/commands/update_closed_at.py
from django.core.management.base import BaseCommand
from execution.models import DemoPosition
from competition.models import CompetitionPosition


class Command(BaseCommand):
    help = "Set closed_at field to updated field for closed positions"

    def handle(self, *args, **options):
        # Filter for positions that are closed and do not have closed_at set
        closed_positions = CompetitionPosition.objects.filter(
            status=CompetitionPosition.CLOSED, closed_at__isnull=True
        )
        count = closed_positions.count()

        for position in closed_positions:
            # Set closed_at to the value of the updated field (or you can use timezone.now() if needed)
            position.closed_at = position.updated
            position.save(update_fields=["closed_at"])

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {count} closed positions.")
        )

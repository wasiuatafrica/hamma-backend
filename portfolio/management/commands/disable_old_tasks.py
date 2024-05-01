from django.core.management.base import BaseCommand
from portfolio.tasks import disable_old_periodic_tasks  # Import the shared task

class Command(BaseCommand):
    help = "Disable all PeriodicTask objects not updated in the current month and year"

    def handle(self, *args, **kwargs):
        # Call the shared task to disable old PeriodicTask objects
        count = disable_old_periodic_tasks()

        # Provide feedback to the user
        self.stdout.write(
            self.style.SUCCESS(f"Successfully disabled {count} old periodic tasks.")
        )

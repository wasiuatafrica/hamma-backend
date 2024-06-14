from django.core.management.base import BaseCommand
from django.utils import timezone
from competition.models import Competition
import datetime

class Command(BaseCommand):
    help = 'Prints the date which is two weeks before the end date of the current competition'

    def handle(self, *args, **kwargs):
        try:
            # Fetch the current competition
            current_competition = Competition.objects.filter(status='current').first()
            print(current_competition.end_date)
            if current_competition:
                end_date = current_competition.end_date
                date_two_weeks_before = end_date - datetime.timedelta(weeks=2)
                self.stdout.write(self.style.SUCCESS(f"Date two weeks before the end of the current competition: {date_two_weeks_before}"))
            else:
                self.stdout.write(self.style.WARNING("No current competition found."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))

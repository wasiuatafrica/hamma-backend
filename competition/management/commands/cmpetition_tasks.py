from django.core.management.base import BaseCommand
from datetime import datetime
from competition.tasks import setup_competition_emails
from competition.models import Competition


class Command(BaseCommand):
    help = ""

    def handle(self, *args, **options):
        competition = Competition.objects.get(status="current")
        setup_competition_emails(competition.id)

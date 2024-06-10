from django.core.management.base import BaseCommand
from datacollection.tasks import collect_live, collect_merged

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        # collect_live()
        collect_merged()
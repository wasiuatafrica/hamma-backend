import json
from django.core.management.base import BaseCommand
from lock.models import SavingsLock


class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        savings =  SavingsLock.objects.all()
        for sav in savings:
            sav.interest_rate =10
            sav.save()

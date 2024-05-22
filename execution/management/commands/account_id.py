# /your_app/management/commands/generate_account_ids.py

from django.core.management.base import BaseCommand
from competition.models import CompetitionPortfolio
from execution.models import DemoPortfolio, Portfolio
import random
import string

class Command(BaseCommand):
    help = 'Generate unique account IDs for existing portfolios'

    def handle(self, *args, **options):
        for portfolio in CompetitionPortfolio.objects.all():
            portfolio.generate_unique_account_id()
            portfolio.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully generated account ID for portfolio {portfolio.pk}'))
            
        for portfolio in DemoPortfolio.objects.all():
            portfolio.generate_unique_account_id()
            portfolio.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully generated account ID for portfolio {portfolio.pk}'))
        
        for portfolio in Portfolio.objects.all():
            portfolio.generate_unique_account_id()
            portfolio.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully generated account ID for portfolio {portfolio.pk}'))



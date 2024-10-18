from django.core.management.base import BaseCommand
from stocknews.models import StockNews


class Command(BaseCommand):
    help = "Sets all existing StockNews objects to validated=True"

    def handle(self, *args, **kwargs):
        updated_count = StockNews.objects.update(validated=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_count} StockNews objects"
            )
        )

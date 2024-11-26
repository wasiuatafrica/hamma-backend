from django.core.management.base import BaseCommand
from prop.tasks import send_3days_pending_account_activation_mail


class Command(BaseCommand):

    def handle(self, *args, **options):
        data = send_3days_pending_account_activation_mail()
        print("done")

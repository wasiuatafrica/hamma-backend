
from tracemalloc import stop
from django.core.management.base import BaseCommand
from execution.tasks import stop_ec2_instance, start_ec2_instance


class Command(BaseCommand):

    def handle(self, *args, **options):
        stop_ec2_instance()
        # start_ec2_instance()
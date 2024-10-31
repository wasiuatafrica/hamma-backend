import json
from math import e
from django.core.management.base import BaseCommand
from competition.models import get_price
import portfolio
from portfolio.models import Stock
from execution.models import DemoPortfolio
from django.contrib.auth import get_user_model
from django.utils import timezone
from execution.tasks import (
    process_all_competition_limit_order_task,
    process_all_demo_limit_order_task,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Save all Stock symbols as JSON file"

    def handle(self, *args, **options):
        # process_all_demo_limit_order_task()
        # print("Demo Orders Processed")
        process_all_competition_limit_order_task()
        print("Competition Orders Processed")

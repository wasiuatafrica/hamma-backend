from django.core.management.base import BaseCommand
from portfolio.models import Stock
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from execution.tasks import update_live_1m

# Load environment variables
load_dotenv()


class Command(BaseCommand):
    help = 'get historical data'

    def handle(self, *args, **options):
        update_live_1m()
        
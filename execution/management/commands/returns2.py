import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from execution.tasks import get_daily_profit_loss2
from execution.models import DemoPosition, DemoProfitLoss
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from django.contrib.auth import get_user_model
from decimal import Decimal


User= get_user_model()

def connect_to_mongodb():
    client = MongoClient(os.environ.get("MONGO_STRING"), maxPoolSize=20, tls=True,
                         tlsAllowInvalidCertificates=True)
    db = client["stock_prices"]
    collection = db["price_combined"]
    return collection

def get_data(collection, day):
    three_days_ago = datetime.utcnow() - timedelta(days=day) + timedelta(hours=6)
    print(three_days_ago)
    query = {"ZENITHBANK.datetime": {"$lt": three_days_ago}}
    result = collection.find_one(query, sort=[("datetime", -1)])
    return result


class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        
        get_daily_profit_loss2()
        
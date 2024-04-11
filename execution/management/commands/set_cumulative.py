import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from execution.tasks import daily_returns, cumulative_returns
from execution.models import DemoPosition, DemoProfitLoss, DemoCumulativeReturns
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from django.contrib.auth import get_user_model
from decimal import Decimal
from portfolio.utils import get_price


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
    query = {"NGXGROUP.datetime": {"$lt": three_days_ago.isoformat()}}
    result = collection.find_one(query, sort=[("datetime")])
    return result


class Command(BaseCommand):
    help = ''

    def handle(self, *args, **options):
        users = User.objects.all()
        data = get_price ('ASI')
        pr = data['current_price']
        
        for user in users:            
            DemoCumulativeReturns.objects.create(user=user, ngx_price = pr)
            
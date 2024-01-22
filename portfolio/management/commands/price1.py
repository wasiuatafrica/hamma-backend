import pandas as pd
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from pymongo import MongoClient
import os

def connect_to_mongodb():
    client = MongoClient(os.environ.get("MONGO_STRING"),maxPoolSize=20,tls=True,
                             tlsAllowInvalidCertificates=True)
    db = client["stock_prices"]
    return db

def get_price():
    db = connect_to_mongodb()
    collection = db["price_combined"]
    last_item = collection.find_one(sort=[('_id', -1)])

    return last_item

def get_price2(symbol):
    db = connect_to_mongodb()
    collection = db["price_combined"]
    last_item = collection.find_one(sort=[('_id', -1)])

    return last_item[symbol]

class Command(BaseCommand):

    def handle(self, *args, **options):
        symbol="ZENITHBANK"
        data = get_price2(symbol)
        print(data)
        
       

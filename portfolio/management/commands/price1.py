import os

import pandas as pd
from django.core.management.base import BaseCommand
from pymongo import MongoClient

from portfolio.models import Stock


def connect_to_mongodb():
    client = MongoClient(
        os.environ.get("MONGO_STRING"),
        maxPoolSize=20,
        tls=True,
        tlsAllowInvalidCertificates=True,
    )
    # db = client["stock_prices"]
    db = client["livelake3"]
    return db


def get_price():
    db = connect_to_mongodb()
    collection = db["merged_live_price_trdv"]
    last_item = collection.find_one(sort=[("_id", -1)])

    return last_item


def get_price2(symbol):
    db = connect_to_mongodb()
    collection = db["merged_live_price_trdv"]
    last_item = collection.find_one(sort=[("_id", -1)])
    return last_item[symbol]


def delete_last_n_prices(n=4):
    db = connect_to_mongodb()
    collection = db["merged_live_price_trdv"]
    last_items = list(collection.find(sort=[("_id", -1)]).limit(n))
    deleted_count = 0
    for item in last_items:
        result = collection.delete_one({"_id": item["_id"]})
        if result.deleted_count == 1:
            deleted_count += 1
    return deleted_count


class Command(BaseCommand):

    def handle(self, *args, **options):
        # Fetch and print last item
        # last_item = get_price()
        # print("Last item:", last_item)

        # # Delete last 4 items
        deleted = delete_last_n_prices(4)
        print(f"Deleted {deleted} items from the collection.")

# your_app/management/commands/print_stock_data.py
import json
import os

import requests
from django.core.management.base import BaseCommand
from pymongo import MongoClient

from portfolio.models import Stock

client = MongoClient(os.environ.get("MONGO_STRING"),tls=True,
                             tlsAllowInvalidCertificates=True)

db_details = client["ngxlistedcompanies"]


class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
        stocks = Stock.objects.filter(active=True)
        print('stocks fetched')
        symbols = [stock.symbol for stock in stocks]
        response = requests.get("https://doclib.ngxgroup.com/REST/api/issuers/companydirectory?$orderby=CompanyName")
        data = response.text
        if data:
            print('data gotten')
            json_data = json.loads(data)
            for data in json_data:
                if data['Symbol'] in symbols:
                    collection = db_details[data['Symbol']]
                    collection.insert_one(data)
                    print(f"Inserted data for {data['Symbol']}")
                
       
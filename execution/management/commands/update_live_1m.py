from django.core.management.base import BaseCommand
from portfolio.models import Stock
from pymongo import MongoClient
import os
import pandas as pd
import pytz
from datetime import datetime, timedelta

MONGO_URL = os.environ.get('MONGO_URL')

def update_document(symbol, new_data):

    client = MongoClient(MONGO_URL)
    db = client['chartdata_1']
    collection = db[symbol]

    existing_document = collection.find_one()


    for key in ['t', 'o', 'h', 'l', 'c', 'v']:
        if key in new_data:
            if key in existing_document:
                print('before',len(existing_document[key]) )
                existing_document[key].extend(new_data[key])
                print('after',len(existing_document[key]) )
            

    # collection.update_one({"_id": document_id}, {"$set": existing_document})

    client.close()

def retrieve_today_live(symbol, interval):
  
    client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
    db = client["livelake3"]
    collection = db["merged_live_price"]

    lagos_tz = pytz.timezone("Africa/Lagos")
    today = datetime.now(lagos_tz).date()
    # reference_date_str = f"{today} 10:00:00"
    reference_date_str = "2024-05-10 10:00:00"
    reference_date = datetime.strptime(reference_date_str, "%Y-%m-%d %H:%M:%S").timestamp()

    data = list(collection.find({}))
    extracted_data = [doc[symbol] for doc in data if symbol in doc]

    df = pd.DataFrame(extracted_data)

    df.drop(["change", "percentage_change", "current_price", "volatility", "momentum"], axis=1, inplace=True)

    df['timestamp'] = pd.to_datetime(df['datetime']).apply(lambda dt: dt.timestamp())


    df_filtered = df[df['timestamp'] >= reference_date]

    df_filtered = df_filtered.sort_values(['symbol', 'timestamp'])
    df_filtered['volume_diff'] = df_filtered['volume'].diff()
    df_filtered = df_filtered[df_filtered['volume_diff'] != 0]
    df_filtered.drop('volume_diff', axis=1, inplace=True)
    
    df_filtered.dropna(inplace=True)
    
    return df_filtered


class Command(BaseCommand):
    help = 'get historical data'

    def handle(self, *args, **options):
        stocks = [stock.symbol for stock in Stock.objects.all()]
        for symbol in stocks:
            df = retrieve_today_live(symbol,"1")
            print('df',df)
            new_data = {
                "t": df["timestamp"].tolist(), 
                "o": df["open"].tolist(),  
                "h": df["high"].tolist(),  
                "l": df["low"].tolist(),  
                "c": df["close"].tolist(),  
                "v": df["volume"].tolist(), 
            }


            update_document(symbol, new_data)
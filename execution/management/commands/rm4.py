from django.core.management.base import BaseCommand
from pymongo import MongoClient
import os
from execution.tasks import retrieve_today_live, update_document, last_data

class Command(BaseCommand):
    help = 'Remove the last items in each list of a MongoDB document'

    def handle(self, *args, **kwargs):
        # Connect to MongoDB
        MONGO_URL = os.environ.get('MONGO_STRING')
        
        symbols= ["NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", 
          "OKOMUOIL", "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE", "RTBRISCOE", 
          "REDSTAREX", "REGALINS", "RONCHESS", "ROYALEX", "SCOA", "NSLTECH", "SEPLAT", "SFSREIT",
          "SKYAVN", "SMURFIT", "SOVRENINS", "STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", 
          "TANTALIZER", "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT", "TRANSCORP", 
          "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UNIONDICON", "UNHOMES", "UBA", "UCAP", 
          "UNITYBNK", "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", 
          "WEMABANK", "ZENITHBANK"]
    
        client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
        db = client["livelake3"]
        collection = db["merged_live_price"]
        last_item = collection.find_one(sort=[('_id', -1)])
        
        for symbol in symbols:
            df = last_data(last_item, symbol)
            if df.empty:
                print(f"No data available for {symbol} today")
                continue

            t = df["timestamp"].tolist()[-1]
            o = df["open"].tolist()[-1]
            h = df["high"].tolist()[-1]
            l = df["low"].tolist()[-1] 
            c = df["close"].tolist()[-1]  
            v = df["volume"].tolist()[-1]

            new_data = {
                "t": [t], 
                "o": [o],  
                "h": [h],  
                "l": [l],  
                "c": [c],  
                "v": [v], 
            }

            print(new_data)

            # update_document(symbol, 'chartdata_5', new_data) 
            update_document(symbol, 'chartdata_1D', new_data) 
            print('updated 5m', symbol)
           
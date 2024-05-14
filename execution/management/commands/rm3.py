from django.core.management.base import BaseCommand
from pymongo import MongoClient
import os
from execution.tasks import retrieve_today_live, update_document

class Command(BaseCommand):
    help = 'Remove the last items in each list of a MongoDB document'

    def handle(self, *args, **kwargs):
        # Connect to MongoDB
        MONGO_URL = os.environ.get('MONGO_STRING')
        client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
        db = client["chartdata_5"]
        
        symbols= ["UNIONDICON", "UNHOMES", "UBA", "UCAP", 
          "UNITYBNK", "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", 
          "WEMABANK", "ZENITHBANK"]
    
        for symbol in symbols:
            print(symbol)
            df = retrieve_today_live(symbol,"1")
            # print('df',df)
            if  df.empty:
                continue
            
            new_data = {
                "t": df["timestamp"].tolist(), 
                "o": df["open"].tolist(),  
                "h": df["high"].tolist(),  
                "l": df["low"].tolist(),  
                "c": df["close"].tolist(),  
                "v": df["volume"].tolist(), 
            }


            update_document(symbol,'chartdata_5', new_data) 
            print('updated 1m', symbol)

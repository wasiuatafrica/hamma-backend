from django.core.management.base import BaseCommand
from pymongo import MongoClient
import os

class Command(BaseCommand):
    help = 'Remove the last items in each list of a MongoDB document'

    def handle(self, *args, **kwargs):
        # Connect to MongoDB
        MONGO_URL = os.environ.get('MONGO_STRING')
        client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
        db = client["chartdata_5"]
        
        symbols= ["NAHCO", "NB", "ENAMELWA", "NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", 
          "OKOMUOIL", "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE", "RTBRISCOE", "RAKUNITY", 
          "REDSTAREX", "REGALINS", "RESORTSAL", "RONCHESS", "ROYALEX", "SCOA", "NSLTECH", "SEPLAT", "SFSREIT",
          "SKYAVN", "SMURFIT", "SOVRENINS", "STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", 
          "TANTALIZER", "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT", "TRANSCORP", 
          "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN", "UNIONDICON", "UNHOMES", "UBA", "UCAP", 
          "UNITYBNK", "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", 
          "WEMABANK", "ZENITHBANK"]
    
        for symbol in symbols:
            collection = db[symbol]

            # Retrieve the document
            document = collection.find_one()

            # Remove the last items in each list
            for key in ['t', 'o', 'h', 'l', 'c', 'v']:
                document[key] = document[key][:-1]

            # Update the document in MongoDB
            collection.update_one({'_id': document['_id']}, {'$set': document})

            # Close the MongoDB connection
            # client.close()

            self.stdout.write(self.style.SUCCESS(f'{symbol} removed'))

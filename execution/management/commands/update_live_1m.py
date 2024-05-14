from django.core.management.base import BaseCommand
from portfolio.models import Stock
from pymongo import MongoClient
import os
import pandas as pd
import pytz
from datetime import datetime, timedelta
from execution.tasks import update_live_1d, update_live_1m, update_live_1W, last_today_live

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
        symbols= ["ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA", "AIICO", 
          "AIRTELAFRI", "ALEX", "ARBICO", "ASOSAVINGS", "ABCTRANS", "AUSTINLAZ", "MANSARD", "BERGER", 
          "BETAGLAS", "BAPLC", "BUACEMENT", "BUAFOODS", "CILEASING", "CADBURY", "CAP", "CAPOIL", "CAVERTON", 
          "CHAMPION", "CHAMS", "NIDF", "CHELLARAM", "CONOIL", "CHIPLC", "CORNERST", "WAPIC", "CUSTODIAN", 
          "CUTIX", "CWG", "DAARCOMM", "DANGCEM", "DANGSUGAR", "DEAPCAP", "DUNLOP", "ETRANZACT", "ETI", 
          "EKOCORP", "ELLAHLAKES", "ETERNA", "EUNISELL", "FBNH", "FCMB", "FIDELITYBK", "FIDSON", "FLOURMILL",
          "FTNCOCOA", "GEREGU", "GLAXOSMITH", "GOLDBREW", "GOLDINSURE", "VANLEER", "GTCO", "GUINEAINS", 
          "GUINNESS", "HONYFLOUR", "IKEJAHOTEL", "IMG", "INFINITY", "INTBREW", "INTENEGINS", "JAIZBANK", 
          "JAPAULGOLD", "JOHNHOLT", "JULI", "JBERGER", "WAPCO", "LASACO", "LEARNAFRCA", "LINKASSURE", 
          "LIVESTOCK", "LIVINGTRUST", "MAYBAKER", "MCNICHOLS", "MEDVIEWAIR", "MEYER", "MORISON", "MRS", 
          "MTNN", "MULTITREX", "MULTIVERSE", "MBENEFIT", "NNFM", "NASCON", "NCR", "NEIMETH", "NEM", "NESTLE", 
          "NIGERINS", "NESF", "NAHCO", "NB", "ENAMELWA", "NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", 
          "OKOMUOIL", "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE", "RTBRISCOE", "RAKUNITY", 
          "REDSTAREX", "REGALINS", "RESORTSAL", "RONCHESS", "ROYALEX", "SCOA", "NSLTECH", "SEPLAT", "SFSREIT",
          "SKYAVN", "SMURFIT", "SOVRENINS", "STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", 
          "TANTALIZER", "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT", "TRANSCORP", 
          "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN", "UNIONDICON", "UNHOMES", "UBA", "UCAP", 
          "UNITYBNK", "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", 
          "WEMABANK", "ZENITHBANK"]
        
        last_today_live(symbols)
        
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from pymongo import MongoClient
import os
import pytz
from datetime import datetime
import pandas as pd
from execution.tasks import update_document

MONGO_URL = os.environ.get('MONGO_STRING')
mongo_client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
db_merged = mongo_client["livelake3"]
collection_merged = db_merged["merged_live_price"]

def retrieve_today_live(symbol):
  
    

    lagos_tz = pytz.timezone("Africa/Lagos")
    # today = datetime.now(lagos_tz).date()
    date_string = "2024-06-28"
    today = datetime.strptime(date_string, "%Y-%m-%d").date()

    pipeline = [
        {
            "$project": {
                "_id": 0,
                "documents": {
                    "$objectToArray": "$$ROOT"
                }
            }
        },
        {
            "$unwind": "$documents"
        },
        {
            "$match": {
                "$expr": {
                    "$eq": [
                        {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": {
                                    "$toDate": "$documents.v.datetime"
                                },
                                "timezone": "Africa/Lagos"
                            }
                        },
                        today.strftime("%Y-%m-%d")
                    ]
                },
                "documents.k": symbol  # Match documents for the given symbol only
            }
        },
        {
            "$replaceRoot": {
                "newRoot": "$documents.v"
            }
        }
    ]


    cursor = collection_merged.aggregate(pipeline)

    data = list(cursor)
    
    if data:  
        df = pd.DataFrame(data)

        df.drop(["change", "percentage_change", "current_price", "volatility", "momentum"], axis=1, inplace=True)

        df['timestamp'] = pd.to_datetime(df['datetime']).apply(lambda dt: dt.timestamp())

        df_filtered = df.sort_values(['symbol', 'timestamp'])
        df_filtered['volume_diff'] = df_filtered['volume'].diff()
        df_filtered = df_filtered[df_filtered['volume_diff'] != 0]
        # df_filtered.drop('volume_diff', axis=1, inplace=True)
        
        df_filtered.dropna(inplace=True)
        
        return df_filtered
    
    
class Command(BaseCommand):
    help = 'get historical data'

    def handle(self, *args, **options):
        stocks = ['CHAMS', 'CHELLARAM', 'CILEASING', 'CONOIL', 'CORNERST', 'CUSTODIAN', 'CUTIX', 'CWG', 'DAARCOMM', 'DANGCEM', 
                  'DANGSUGAR', 'DEAPCAP', 'DUNLOP', 'EKOCORP', 'ELLAHLAKES', 'ENAMELWA', 'ETERNA', 'ETI', 'ETRANZACT', 'EUNISELL', 'FBNH', 'FCMB', 
                  'FIDELITYBK', 'FIDSON', 'FLOURMILL', 'FTNCOCOA', 'GEREGU', 'GOLDBREW', 'GOLDINSURE', 'GTCO', 'GUINEAINS', 'GUINNESS', 'HONYFLOUR', 
                  'IKEJAHOTEL', 'IMG', 'INFINITY', 'INTBREW', 'INTENEGINS', 'JAIZBANK', 'JAPAULGOLD', 'JBERGER', 'JOHNHOLT', 'JULI', 'LASACO', 
                  'LEARNAFRCA', 'LINKASSURE', 'LIVESTOCK', 'LIVINGTRUST', 'MANSARD', 'MAYBAKER', 'MBENEFIT', 'MCNICHOLS', 'MEDVIEWAIR', 'MEYER', 
                  'MORISON', 'MRS', 'MTNN', 'MULTITREX', 'MULTIVERSE', 'NAHCO', 'NASCON', 'NB', 'NCR', 'NEIMETH', 'NEM', 'NESTLE', 'NGXGROUP', 
                  'NIDF', 'NIGERINS', 'NNFM', 'NOTORE', 'NPFMCRFBK', 'NSLTECH', 'OANDO', 'OKOMUOIL', 'OMATEK', 'PHARMDEKO', 'PREMPAINTS', 'PRESCO', 
                  'PRESTIGE', 'PZ', 'RAKUNITY', 'REDSTAREX', 'REGALINS', 'RESORTSAL', 'RONCHESS', 'ROYALEX', 'RTBRISCOE', 'SCOA', 'SEPLAT', 
                  'SFSREIT', 'SKYAVN', 'SMURFIT', 'SOVRENINS', 'STACO', 'STANBIC', 'STDINSURE', 'STERLINGNG', 'SUNUASSUR', 'TANTALIZER', 
                  'THOMASWY', 'TIP', 'TOTAL', 'TOURIST', 'TRANSCOHOT', 'TRANSCORP', 'TRANSEXPR', 'TRIPPLEG', 'UACN', 'UBA', 'UCAP', 'UHOMREIT', 
                  'UNHOMES', 'UNILEVER', 'UNIONDICON', 'UNITYBNK', 'UNIVINSURE', 'UPDC', 'UPDCREIT', 'UPL', 'VANLEER', 'VERITASKAP', 'VFDGROUP', 
                  'VITAFOAM', 'WAPCO', 'WAPIC', 'WEMABANK', 'ZENITHBANK']

        for symbol in stocks:
            print(symbol)
            df = retrieve_today_live(symbol)
            # print('df',df)
            if df is None or df.empty:
                continue
            
            new_data = {
                "t": df["timestamp"].tolist(), 
                "o": df["open"].tolist(),  
                "h": df["high"].tolist(),  
                "l": df["low"].tolist(),  
                "c": df["close"].tolist(),  
                "v": df["volume_diff"].tolist(), 
            }


            update_document(symbol,'chartdata_5', new_data) 
            print('updated 1m', symbol)
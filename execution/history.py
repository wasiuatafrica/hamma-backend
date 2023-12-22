from tvDatafeed import TvDatafeed, Interval
from pymongo import MongoClient
import json

def load_list(filename):
    with open(filename, 'r') as file:
        data = json.load(file)
        return data

def get_data(symbol):
    tv = TvDatafeed()
    dataframe = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_1_hour, n_bars=1000000000)
    return dataframe

def connect_to_mongodb():
    client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",
                         tls=True, tlsAllowInvalidCertificates=True)
    db = client["anyon_history"]
    return db

def symbol_exists_in_mongo(db, symbol):
    collections = db.list_collection_names()
    return str(symbol) in collections

def save_to_mongo(symbol, dataframe):
    if dataframe is None:
        print(f"Data for {symbol} could not be retrieved. Skipping...")
        return
    db = connect_to_mongodb()

    # Check if the symbol already exists in MongoDB
    if symbol_exists_in_mongo(db, symbol):
        print(f"Data for {symbol} already exists in MongoDB. Skipping...")
        return
    
    collection = db[str(symbol)]
    records = dataframe.reset_index().to_dict(orient='records')
    collection.insert_many(records)
    print(f"Data for {symbol} saved")

stocks = load_list('./symbols.json')

for symbol in stocks:
    data = get_data(symbol)
    save_to_mongo(symbol, data)
print('All data saved')
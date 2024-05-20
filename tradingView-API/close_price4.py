from tvDatafeed import TvDatafeed, Interval
from pymongo import MongoClient
from datetime import datetime, timedelta, time
import pytz
import pandas as pd
import numpy as np
import random
import time as module_time

tv = TvDatafeed()
symbols= ["ASI", "ABBEYBDS", "ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA", "AIICO", 
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
# symbols = ["WEMABANK", "ZENITHBANK"]

def connect_to_mongodb():
    client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",maxPoolSize=20,tls=True,
                             tlsAllowInvalidCertificates=True)
    db = client["stock_prices"]
    return db


def write_to_mongodb(data):
    db = connect_to_mongodb()
    collection = db["price_combined"]
    collection.insert_one(data)

def calculate_volatility_momentum(data, period):
    now = datetime.now()
    # data['datetime'] = pd.to_datetime(data.index)
    data.loc[:, 'datetime'] = pd.to_datetime(data.index)

    filtered_data = data[data['datetime'] >= (now - timedelta(days=period))].copy()
    
    if len(filtered_data) < 3:
        return None, None
    
    filtered_data['returns'] = (filtered_data['close'] - filtered_data['open']) / filtered_data['open']
    volatility = filtered_data['returns'].std() * np.sqrt(252 / period)
    start_price = filtered_data['close'].iloc[0]
    end_price = filtered_data['close'].iloc[-1]
    momentum = (end_price - start_price) / start_price * 100
    
    return round(volatility, 2), round(momentum, 2)

def get_data(symbol):
    data = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_1_minute, n_bars=2)

    if data is not None and not data.empty:
        data_reset = data.reset_index()
        last_two_rows = data_reset.iloc[-2:]
        last_data_dicts = [row.to_dict() for _, row in last_two_rows.iterrows()]
        close_change = last_two_rows['close'].diff().iloc[-1]
        
        last_data_dicts[-1]['change'] = round(close_change,2)
        
        if len(last_two_rows['close']) >= 2:
            close_percentage_change = (close_change / last_two_rows['close'].iloc[-2]) * 100
            last_data_dicts[-1]['percentage_change'] = round(close_percentage_change,2)
        else:
            close_percentage_change = 0

        last_data_dicts[-1]['current_price'] = last_data_dicts[-1]['close']

        for entry in last_data_dicts:
            entry['datetime'] = entry['datetime'].strftime('%Y-%m-%d %H:%M:%S')
        
        data2 = last_data_dicts[-1]
        if isinstance(data2, dict):
            return data2
        
def calculate_volatility_momentum_24hr(symbol):
    client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",maxPoolSize=20,tls=True,
                             tlsAllowInvalidCertificates=True)
    db = client["livelake3"]
    collection = db["merged_live_price"]
        
    data = list(collection.find().sort([('_id', -1)]).limit(270))
    # print(len(data ))
    
    if not data:
        print(f"No data found for symbol {symbol}")
        return None, None
    
    symbol_data = [entry[symbol] for entry in reversed(data) if symbol in entry]
    
    if not symbol_data:
        print(f"No data found for symbol {symbol}")
        return None, None
    
    df = pd.DataFrame(symbol_data)
    # print('df',df)
    df = df.dropna(subset=['open', 'close'])
    
    if df.empty:
        return None, None
    
    df['returns'] = (df['close'] - df['open']) / df['open']
    volatility = df['returns'].std() * np.sqrt(252)
    momentum = df['returns'].mean() * 100
    
    return round(volatility, 2), round(momentum, 2)
def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:
        market_open_time = time(9, 55)
        market_close_time = time(16, 30)

        if market_open_time <= current_time_lagos <= market_close_time:
            return True

    return False

while True:
    if is_market_open():
        data1 = {}
        for symbol in symbols:
            data3 = get_data(symbol)
            if data3 is not None:
                data_full = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_daily, n_bars=365)
                if data_full is not None:
                    
                    vol_mom_1week = calculate_volatility_momentum(data_full, 7)
                    vol_mom_1month = calculate_volatility_momentum(data_full, 30)
                    vol_mom_1year = calculate_volatility_momentum(data_full, 365)
                    
                    # Calculate year-to-date volatility and momentum
                    current_year = datetime.now().year
                    data_ytd = data_full[data_full.index.year == current_year]
                    vol_mom_ytd = calculate_volatility_momentum(data_ytd, len(data_ytd))
                    vol_mom_24hr = calculate_volatility_momentum_24hr(symbol)
                    
                    data3['volatility_1week'] = vol_mom_1week[0] if vol_mom_1week else None
                    data3['momentum_1week'] = vol_mom_1week[1] if vol_mom_1week else None
                    data3['volatility'] = vol_mom_1month[0] if vol_mom_1month else None
                    data3['momentum'] = vol_mom_1month[1] if vol_mom_1month else None
                    data3['volatility_1year'] = vol_mom_1year[0] if vol_mom_1year else None
                    data3['momentum_1year'] = vol_mom_1year[1] if vol_mom_1year else None
                    data3['volatility_ytd'] = vol_mom_ytd[0] if vol_mom_ytd else None
                    data3['momentum_ytd'] = vol_mom_ytd[1] if vol_mom_ytd else None
                    data3['volatility_24hr'] = vol_mom_24hr[0] if vol_mom_24hr else None
                    data3['momentum_24hr'] = vol_mom_24hr[1] if vol_mom_24hr else None
                else:
                    data3['volatility_1week'] = None
                    data3['momentum_1week'] = None
                    data3['volatility'] = None
                    data3['momentum'] = None
                    data3['volatility_1year'] = None
                    data3['momentum_1year'] = None
                    data3['volatility_ytd'] = None
                    data3['momentum_ytd'] = None
                    data3['volatility_24hr'] = None
                    data3['momentum_24hr'] = None

            data1[symbol] = data3
            print(data3)
            
        # print(data1)
        write_to_mongodb(data1)
        print("all data saved")
    else:
        print("Market closed")
    module_time.sleep(300)
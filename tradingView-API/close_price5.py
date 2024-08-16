from tvDatafeed import TvDatafeed, Interval
from pymongo import MongoClient
from datetime import datetime, timedelta, time
import pytz
import pandas as pd
import numpy as np
import random
import time as module_time

client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",maxPoolSize=20,tls=True,
                             tlsAllowInvalidCertificates=True)
db = client["stock_prices"]
db_merged = client["livelake3"]

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
          "NESF", "NAHCO", "NB", "ENAMELWA", "NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", 
          "OKOMUOIL", "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE", "RTBRISCOE", 
          "REDSTAREX", "REGALINS", "RONCHESS", "ROYALEX", "SCOA", "NSLTECH", "SEPLAT", "SFSREIT",
          "SKYAVN", "SMURFIT", "SOVRENINS", "STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", 
          "TANTALIZER", "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT", "TRANSCORP", 
          "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN", "UNIONDICON", "UNHOMES", "UBA", "UCAP", 
          "UNITYBNK", "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", 
          "WEMABANK", "ZENITHBANK"]

# symbols = ["WEMABANK", "ZENITHBANK"]



def write_to_mongodb(data):
    collection = db["price_combined"]
    collection.insert_one(data)


def calculate_volatility_momentum(data, period):
    now = datetime.now()
    data.loc[:, 'datetime'] = pd.to_datetime(data.index)

    filtered_data = data[data['datetime'] >= (now - timedelta(days=period))].copy()
    
    if len(filtered_data) < 3:
        return None, None, None, None, None
    
    # Handle NaN values in the dataset
    filtered_data = filtered_data.fillna(method='ffill').fillna(method='bfill')
    
    # Calculate returns
    # filtered_data['returns'] = (filtered_data['close'] - filtered_data['open']) / filtered_data['open']
    filtered_data['returns'] = filtered_data['close'].pct_change()
    
    # Handle potential NaN values in returns calculation
    # filtered_data['returns'].replace([np.inf, -np.inf], np.nan, inplace=True)
    filtered_data['returns'].fillna(0, inplace=True)
    
    # Calculate annualized volatility for the period
    volatility = filtered_data['returns'].std() * np.sqrt(252 / period)
    
    # Calculate price momentum
    start_price = filtered_data['close'].iloc[0]
    end_price = filtered_data['close'].iloc[-1]
    momentum_change = end_price - start_price
    momentum = momentum_change / start_price * 100
    
    # Calculate volume momentum
    start_volume = filtered_data['volume'].iloc[0]
    end_volume = filtered_data['volume'].iloc[-1]
    volume_momentum_change = end_volume - start_volume
    volume_momentum = (volume_momentum_change / start_volume) * 100
    
    return round(volatility, 2), round(momentum, 2), round(momentum_change, 2), round(volume_momentum, 2), round(volume_momentum_change, 2)


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
        
def calculate_volatility_momentum_24hr(symbol,data):
    

    df = data[-3:]
    df = df.dropna(subset=['open', 'close'])
    
    if df is None or df.empty:
        return None, None, None, None, None
    
    # df['returns'] = (df['close'] - df['open']) / df['open']
    df['returns'] = df['close'].pct_change() 
    # print(df)
    volatility = df['returns'].std() * np.sqrt(252/2)
    # momentum = df['returns'].mean() * 100
    
    start_price = df['close'].iloc[1]
    end_price = df['close'].iloc[-1]
    momentum_change = end_price - start_price
    momentum = (momentum_change / start_price) * 100
    
    start_volume = df['volume'].iloc[1]
    end_volume = df['volume'].iloc[-1]
    volume_momentum_change = end_volume - start_volume
    volume_momentum = (volume_momentum_change / start_volume) * 100
    
    return round(volatility, 2), round(momentum, 2), round(momentum_change,2) , round(volume_momentum, 2), round(volume_momentum_change, 2)

def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:
        # market_open_time = time(4, 5)
        market_open_time = time(10, 7)
        market_close_time = time(14, 40)

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
                    vol_mom_24hr = calculate_volatility_momentum_24hr(symbol,data_ytd)
                    
                    data3['volatility_1week'] = vol_mom_1week[0] if vol_mom_1week else None
                    data3['momentum_1week'] = vol_mom_1week[1] if vol_mom_1week else None
                    data3['momentum_change_1week'] = vol_mom_1week[2] if vol_mom_1week else None
                    data3['volume_momentum_1week'] = vol_mom_1week[3] if vol_mom_1week else None
                    data3['volume_momentum_change_1week'] = vol_mom_1week[4] if vol_mom_1week else None
                    
                    data3['volatility'] = vol_mom_1month[0] if vol_mom_1month else None
                    data3['momentum'] = vol_mom_1month[1] if vol_mom_1month else None
                    data3['momentum_change'] = vol_mom_1month[2] if vol_mom_1month else None
                    data3['volume_momentum'] = vol_mom_1month[3] if vol_mom_1month else None
                    data3['volume_momentum_change'] = vol_mom_1month[4] if vol_mom_1month else None
                    
                    
                    data3['volatility_1year'] = vol_mom_1year[0] if vol_mom_1year else None
                    data3['momentum_1year'] = vol_mom_1year[1] if vol_mom_1year else None
                    data3['momentum_change_1year'] = vol_mom_1year[2] if vol_mom_1year else None
                    data3['volume_momentum_1year'] = vol_mom_1year[3] if vol_mom_1year else None
                    data3['volume_momentum_change_1year'] = vol_mom_1year[4] if vol_mom_1year else None
                    
                    
                    data3['volatility_ytd'] = vol_mom_ytd[0] if vol_mom_ytd else None
                    data3['momentum_ytd'] = vol_mom_ytd[1] if vol_mom_ytd else None
                    data3['momentum_change_ytd'] = vol_mom_ytd[2] if vol_mom_ytd else None
                    data3['volume_momentum_ytd'] = vol_mom_ytd[3] if vol_mom_ytd else None
                    data3['volume_momentum_change_ytd'] = vol_mom_ytd[4] if vol_mom_ytd else None
                    
                    
                    data3['volatility_24hr'] = vol_mom_24hr[0] if vol_mom_24hr else None
                    data3['momentum_24hr'] = vol_mom_24hr[1] if vol_mom_24hr else None
                    data3['momentum_change_24hr'] = vol_mom_24hr[2] if vol_mom_24hr else None
                    data3['volume_momentum_24hr'] = vol_mom_24hr[3] if vol_mom_24hr else None
                    data3['volume_momentum_change_24hr'] = vol_mom_24hr[4] if vol_mom_24hr else None
                    
                else:
                    data3['volatility_1week'] = None
                    data3['momentum_1week'] = None
                    data3['momentum_change_1week'] = None
                    data3['volume_momentum_1week'] = None
                    data3['volume_momentum_change_1week'] = None
                    data3['volatility'] = None
                    data3['momentum'] = None
                    data3['momentum_change'] = None
                    data3['volume_momentum'] = None
                    data3['volume_momentum_change'] = None
                    data3['volatility_1year'] = None
                    data3['momentum_1year'] = None
                    data3['momentum_change_1year'] = None
                    data3['volume_momentum_1year'] = None
                    data3['volume_momentum_change_1year'] = None
                    
                    data3['volatility_ytd'] = None
                    data3['momentum_ytd'] = None
                    data3['momentum_change_ytd'] = None
                    data3['volume_momentum_ytd'] = None
                    data3['volume_momentum_change_ytd'] = None
                    
                    data3['volatility_24hr'] = None
                    data3['momentum_24hr'] = None
                    data3['momentum_change_24hr'] = None
                    data3['volume_momentum_24hr'] = None
                    data3['volume_momentum_change_24hr'] = None
                    

            data1[symbol] = data3
            print(data3)
            
        # print(data1)
        write_to_mongodb(data1)
        print("all data saved")
    else:
        print("Market closed")
    module_time.sleep(900)
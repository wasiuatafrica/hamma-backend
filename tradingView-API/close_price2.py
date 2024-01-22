from tvDatafeed import TvDatafeed, Interval
import time as module_time
from pymongo import MongoClient
from datetime import datetime, time
import pytz

tv = TvDatafeed()
symbols= ["ABBEYBDS", "ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA", "AIICO", 
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

def connect_to_mongodb():
    client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",maxPoolSize=20,tls=True,
                             tlsAllowInvalidCertificates=True)
    db = client["stock_prices"]
    return db


def write_to_mongodb(data):
    db = connect_to_mongodb()
    collection = db["price_combined"]
    collection.insert_one(data)
    
def get_data(symbol):
    data = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_1_minute, n_bars=2)

    if data is not None and not data.empty:
        data_reset = data.reset_index()

        last_two_rows = data_reset.iloc[-2:]

        # Convert the last two rows to dictionaries
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
            print(data2)
            return data2
        
def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:
        market_open_time = time(9, 30)
        market_close_time = time(14, 30)

        if market_open_time <= current_time_lagos <= market_close_time:
            return True

    return False

        
while True:
    if is_market_open():
        data1 =  {}
        for symbol in symbols:
            data3 = get_data(symbol)
            print(data3)
            data1[symbol] = data3
            

        write_to_mongodb(data1)
        print("all data saved")
    else:
        print("Market closed")
    module_time.sleep(300)
from tvDatafeed import TvDatafeed, Interval
import time
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor


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

# symbols = ["WEMABANK", "ZENITHBANK"]

def connect_to_mongodb():
    client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",maxPoolSize=20,tls=True,
                             tlsAllowInvalidCertificates=True)
    db = client["stock_prices"]
    return db


def write_to_mongodb(symbol,data):
    db = connect_to_mongodb()
    collection = db[symbol]
    collection.insert_one(data)
    
def get_data(symbol):
    data = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_1_minute, n_bars=2)

    # Check if data is None before processing
    if data is not None and not data.empty:
        data_reset = data.reset_index()

        # Extract the last two rows
        last_two_rows = data_reset.iloc[-2:]

        # Convert the last two rows to dictionaries
        last_data_dicts = [row.to_dict() for _, row in last_two_rows.iterrows()]

        close_change = last_two_rows['close'].diff().iloc[-1]
        
        last_data_dicts[-1]['close_change'] = round(close_change,2)
        
        if len(last_two_rows['close']) >= 2:
            close_percentage_change = (close_change / last_two_rows['close'].iloc[-2]) * 100
            last_data_dicts[-1]['close_percentage_change'] = round(close_percentage_change,2)
        else:
            close_percentage_change = 0

        # Add change and percentage change to the last item's dictionary

        # Add 'current_price' key with the closing price value
        last_data_dicts[-1]['current_price'] = last_data_dicts[-1]['close']

        # Format the 'datetime' field as a string
        for entry in last_data_dicts:
            entry['datetime'] = entry['datetime'].strftime('%Y-%m-%d %H:%M:%S')
        
        data2 = last_data_dicts[-1]
        # if isinstance(data2, dict):
        #     write_to_mongodb(symbol,data2)

        print(data2)
        # return last_data_dicts[-1]

while True:
    # with ThreadPoolExecutor() as executor:
    #     futures = executor.map(get_data, symbols)
            
    for symbol in symbols:
        get_data(symbol)
from pymongo import MongoClient
from tvDatafeed import Interval, TvDatafeed
import os
from pathlib import Path
import environ

environ.Env.read_env(Path(__file__).resolve().parent.parent / ".env")

tv = TvDatafeed()

symbols = [
    "ABBEYBDS",
    "ACADEMY",
    "ACCESSCORP",
    "AFRIPRUD",
    "AFRINSURE",
    "AFROMEDIA",
    "AIICO",
    "AIRTELAFRI",
    "ALEX",
    "ARBICO",
    "ASOSAVINGS",
    "ABCTRANS",
    "AUSTINLAZ",
    "MANSARD",
    "BERGER",
    "BETAGLAS",
    "BAPLC",
    "BUACEMENT",
    "BUAFOODS",
    "CILEASING",
    "CADBURY",
    "CAP",
    "CAPOIL",
    "CAVERTON",
    "CHAMPION",
    "CHAMS",
    "NIDF",
    "CHELLARAM",
    "CONOIL",
    "CHIPLC",
    "CORNERST",
    "WAPIC",
    "CUSTODIAN",
    "CUTIX",
    "CWG",
    "DAARCOMM",
    "DANGCEM",
    "DANGSUGAR",
    "DEAPCAP",
    "DUNLOP",
    "ETRANZACT",
    "ETI",
    "EKOCORP",
    "ELLAHLAKES",
    "ETERNA",
    "EUNISELL",
    "FBNH",
    "FCMB",
    "FIDELITYBK",
    "FIDSON",
    "FLOURMILL",
    "FTNCOCOA",
    "GEREGU",
    "GLAXOSMITH",
    "GOLDBREW",
    "GOLDINSURE",
    "VANLEER",
    "GTCO",
    "GUINEAINS",
    "GUINNESS",
    "HONYFLOUR",
    "IKEJAHOTEL",
    "IMG",
    "INFINITY",
    "INTBREW",
    "INTENEGINS",
    "JAIZBANK",
    "JAPAULGOLD",
    "JOHNHOLT",
    "JULI",
    "JBERGER",
    "WAPCO",
    "LASACO",
    "LEARNAFRCA",
    "LINKASSURE",
    "LIVESTOCK",
    "LIVINGTRUST",
    "MAYBAKER",
    "MCNICHOLS",
    "MEDVIEWAIR",
    "MEYER",
    "MORISON",
    "MRS",
    "MTNN",
    "MULTITREX",
    "MULTIVERSE",
    "MBENEFIT",
    "NNFM",
    "NASCON",
    "NCR",
    "NEIMETH",
    "NEM",
    "NESTLE",
    "NIGERINS",
    "NESF",
    "NAHCO",
    "NB",
    "ENAMELWA",
    "NGXGROUP",
    "NOTORE",
    "NPFMCRFBK",
    "OANDO",
    "OKOMUOIL",
    "OMATEK",
    "PZ",
    "PHARMDEKO",
    "PREMPAINTS",
    "PRESCO",
    "PRESTIGE",
    "RTBRISCOE",
    "RAKUNITY",
    "REDSTAREX",
    "REGALINS",
    "RESORTSAL",
    "RONCHESS",
    "ROYALEX",
    "SCOA",
    "NSLTECH",
    "SEPLAT",
    "SFSREIT",
    "SKYAVN",
    "SMURFIT",
    "SOVRENINS",
    "STACO",
    "STANBIC",
    "STDINSURE",
    "STERLINGNG",
    "SUNUASSUR",
    "TANTALIZER",
    "TIP",
    "THOMASWY",
    "TOTAL",
    "TOURIST",
    "TRANSEXPR",
    "TRANSCOHOT",
    "TRANSCORP",
    "TRIPPLEG",
    "UACN",
    "UHOMREIT",
    "UNILEVER",
    "UBN",
    "UNIONDICON",
    "UNHOMES",
    "UBA",
    "UCAP",
    "UNITYBNK",
    "UNIVINSURE",
    "UPL",
    "UPDC",
    "UPDCREIT",
    "VERITASKAP",
    "VFDGROUP",
    "VITAFOAM",
    "WEMABANK",
    "ZENITHBANK",
]


def connect_to_mongodb():
    client = MongoClient(
        os.environ["MONGO_STRING"],
        maxPoolSize=20,
        tls=True,
        tlsAllowInvalidCertificates=True,
    )
    db = client["chart_data0"]
    return db


def write_to_mongodb(symbol, data):
    db = connect_to_mongodb()
    collection = db[symbol]
    collection.insert_many(data)


def get_data(symbol):
    data = tv.get_hist(
        symbol=symbol, exchange="NSENG", interval=Interval.in_1_minute, n_bars=12390010
    )

    if data is not None and not data.empty:
        # Create new columns for change in closing price and percentage change
        data["change"] = (
            data["close"].diff().round(2)
        )  # Change in closing price from previous row
        data["percent_change"] = (
            (data["change"] / data["close"].shift(1)) * 100
        ).round(
            2
        )  # Percentage change in closing price

        data["change"] = data["change"].fillna(0)  # Fill NaN values with 0
        data["percent_change"] = data["percent_change"].fillna(
            0
        )  # Fill NaN values with 0

        # Convert datetime to string format
        data.reset_index(
            inplace=True
        )  # Reset the index to ensure `datetime` is part of the columns
        data["datetime"] = data["datetime"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M:%S")
        )  # Format datetime to string

        # Optionally, you could convert the DataFrame to dictionary of records
        data_dict = data.to_dict(orient="records")

        # Print head and tail for demonstration
        print(data.head(5))
        print(data.tail(5))
        print(data_dict[-1])
        write_to_mongodb(symbol, data_dict)


get_data("CUTIX")

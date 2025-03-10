from django.core.management.base import BaseCommand
from execution.tasks import update_document
from tvDatafeed import TvDatafeed, Interval
from portfolio.models import Stock

tv = TvDatafeed()


class Command(BaseCommand):
    help = "get historical data"

    def handle(self, *args, **options):
        # symbols = [
        #     stock.symbol
        #     for stock in Stock.objects.filter(active=True, symbol__gt="FBNH").order_by(
        #         "symbol"
        #     )
        # ]
        # print(symbols)

        symbols = [
            # "FCMB",
            # "FIDELITYBK",
            # "FIDSON",
            # "FTNCOCOA",
            # "GEREGU",
            # "GOLDBREW",
            # "GOLDINSURE",
            # "GTCO",
            # "GUINEAINS",
            # "GUINNESS",
            # "HONYFLOUR",
            # "IKEJAHOTEL",
            # "IMG",
            # "INFINITY",
            # "INTBREW",
            # "INTENEGINS",
            # "JAIZBANK",
            # "JAPAULGOLD",
            # "JBERGER",
            # "JOHNHOLT",
            # "JULI",
            # "LASACO",
            # "LEARNAFRCA",
            # "LINKASSURE",
            # "LIVESTOCK",
            # "LIVINGTRUST",
            # "MANSARD",
            # "MAYBAKER",
            # "MBENEFIT",
            # "MCNICHOLS",
            # "MEDVIEWAIR",
            # "MEYER",
            # "MORISON",
            # "MRS",
            # "MTNN",
            # "MULTITREX",
            # "MULTIVERSE",
            # "NAHCO",
            # "NASCON",
            # "NB",
            # "NCR",
            # "NEIMETH",
            # "NEM",
            # "NESTLE",
            # "NGXGROUP",
            # "NIDF",
            # "NNFM",
            # "NOTORE",
            # "NPFMCRFBK",
            # "NSLTECH",
            # "OANDO",
            # "OKOMUOIL",
            # "OMATEK",
            # "PHARMDEKO",
            # "PREMPAINTS",
            # "PRESCO",
            # "PRESTIGE",
            # "PZ",
            # "REDSTAREX",
            # "REGALINS",
            # "RONCHESS",
            # "ROYALEX",
            # "RTBRISCOE",
            # "SCOA",
            # "SEPLAT",
            # "SFSREIT",
            # "SKYAVN",
            # "SMURFIT",
            # "SOVRENINS",
            # "STACO",
            # "STANBIC",
            # "STDINSURE",
            # "STERLINGNG",
            # "SUNUASSUR",
            # "TANTALIZER",
            # "THOMASWY",
            # "TIP",
            # "TOTAL",
            # "TRANSCOHOT",
            # "TRANSCORP",
            # "TRANSEXPR",
            # "TRIPPLEG",
            # "UACN",
            # "UBA",
            # "UCAP",
            # "UHOMREIT",
            # "UNILEVER",
            # "UNIONDICON",
            "UNITYBNK",
            "UNIVINSURE",
            "UPDC",
            "UPDCREIT",
            "UPL",
            "VANLEER",
            "VERITASKAP",
            "VFDGROUP",
            "VITAFOAM",
            "WAPCO",
            "WAPIC",
            "WEMABANK",
            "ZENITHBANK",
        ]

        for symbol in symbols:
            df = tv.get_hist(
                symbol,
                "NSENG",
                Interval.in_daily,
                n_bars=4,
            )
            print(df)
            df.reset_index(inplace=True)
            df["timestamp"] = df["datetime"].apply(lambda x: int(x.timestamp()))

            t = df["timestamp"].tolist()
            o = df["open"].tolist()
            h = df["high"].tolist()
            l = df["low"].tolist()
            c = df["close"].tolist()
            v = df["volume"].tolist()

            new_data = {
                "t": t[:-1],
                "o": o[:-1],
                "h": h[:-1],
                "l": l[:-1],
                "c": c[:-1],
                "v": v[:-1],
            }

            print(new_data)

            update_document(symbol, "chartdata_1D", new_data)
            print("updated 1D", symbol)
            # break

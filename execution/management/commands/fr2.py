from django.core.management.base import BaseCommand
from execution.tasks import update_document
from tvDatafeed import TvDatafeed, Interval

tv = TvDatafeed()


class Command(BaseCommand):
    help = "get historical data"

    def handle(self, *args, **options):

        symbols = [
            # "TRANSCOHOT",
            # "TRANSCORP",
            # "TRANSEXPR",
            # "TRIPPLEG",
            # "UACN",
            # "UBA",
            # "UCAP",
            # "UHOMREIT",
            # "UNHOMES",
            # "UNILEVER",
            # "UNIONDICON",
            # "UNITYBNK",
            # "UNIVINSURE",
            # "UPDC",
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
                n_bars=20,
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
                "t": t,
                "o": o,
                "h": h,
                "l": l,
                "c": c,
                "v": v,
            }

            print(new_data)

            update_document(symbol, "chartdata_1D", new_data)
            print("updated 1D", symbol)
            # break

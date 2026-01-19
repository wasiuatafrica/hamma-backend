import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from bson import json_util
from django.contrib.auth import get_user_model
from openai import OpenAI
from pymongo import MongoClient

from execution.symbol_pair import pairs
from portfolio.serializers import AlertSerializer
from stocknews.models import StockNews

from .models import Alert, AlertAI, Conversation, Message
from .serializers import StockNewsSerializer

User = get_user_model()
client = MongoClient(
    os.environ.get("MONGO_STRING"), tls=True, tlsAllowInvalidCertificates=True
)

db_merged = client["livelake3"]
db_details = client["ngxlistedcompanies"]
db_fundamental = client["ngxfundamentals"]
db_calendar = client["ngxcalendar"]
signal_db = client["trade_signals"]


def connect_to_mongodb(db_name):

    # db = client["anyon_orderbook"]
    db = client[db_name]
    return db


def get_symbol_data(symbol):
    db = connect_to_mongodb("anyon_orderbook")
    collection = db[symbol]

    # Sort the records in descending order based on some timestamp field (replace 'timestamp' with your actual field)
    records_cursor = collection.find().sort("timestamp", -1).limit(10)

    json_data = [
        {
            "symbol": record["symbol"],
            "datetime": record["datetime"],
            "bid_price": round(record["bid_price"], 2),
            "ask_price": round(record["ask_price"], 2),
            "bid_quantity": record["bid_quantity"],
            "ask_quantity": record["ask_quantity"],
        }
        for record in records_cursor
    ]
    return json_data


def get_historical_data(symbol):
    db = connect_to_mongodb("anyon_history")
    collection = db[symbol]
    records = list(collection.find())
    serialized_records = json.loads(json_util.dumps(records))
    return serialized_records


def get_trend(closing_prices):
    # Function to determine the trend (up or down) based on closing prices
    if closing_prices[-1] > closing_prices[0]:
        return "up"
    elif closing_prices[-1] < closing_prices[0]:
        return "down"
    else:
        return "neutral"


def get_mini_data():
    db = connect_to_mongodb("anyon_history")
    collection_names = db.list_collection_names()
    result_list = []

    for collection_name in collection_names:
        collection = db[collection_name]
        last_27_items = list(collection.find().sort("datetime", -1).limit(27))

        if len(last_27_items) >= 2:
            closing_prices = [item["close"] for item in last_27_items]
            trend = get_trend(closing_prices)
        else:
            trend = "insufficient_data"

        result_list.append({collection_name: trend})

    return result_list


def get_price(symbol):

    # collection = db_merged["merged_live_price"]
    collection = db_merged["merged_live_price_trdv"]
    last_item = collection.find_one(sort=[("_id", -1)])
    # print(symbol)
    return last_item[symbol]


def get_details(stock):
    data = get_price(stock.symbol)
    details = {
        "company": stock.company,
        "symbol": stock.symbol,
        "sector": stock.sector,
        "current_price": data["current_price"],
        "percent_change": data["percentage_change"],
        "change": round(data["current_price"] - data["open_price"], 2),
    }

    return details


def get_stockdata2():
    # collection = db_merged["merged_live_price"]
    collection = db_merged["merged_live_price_trdv"]

    # Each document contains multiple stocks as keys, each with a datetime field
    # Since all stocks in a document have the same datetime, we can sort by any stock's datetime
    # We'll try common stocks first (MTNN, ACCESSCORP, etc.) and fallback to _id

    # Try sorting by a common stock's datetime (MTNN is usually present)
    common_stocks = ["MTNN", "ACCESSCORP", "GTCO", "ZENITHBANK", "UBA"]

    for stock_symbol in common_stocks:
        try:
            last_item = collection.find_one(
                {f"{stock_symbol}.datetime": {"$exists": True}},
                sort=[(f"{stock_symbol}.datetime", -1)],
            )
            if last_item:
                return last_item
        except Exception:
            continue

    # Fallback: use _id (ObjectId contains timestamp)
    return collection.find_one(sort=[("_id", -1)])


def get_details2(stock, stock_data):
    data = stock_data.get(stock.symbol, {})

    # print(data)

    if data:
        return {
            "company": stock.company,
            "symbol": stock.symbol,
            "sector": stock.sector,
            "logo_url": stock.logo_url,
            "current_price": data.get("current_price"),
            "percent_change": data.get("percentage_change"),
            "change": data.get("change"),
            "volume": data.get("volume"),
            "momentum": data.get("momentum"),
            "momentum_change": data.get("momentum_change"),
            "volume_momentum": data.get("volume_momentum"),
            "volume_momentum_change": data.get("volume_momentum_change"),
            "volatility": data.get("volatility"),
            "volatility_1week": data.get("volatility_1week"),
            "momentum_1week": data.get("momentum_1week"),
            "momentum_change_1week": data.get("momentum_change_1week"),
            "volume_momentum_1week": data.get("volume_momentum_1week"),
            "volume_momentum_change_1week": data.get("volume_momentum_change_1week"),
            "volatility_1year": data.get("volatility_1year"),
            "momentum_1year": data.get("momentum_1year"),
            "momentum_change_1year": data.get("momentum_change_1year"),
            "volume_momentum_1year": data.get("volume_momentum_1year"),
            "volume_momentum_change_1year": data.get("volume_momentum_change_1year"),
            "volatility_ytd": data.get("volatility_ytd"),
            "momentum_ytd": data.get("momentum_ytd"),
            "momentum_change_ytd": data.get("momentum_change_ytd"),
            "volume_momentum_ytd": data.get("volume_momentum_ytd"),
            "volume_momentum_change_ytd": data.get("volume_momentum_change_ytd"),
            "volatility_24hr": data.get("volatility_24hr"),
            "momentum_24hr": data.get("momentum_24hr"),
            "momentum_change_24hr": data.get("momentum_change_24hr"),
            "volume_momentum_24hr": data.get("volume_momentum_24hr"),
            "volume_momentum_change_24hr": data.get("volume_momentum_change_24hr"),
        }
    else:
        # Handle the case when data is not available for the symbol
        return {
            "company": stock.company,
            "symbol": stock.symbol,
            "logo_url": stock.logo_url,
            "sector": stock.sector,
            "current_price": 0,
            "percent_change": 0,
            "change": 0,
        }


def handle_special_values(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0  # or any default value you prefer
    return value


def get_details3(stocks):
    stockdata = get_stockdata2()
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_details2, stock, stockdata) for stock in stocks]
        performance_data = [future.result() for future in futures]
    return performance_data


def get_alert_data(prompt):
    client = OpenAI()

    model = """
    class Alert(auto_prefetch.Model):
        user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
        stock= auto_prefetch.ForeignKey(Stock,on_delete=models.CASCADE)
        alert_name=models.CharField(max_length=50)
        description=models.TextField(default="")
        alert_type=models.CharField(max_length=30, choices=(("price", "price"), ("volume", "volume")), default='price')
        action=models.CharField(max_length=50, choices=(("above", "above"), ("below", "below")))
        to_price=models.FloatField(blank=True, null=True)
        to_volume=models.FloatField(blank=True, null=True)    
        frequency=models.CharField(max_length=50, choices=(("Once","Once"),("Everytime", "Everytime")))
        expire = models.DateTimeField(default=datetime.now() +timedelta(weeks=7))
        
    """
    # prompt = '''
    # notify me for ZENITHBANK stock everytime the volume goes below 9320 before 7 january 2024 3pm
    # '''
    # prompt = '''
    # alert me everytime WEMABANK price goes below 93.20 before 7 january 2024 3pm
    # '''

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful django software development assistant helping in creating a trading app alert system.",
            },
            {
                "role": "user",
                "content": f"""i have company name and symbol pairing {pairs} useful for getting appropriate symbol that will be value of "stocks".
         i want to extract parameters from - {prompt} - to create djano model {model} can you 
            extract the needed parameter in python dictionary  format only as the response, the expected dict keys are stock,alert_type,action,to_price or to_volume and frequency. if there is no element of frequency in  the text, then "frequency":"Once".
            don't write write any explanation before or after the dictionary,all keys and values must be string and in double quotation marks. I only want the dictionary as response, nothing else, dont explain anything even if you made assumptions""",
            },
        ],
    )

    # print(response)
    # print(response['choices'][0]['message']['content'])
    return response.choices[0].message.content


from channels.db import database_sync_to_async


@database_sync_to_async
def get_alert_prompt_history(id):
    user = User.objects.get(id=id)

    alerts_query = AlertAI.objects.filter(user=user, alert_created=True)
    if alerts_query:
        alerts = [(alert.prompt, alert.created.isoformat()) for alert in alerts_query]
        alerts_sorted = sorted(alerts, key=lambda x: x[1], reverse=True)
        return alerts_sorted


@database_sync_to_async
def get_conversation(name, user):
    conversation, created = Conversation.objects.get_or_create(name=name, user=user)
    if created:
        client = OpenAI()
        thread = client.beta.threads.create()
        conversation.thread_id = thread.id
        conversation.save()
    return conversation


@database_sync_to_async
def get_messages(conversation):
    messages = Message.objects.filter(room=conversation)
    return messages


from django.utils import timezone


def get_alerts(user):

    current_month_start = timezone.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    current_month_end = current_month_start.replace(
        month=current_month_start.month + 1
    ) - timezone.timedelta(seconds=1)

    alerts_query = Alert.objects.filter(
        created__range=(current_month_start, current_month_end), user=user
    )
    alerts = AlertSerializer(alerts_query, many=True).data
    print("serialize", alerts)
    return alerts


def get_symbol_overview(symbol):
    collection = db_details[symbol]
    company_data = collection.find_one({})
    overview = {}

    overview["marketcap"] = float(company_data.get("PrevClose")) * float(
        company_data.get("SharesOutstanding", 0)
    )
    # overview['shares'] = company_data.get('SharesOutstanding')
    overview["CompanyName"] = company_data.get("CompanyName")
    overview["Sector"] = company_data.get("Sector")
    overview["SubSector"] = company_data.get("SubSector")
    overview["dividend"] = company_data.get("dividend", 0)
    overview["MarketClassification"] = company_data.get("MarketClassification")
    overview["DateOfIncorporation"] = company_data.get("DateOfIncorporation")
    overview["Website"] = company_data.get("Website")
    overview["NatureofBusiness"] = company_data.get("NatureofBusiness")
    overview["CompanyAddress"] = company_data.get("CompanyAddress")
    overview["Telephone"] = company_data.get("Telephone")
    overview["HIGH52WK_PRICE"] = company_data.get("HIGH52WK_PRICE")
    overview["LOW52WK_PRICE"] = company_data.get("LOW52WK_PRICE")
    overview["BoardOfDirectors"] = company_data.get("BoardOfDirectors")
    overview["Email"] = company_data.get("Email")
    # overview['Email'] = company_data.get('Email')
    # overview['Email'] = company_data.get('Email')
    # overview['Email'] = company_data.get('Email')

    return overview


def get_symbol_fundamentals(symbol):
    collection = db_fundamental[symbol]
    company_data = collection.find_one({})
    if company_data:
        company_data.pop("_id", None)
        return company_data
    return {}


def get_stock_news(symbol):
    news = StockNews.objects.filter(stock__symbol=symbol, validated=True).order_by(
        "-published_date"
    )[:10]
    news_data = StockNewsSerializer(news, many=True).data
    return news_data


# def get_calendar(symbol):
#     collection = db_calendar[symbol]
#     company_data = collection.find_one({})
#     if company_data:
#         company_data.pop("_id", None)
#         return company_data
#     return {}


def get_calendar(symbol):
    collection = db_calendar[symbol]
    company_data = collection.find_one({})
    if company_data:
        company_data.pop("_id", None)

        # Get current date
        current_date = datetime.now().date()

        # Calculate the date 5 years ago
        five_years_ago = current_date - timedelta(days=5 * 365)

        # Filter and sort events
        filtered_events = [
            event
            for event in company_data.get("events", [])
            if datetime.strptime(event["date"], "%Y-%m-%d").date() >= five_years_ago
        ]

        sorted_events = sorted(filtered_events, key=lambda x: x["date"], reverse=True)

        company_data["events"] = sorted_events
        return company_data
    return {}


def get_signal(symbol):
    signal_collection = signal_db["signals"]
    signals_data = signal_collection.find_one(sort=[("_id", -1)])
    company_data = signals_data[symbol]
    if company_data:
        # print("here")
        company_data.pop("_id", None)
        return company_data
    return {}

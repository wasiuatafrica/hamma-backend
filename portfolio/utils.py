import hashlib
import json
import math
import os
from datetime import datetime, timedelta

from bson import json_util
from django.contrib.auth import get_user_model
from django.core.cache import cache
from backend.lazy import OpenAI
from pymongo import MongoClient

from execution.symbol_pair import pairs
from portfolio.company_profile import get_symbol_overview
from portfolio.serializers import AlertSerializer
from stocknews.models import StockNews

from .models import Alert, AlertAI, Conversation, Message
from .prices import PriceUnavailable, get_price, get_prices_map  # noqa: F401 (re-exported)
from .serializers import StockNewsSerializer

User = get_user_model()
client = MongoClient(os.environ.get("MONGO_STRING"), tls=True)

db_merged = client["livelake3"]
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
    """Latest usable prices keyed by symbol; see prices.get_prices_map()."""
    return get_prices_map()


LOGO_URL_CACHE_SECONDS = 12 * 60 * 60  # presigned URLs are valid for 24h


def get_cached_logo_url(stock):
    """Presigned logo URL, cached so list endpoints don't sign ~150 URLs per call."""
    if not stock.logo_url:
        return None
    digest = hashlib.md5(stock.logo_url.encode()).hexdigest()
    key = f"stock_logo_url:{stock.pk}:{digest}"
    try:
        url = cache.get(key)
    except Exception:
        url = None
    if url is None:
        url = stock.get_signed_logo_url()
        try:
            cache.set(key, url, LOGO_URL_CACHE_SECONDS)
        except Exception:
            pass
    return url


def _stock_fields(stock):
    return {
        "company": stock.company,
        "symbol": stock.symbol,
        "sector": stock.sector,
        "logo_url": get_cached_logo_url(stock),
        "tv_symbol": stock.tv_symbol,
        "ngx_status": stock.ngx_status,
        "is_active": stock.active,
    }


def _json_safe(details):
    """NaN/Infinity are not valid JSON and would break the whole response."""
    return {
        key: None if isinstance(value, float) and not math.isfinite(value) else value
        for key, value in details.items()
    }


def get_details2(stock, stock_data):
    data = stock_data.get(stock.symbol, {})

    if data:
        return _json_safe({
            **_stock_fields(stock),
            "current_price": data.get("current_price"),
            "percent_change": data.get("percentage_change"),
            "change": data.get("change"),
            "price_status": "stale" if data.get("is_stale") else "live",
            "as_of": data.get("as_of") or data.get("datetime"),
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
        })
    else:
        # No usable price: return nulls, never 0, so clients can show "unavailable"
        return {
            **_stock_fields(stock),
            "current_price": None,
            "percent_change": None,
            "change": None,
            "price_status": "unavailable",
            "as_of": None,
        }


def handle_special_values(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0  # or any default value you prefer
    return value


def get_details3(stocks):
    stockdata = get_stockdata2()
    return [get_details2(stock, stockdata) for stock in stocks]


def is_tradeable(detail):
    """Listed and priced; stocks without a usable price can't be traded."""
    return bool(detail.get("is_active")) and detail.get("price_status") != "unavailable"


def get_tradeable_details(stocks):
    """get_details3() for lists people browse: drops stocks that can't be traded."""
    return [detail for detail in get_details3(stocks) if is_tradeable(detail)]


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
    return alerts


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
    signals_data = signal_collection.find_one(sort=[("_id", -1)]) or {}
    # New or renamed stocks have no signal until the next signals run
    company_data = signals_data.get(symbol)
    if company_data:
        # print("here")
        company_data.pop("_id", None)
        return company_data
    return {}

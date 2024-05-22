from django.core.management.base import BaseCommand
from portfolio.models import Stock
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URL = os.environ.get('MONGO_STRING')
client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
db = client['chartdata_1W']
# MongoDB connection
def removal(symbol):
    print(symbol)
    collection = db[symbol]

    # Find the document
    document = collection.find_one()

    if document:
        # Extract lists
        timestamps = document['t']
        open_prices = document['o']
        high_prices = document['h']
        low_prices = document['l']
        close_prices = document['c']
        volumes = document['v']

        # Filter out indices where both high and low are 0
        filtered_data = [(t, o, h, l, c, v) for t, o, h, l, c, v in zip(timestamps, open_prices, high_prices, low_prices, close_prices, volumes) if not (h == 0 and l == 0)]
        # print(filtered_data[0])
        # Unzip the filtered data back into separate lists
        if filtered_data:
            t_filtered, o_filtered, h_filtered, l_filtered, c_filtered, v_filtered = zip(*filtered_data)
       

            # Update the document with the filtered lists
            collection.update_one(
                {'_id': document['_id']},
                {
                    '$set': {
                        't': list(t_filtered),
                        'o': list(o_filtered),
                        'h': list(h_filtered),
                        'l': list(l_filtered),
                        'c': list(c_filtered),
                        'v': list(v_filtered)
                    }
                }
            )

            print(f"{symbol} Document updated successfully")
        
    else:
        print("No document found")

class Command(BaseCommand):
    help = 'get historical data'

    def handle(self, *args, **options):
        excluded_symbols = [
            'ABBEYBDS', 'ACADEMY', 'ACCESSCORP', 'AFRIPRUD', 'AFRINSURE', 'AFROMEDIA',
            'AIICO', 'AIRTELAFRI', 'ALEX', 'ARBICO', 'ASOSAVINGS', 'ABCTRANS',
            'AUSTINLAZ', 'MANSARD', 'BERGER', 'BETAGLAS'
        ]

        # Filter stocks to exclude the specified symbols
        # stocks = Stock.objects.filter(active=True).exclude(symbol__in=excluded_symbols)
        stocks = Stock.objects.filter(active=True)
        for stock in stocks:
            removal(stock.symbol)
        
import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from execution.models import DemoPosition, DemoProfitLoss, DemoDailyReturns
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from django.contrib.auth import get_user_model
from decimal import Decimal
import random

User= get_user_model()

def connect_to_mongodb():
    client = MongoClient(os.environ.get("MONGO_STRING"), maxPoolSize=20, tls=True,
                         tlsAllowInvalidCertificates=True)
    db = client["stock_prices"]
    collection = db["price_combined"]
    return collection

def get_data(collection, day):
    three_days_ago = datetime.utcnow() - timedelta(days=day) + timedelta(hours=6)
    print(three_days_ago)
    query = {"ZENITHBANK.datetime": {"$lt": three_days_ago}}
    result = collection.find_one(query, sort=[("datetime", -1)])
    return result


class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        
        asis = [
                {
                    "datetime": "2024-01-18 14:15:00",
                    "symbol": "NSENG:ASI",
                    "open": 91829.34,
                    "high": 91896.97,
                    "low": 91826.82,
                    "close": 91896.97,
                    "volume": 0.0
                },
                {
                    "datetime": "2024-01-19 14:15:00",
                    "symbol": "NSENG:ASI",
                    "open": 94348.14,
                    "high": 94538.12,
                    "low": 94335.81,
                    "close": 94538.12,
                    "volume": 0.0
                },
                {
                    "datetime": "2024-01-22 14:15:00",
                    "symbol": "NSENG:ASI",
                    "open": 95781.2,
                    "high": 95782.3,
                    "low": 95765.28,
                    "close": 95768.12,
                    "volume": 0.0
                },
                {
                    "datetime": "2024-01-23 14:15:00",
                    "symbol": "NSENG:ASI",
                    "open": 98615.11,
                    "high": 98628.07,
                    "low": 98559.76,
                    "close": 98616.97,
                    "volume": 0.0
                },
                {
                    "datetime": "2024-01-24 14:15:00",
                    "symbol": "NSENG:ASI",
                    "open": 100978.65,
                    "high": 101571.11,
                    "low": 100975.53,
                    "close": 101571.11,
                    "volume": 0.0
                },
                {
                    "datetime": "2024-01-25 14:15:00",
                    "symbol": "NSENG:ASI",
                    "open": 101786.35,
                    "high": 102149.93,
                    "low": 101780.64,
                    "close": 102149.93,
                    "volume": 0.0
                }
                ]
        with open('prices.json', 'r') as file:
            prices = json.load(file)
                    
        # print(prices[0]['ZENITHBANK'])
        # print(dates)
        users = User.objects.all()
        # data = get_price('NGXGROUP')
        # pr = data['current_price']
        # print(data)
        # # pr = 24.15
        
        for user in users:
            positions = DemoPosition.objects.filter(portfolio__user=user,status='open')
            
            
            if positions:
                
                for hope in asis:
                   
                    total_invested  = sum([post.amount_invested for post in positions])
                    position_shares = []
                    for position in positions:
                        # pl,value,price = position.calculate_profit_loss() 
                        price = round(prices[-1][position.stock.symbol]['current_price'] + random.uniform(-2,2),2)
                        value = position.quantity * price
                        returned =  (Decimal(value)/position.amount_invested) - 1
                        weight = (position.amount_invested/total_invested )
                        
                        position_shares.append(returned*weight)
                    shares = round(sum(position_shares)*100,2)
                    
                    last_ngx_query = DemoDailyReturns.objects.filter(user=user).last()
                    # print(last_ngx_query.ngx_price)
                    if last_ngx_query:
                        last_ngx = last_ngx_query.ngx_price
                        market_returns = round(((hope['close'] - last_ngx)/last_ngx) *100,2)
                    
                        print('return', shares)
                    else:
                        market_returns = 0
                    # last_ngx = 25.5
                    
                    # market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                        
                    DemoDailyReturns.objects.create(user=user, portfolio_returns=shares, market_returns =market_returns, ngx_price=hope['close'], created = datetime.strptime(hope['datetime'], "%Y-%m-%d %H:%M:%S"))
                    print(f"{user.email} daily profit/loss calculated")
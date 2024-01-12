# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from portfolio.models import Stock, DemoPortfolio, DemoPosition,Portfolio, Position
from decimal import Decimal
import random
from datetime import datetime, timedelta

User= get_user_model()


class DemoEquityConsumer(AsyncWebsocketConsumer):
    
    @database_sync_to_async
    def get_user_id_from_token(self, access_token):
        from rest_framework_simplejwt.tokens import UntypedToken
        
        try:
            untyped_token = UntypedToken(access_token)
            user_id = untyped_token.payload['user_id']
            return user_id
        except Exception as e:
            return None
    
    @database_sync_to_async
    def get_all_stocks(self):
        
        try:
            stocks = Stock.objects.all()
            return stocks
        
        except Exception as e:
            return None
    
    
    def market_returns(current_portfolio_value, days=7):
        volatility_factor = 0.02  # Adjust as needed

        # Generate random market returns
        market_returns = [random.uniform(-volatility_factor, volatility_factor) for _ in range(days)]

        # Calculate portfolio returns based on market returns
        portfolio_returns = [(1 + market_return) * current_portfolio_value for market_return in market_returns]

        # Generate dates for the past 5 days (including today)
        end_date = datetime.now().date()
        date_list = [end_date - timedelta(days=i) for i in range(days)][::-1]

        # Create a tuple of (date, portfolio return, market return) for each day
        result_data = list(zip(date_list, portfolio_returns, market_returns))

        return result_data



    @database_sync_to_async
    def get_user(self,id):
        user =User.objects.get(id=id)
        return user
    
    @database_sync_to_async
    def get_equity_data(self, user):
        portfolio = DemoPortfolio.objects.get(user=user)
        
        equity = portfolio.equity
        
        positions_query = DemoPosition.objects.filter(portfolio=portfolio)
        
        def calc_pnl(position):
            cost = position.average_price * position.quantity
            current = position.current_price * position.quantity
            return float(Decimal(current) - cost)
        
        def market_returns(current_portfolio_value, days=7):
            volatility_factor = 15  

            market_returns = [round(float(Decimal(random.uniform(-volatility_factor, volatility_factor)) + current_portfolio_value), 2) for _ in range(days)]
            portfolio_returns = [round(float(Decimal((1 + market_return)) + current_portfolio_value),2) for market_return in market_returns]

            end_date = datetime.now().date()
            date_list = [(end_date - timedelta(days=i)).isoformat() for i in range(days)][::-1]

            result_data = [
                {"date": date, "portfolio_returns": portfolio, "market_returns": market}
                for date, portfolio, market in zip(date_list, portfolio_returns, market_returns)
            ]

            return result_data

        
        positions = [{
            'date':position.created.isoformat(),
            'pnl':calc_pnl(position)
        } for position in positions_query]
        
        print(portfolio.calculate_portfolio_return())
        overview = market_returns(portfolio.calculate_portfolio_return())
        
        data =    {"equity":float(equity), "positions":positions, "overview":overview}
        
        return data
    
    async def initialize(self):
        access_token = self.scope.get('query_string').decode('utf-8').split('=')[1]
        self.user_id = await self.get_user_id_from_token(access_token)
        self.stocks = await self.get_all_stocks()
        self.user = await self.get_user(self.user_id)
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'demo-equity-{self.user_id}',
            self.channel_name
        )
        
        data = await self.get_equity_data(self.user)
        await self.send_message({'data': data})
        

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f'demo-equity-{self.user_id}',
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            await self.send_message({'data': data})
        except json.JSONDecodeError:
            pass

    async def send_message(self, event):
        data = event['data']

        await self.send(text_data=json.dumps({'data': data}))

class EquityConsumer(AsyncWebsocketConsumer):
    
    @database_sync_to_async
    def get_user_id_from_token(self, access_token):
        from rest_framework_simplejwt.tokens import UntypedToken
        
        try:
            untyped_token = UntypedToken(access_token)
            user_id = untyped_token.payload['user_id']
            return user_id
        except Exception as e:
            return None
    
    @database_sync_to_async
    def get_all_stocks(self):
        
        try:
            stocks = Stock.objects.all()
            return stocks
        
        except Exception as e:
            return None
    
    @database_sync_to_async
    def get_user(self,id):
        user =User.objects.get(id=id)
        return user
    
    @database_sync_to_async
    def get_equity_data(self, user):
        portfolio = Portfolio.objects.get(user=user)
        
        equity = portfolio.equity
        
        positions_query = Position.objects.filter(portfolio=portfolio)
        
        def calc_pnl(position):
            cost = position.average_price * position.quantity
            current = position.current_price * position.quantity
            return float(Decimal(current) - cost)
        
        positions = [{
            'date':position.created.isoformat(),
            'pnl':calc_pnl(position)
        } for position in positions_query]
        
        data =    {"equity":float(equity), "positions":positions, "overview":[]}
        
        return data
    
    async def initialize(self):
        access_token = self.scope.get('query_string').decode('utf-8').split('=')[1]
        self.user_id = await self.get_user_id_from_token(access_token)
        self.stocks = await self.get_all_stocks()
        self.user = await self.get_user(self.user_id)
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'live-equity-{self.user_id}',
            self.channel_name
        )
        
        data = await self.get_equity_data(self.user)
        await self.send_message({'data': data})
        

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f'live-equity-{self.user_id}',
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            await self.send_message({'data': data})
        except json.JSONDecodeError:
            pass

    async def send_message(self, event):
        data = event['data']

        await self.send(text_data=json.dumps({'data': data}))

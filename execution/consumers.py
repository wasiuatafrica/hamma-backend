# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .utils import get_notifications, update_notification
from channels.db import database_sync_to_async
from portfolio.models import Stock

class MarketsConsumer(AsyncWebsocketConsumer):
    
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
        
    async def initialize(self):
        access_token = self.scope.get('query_string').decode('utf-8').split('=')[1]
        self.user_id = await self.get_user_id_from_token(access_token)
        self.stocks = await self.get_all_stocks()
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'{self.stocks[0].symbol}',
            self.channel_name
        )
        
        
        # notifications =  
        # # print(notifications)
        # await self.send_first_data({'data': notifications})
        

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f'user_{self.user_id}',
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            notification_id = data.get('notification_id')
            notification = notification_id.split('-')
            if notification:
                update_notification(notification[1],notification[0])
                notifications1 =  get_notifications(notification[1])
                await self.send_notification({'message': notifications1})
        except json.JSONDecodeError:
            pass

    async def send_first_data(self, event):
        data = event['data']

        await self.send(text_data=json.dumps({'data': data}))

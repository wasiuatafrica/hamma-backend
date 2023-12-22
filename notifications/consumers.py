# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .utils import get_notifications, update_notification
from channels.db import database_sync_to_async

class NotificationConsumer(AsyncWebsocketConsumer):
    
    @database_sync_to_async
    def get_user_id_from_token(self, access_token):
        from rest_framework_simplejwt.tokens import UntypedToken
        
        try:
            untyped_token = UntypedToken(access_token)
            user_id = untyped_token.payload['user_id']
            return user_id
        except Exception as e:
            return None
        
    async def initialize(self):
        access_token = self.scope.get('query_string').decode('utf-8').split('=')[1]
        self.user_id = await self.get_user_id_from_token(access_token)
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'user_{self.user_id}',
            self.channel_name
        )
        
        
        notifications =  get_notifications(self.user_id)
        # print(notifications)
        await self.send_notification({'message': notifications})
        

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

    async def send_notification(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({'message': message}))

# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .utils import get_notifications, update_notification

class NotificationConsumer(AsyncWebsocketConsumer):
    async def initialize(self):
        self.user_id = self.scope['user'].id
        # self.user_id = self.scope['query_string'].decode('utf-8').split('=')[1]
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'user_{self.user_id}',
            self.channel_name
        )
        
        
        notifications =  get_notifications(self.user_id)
        for notification in notifications:
            await self.send_notification({'message': notification})


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f'user_{self.user_id}',
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            notification_id = data.get('notification_id')
            
            if notification_id:
                await update_notification(self.user_id,notification_id)
        except json.JSONDecodeError:
            pass

    async def send_notification(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({'message': message}))

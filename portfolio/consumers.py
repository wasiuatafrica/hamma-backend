# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .tasks import process_alert_data, process_alert_data2
from .utils import get_alert_prompt_history, get_conversation
import time
from .models import Message

User= get_user_model()

class AlertConsumer(AsyncWebsocketConsumer):
    
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
    def get_user_id_from_email(self, email):
        
        
        try:
            user=User.objects.get(email=email)
            return user.id
        except Exception as e:
            return None
    
    @database_sync_to_async
    def get_user(self,id):
        user =User.objects.get(id=id)
        return user
    
    @database_sync_to_async
    def get_messages(self, conversation):
        query= Message.objects.filter(room = conversation)
        messages = [
            {
                'message':message.content,
                'sender':message.sender,
                'created':message.created.isoformat()
                    } for message in query
        ]

            
        # print(messages)
        return messages
    
    
      
    async def initialize(self):
        query_string = self.scope.get('query_string').decode('utf-8')

        # Split the query string into key-value pairs
        query_params = dict(param.split('=') for param in query_string.split('&'))

        # Extract the values for 'token' and 'status' parameters
        access_token = query_params.get('token', None)
        email = query_params.get('email', None)
        print(email)
        conversation_id  = query_params.get('conversation_id', None)

        print(access_token, conversation_id)
        # access_token = self.scope.get('query_string').decode('utf-8').split('=')[1]
        if access_token:
            self.user_id = await self.get_user_id_from_token(access_token)
        elif email:
            self.user_id = await self.get_user_id_from_email(email)
            
        # self.user_id = await self.get_user_id_from_token(access_token)
        # print('user',self.user_id)
        self.user = await self.get_user(self.user_id)
        self.conversation_id = conversation_id
        self.conversation = await get_conversation(conversation_id,self.user)
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'alert_{self.conversation_id}',
            self.channel_name
        )
        
        history = await self.get_messages(self.conversation)
        # print(history)
            
        # # history = await get_alert_prompt_history(self.user_id)
        if history:
            await self.send_message({'message': history})
        

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f'alert_{self.conversation_id}',
            self.channel_name
        )

    async def receive(self, text_data):
        message = json.loads(text_data)['message']
        # print(message)
        def create_message(sender,content):
            return Message.objects.create(user=self.user, room=self.conversation, sender=sender,content=content)
        
        await database_sync_to_async(create_message)('user',message)
        keywords = ['stock', 'price', 'above', 'below', 'greater', 'lesser', 'volume', 'symbol', 'expire']
        common_phrases = {
            "greetings": ["how are you doing","how are you","hello", "hi", "hey", "howdy", "greetings", "good morning", "good afternoon", "good evening"],
            "farewells": ["bye", "goodbye", "see you", "take care", "farewell", "have a nice day", "good night"],
            "thanks": ["thanks", "thank you", "appreciate it", "thank you so much", "thanks a lot"],
            "confirmations": ["yes", "yeah", "yep", "sure", "absolutely", "indeed"],
            "negations": ["no", "nope", "nah", "not really", "sorry, no"],
            }

        responses = {
            "greetings": "Hello! How can I assist you?",
            "farewells": "Goodbye! Have a nice day!",
            "thanks": "You're welcome!",
            "confirmations": "Great, let's proceed!",
            "negations": "I understand. Is there anything else I can assist you with?",
        }
        response=''
        
        for category, phrases in common_phrases.items():
            if len(message.split(' ')) < 4 and any(phrase in message.lower() for phrase in phrases):
                
                response = responses[category]
                break
            elif len(message.split(' ')) < 4 and not any(phrase in message.lower() for phrase in phrases):
                
                response = "I am  HammaAlert, alert creation AI, please state the symbol, price or volume actions, conditions to be met to create your alert."
                break
        
        if not response:
            if not any(keyword in message.lower() for keyword in keywords):
                response = "I am HammaAlert, alert creation AI, Please state the symbol, price or volume actions,conditions to be met  to create your alert."
            else:
                response = 'Alert is being created. . . .'
                process_alert_data.delay(message,self.conversation_id, self.user_id, self.channel_name)
                
        time.sleep(1)
        
        
        await self.send_message({'message': response})
        await database_sync_to_async(create_message)('bot',response)
        

    async def send_message(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({'message': message}))

class AlertConsumer2(AsyncWebsocketConsumer):
    
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
    def get_user_id_from_email(self, email):
        
        
        try:
            user=User.objects.get(email=email)
            return user.id
        except Exception as e:
            return None
    
    @database_sync_to_async
    def get_user(self,id):
        user =User.objects.get(id=id)
        return user
    
    @database_sync_to_async
    def get_messages(self, conversation):
        query= Message.objects.filter(room = conversation)
        messages = [
            {
                'message':message.content,
                'sender':message.sender,
                'created':message.created.isoformat()
                    } for message in query
        ]

            
        # print(messages)
        return messages
    
    
      
    async def initialize(self):
        query_string = self.scope.get('query_string').decode('utf-8')

        # Split the query string into key-value pairs
        query_params = dict(param.split('=') for param in query_string.split('&'))

        # Extract the values for 'token' and 'status' parameters
        access_token = query_params.get('token', None)
        email = query_params.get('email', None)
        print(email)
        conversation_id  = query_params.get('conversation_id', None)

        print(access_token, conversation_id)
        # access_token = self.scope.get('query_string').decode('utf-8').split('=')[1]
        if access_token:
            self.user_id = await self.get_user_id_from_token(access_token)
        elif email:
            self.user_id = await self.get_user_id_from_email(email)
            
        # self.user_id = await self.get_user_id_from_token(access_token)
        # print('user',self.user_id)
        self.user = await self.get_user(self.user_id)
        self.conversation_id = conversation_id
        self.conversation = await get_conversation(conversation_id,self.user)
        
    async def connect(self):
        await self.accept()
        await self.initialize()
        
        await self.channel_layer.group_add(
            f'alert_{self.conversation_id}',
            self.channel_name
        )
        
        history = await self.get_messages(self.conversation)
        # print(history)
            
        # # history = await get_alert_prompt_history(self.user_id)
        if history:
            await self.send_message({'message': history})
        

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f'alert_{self.conversation_id}',
            self.channel_name
        )

    async def receive(self, text_data):
        message = json.loads(text_data)['message']
        # print(message)
        def create_message(sender,content):
            return Message.objects.create(user=self.user, room=self.conversation, sender=sender,content=content)
        
        await database_sync_to_async(create_message)('user',message)
        process_alert_data2.delay(message,self.conversation_id, self.user_id, self.channel_name)
                
        
    async def send_message(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({'message': message}))

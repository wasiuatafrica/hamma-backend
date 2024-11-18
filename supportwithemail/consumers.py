import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import logging
from urllib.parse import parse_qs
from . import utils
from . import models
from accounts.models import CustomUser
from openai import OpenAI
from rest_framework_simplejwt.tokens import UntypedToken
from openai import OpenAI

logger = logging.getLogger(__name__)


class NoAuthSupportConsumer(AsyncWebsocketConsumer):

    @database_sync_to_async
    def check_if_user_exists(self, email):
        return CustomUser.objects.filter(email=email).exists()

    @database_sync_to_async
    def get_conversation(self, email, is_prop=False):
        conversation = models.SupportThread.objects.create(email=email, is_prop=is_prop)

        client = OpenAI()
        thread = client.beta.threads.create()
        conversation.thread_id = thread.id
        conversation.save()
        return conversation

    async def initialize(self):
        query_string = self.scope.get("query_string").decode("utf-8")
        parsed_query = parse_qs(query_string)
        self.email = parsed_query.get("email", [None])[0]
        self.name = parsed_query.get("name", [None])[0]
        self.bot_type = parsed_query.get("is_prop", [None])[0]

        # Safely handle None case
        self.is_prop = self.bot_type.lower() == "true" if self.bot_type else False

        self.conversation = await self.get_conversation(
            self.email, is_prop=self.is_prop
        )
        self.conversation_id = self.conversation.id

    async def connect(self):
        print("Heloooo reached here")
        await self.accept()
        await self.initialize()

        if not self.email:
            await self.close()
            return

        else:

            await self.channel_layer.group_add(
                f"email_{self.conversation.thread_id}_bot", self.channel_name
            )
            await self.channel_layer.group_add(f"admin_room", self.channel_name)
            self.channel_room_name = f"email_{self.conversation.thread_id}_bot"
        print(self.channel_room_name, "this is the room name")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f"email_{self.conversation.thread_id}_bot", self.channel_name
        )

    async def receive(self, text_data):
        try:

            data = json.loads(text_data)
            message = data.get("message")

            def create_message(sender, content):
                print(self.conversation, "this is the thread...")
                return models.SupportMessage.objects.create(
                    email=self.email,
                    thread=self.conversation,
                    sender=sender,
                    content=content,
                    name=self.name,
                )

            message_id = await database_sync_to_async(create_message)("user", message)
            assistant_id = (
                "asst_cNYBMhon9Y4opWwtdK2xR345"
                if self.is_prop
                else "asst_MJ9ZqMIyzQqgjvm5sUwGZI7E"
            )
            await database_sync_to_async(utils.send_assistant_message)(
                message,
                self.channel_room_name,
                self.conversation,
                message_id.id,
                assistant_id=assistant_id,
            )

        except json.JSONDecodeError:
            pass

    async def send_message_to_user(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))

from concurrent.futures import thread
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import logging
from urllib.parse import parse_qs
from . import utils
from . import models
from accounts.models import CustomUser
from backend.lazy import OpenAI
from rest_framework_simplejwt.tokens import UntypedToken
from backend.lazy import OpenAI
import random
from .models import SupportAdminProfile


logger = logging.getLogger(__name__)


class AdminSupportConsumer(AsyncWebsocketConsumer):

    @database_sync_to_async
    def get_user_id_from_token(self, access_token):
        try:
            untyped_token = UntypedToken(access_token)
            user_id = untyped_token.payload["user_id"]
            return user_id
        except Exception as e:
            logger.error(f"Error getting user ID from token: {e}")
            return None

    @database_sync_to_async
    def is_admin_user(self, user_id):

        try:
            user = CustomUser.objects.get(id=user_id)
            return (
                True if (user.is_superuser | user.is_staff | user.is_analyst) else False
            )
        except Exception as e:
            logger.error(f"Error getting user 1: {e}")
            return None

    @database_sync_to_async
    def return_email(self, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
            return user.email
        except Exception as e:
            logger.error(f"Error getting user 2: {e}")
            return None

    @database_sync_to_async
    def previous_messages(self, thread_id):
        thread = models.SupportThread.objects.filter(thread_id=thread_id).first()
        prev_messages = models.SupportMessage.objects.filter(thread=thread)
        data = []
        if prev_messages:
            for message in prev_messages:
                user_message_data = {
                    "id": message.id,
                    "sender": message.sender,
                    "content": message.content,
                    "fullname": message.name,
                    "created": str(message.created),
                    "updated": str(message.updated),
                    "thread": message.thread.id,
                    "user_name": message.user_name,
                    "user_pics": (
                        str(message.admin_profile_url)
                        if message.sender == "admin"
                        else message.user_pics
                    ),
                    "thread_value": message.thread_value,
                    "email": message.email,
                    "chat_switched_to_admin": message.thread.switched_to_admin_support,
                }
                data.append(user_message_data)
        return data

    @database_sync_to_async
    def previous_switch_to_Admin_request_messages(self, is_prop=False):
        prev_messages = models.SupportMessage.objects.filter(
            is_first_admin_request_message=True, thread__is_prop=is_prop
        ).order_by("-created")
        data = []
        if prev_messages:
            for message in prev_messages:
                user_message_data = {
                    "id": message.id,
                    "sender": message.sender,
                    "content": message.content,
                    "fullname": message.name,
                    "created": str(message.created),
                    "updated": str(message.updated),
                    "thread": message.thread.id,
                    "user_name": message.user_name,
                    "user_pics": str(message.user_pics),
                    "thread_value": message.thread_value,
                    "email": message.email,
                    "chat_switched_to_admin": message.thread.switched_to_admin_support,
                }
                data.append(user_message_data)
        return data

    @database_sync_to_async
    def get_admin_random_profile(self):
        """
        Randomly selects a name from a predefined list and returns the corresponding
        SupportAdminProfile instance filtered by that name.

        Returns:
        SupportAdminProfile instance or None if no matching instance is found.
        """
        # List of names to choose from
        names = [admin.name for admin in SupportAdminProfile.objects.all()]

        # Randomly select a name from the list
        selected_name = random.choice(names)


        try:
            # Filter and return the first instance with the selected name
            profile = SupportAdminProfile.objects.filter(
                name__icontains=selected_name
            ).first()

            if profile:
                pass
            else:
                pass

            return profile

        except SupportAdminProfile.DoesNotExist:
            return None

    @database_sync_to_async
    def get_conversation(self, thread_id):

        conversation = models.SupportThread.objects.filter(thread_id=thread_id).first()

        return conversation

    async def initialize(self):
        query_string = self.scope.get("query_string").decode("utf-8")
        parsed_query = parse_qs(query_string)

        # check which bot type is being accessed
        self.bot_type = parsed_query.get("is_prop", [None])[0]
        # Safely handle None case
        self.is_prop = self.bot_type.lower() == "true" if self.bot_type else False

        self.thread_id = parsed_query.get("thread_id", [None])[0]
        self.access_token = parsed_query.get("access_token", [None])[0]
        self.admin_user = await self.get_user_id_from_token(self.access_token)
        self.email = await self.return_email(self.admin_user)
        self.admin_profile = await self.get_admin_random_profile()

        self.prev_messages = (
            await self.previous_messages(self.thread_id) if self.thread_id else []
        )
        self.request_messages = await self.previous_switch_to_Admin_request_messages(
            self.is_prop
        )

        self.conversation = await self.get_conversation(self.thread_id)
        self.channel_room_name = "admin_support_group_"


    async def connect(self):
        await self.accept()
        await self.initialize()

        # check if user is an admin
        is_admin = await self.is_admin_user(self.admin_user)
        if not is_admin or is_admin == None:
            await self.close()
            return

        # admin wants to connect to a specific thread to reply a user
        if self.thread_id:
            await self.channel_layer.group_add(
                f"admin_support_group_{str(self.is_prop)}{self.thread_id}",
                self.channel_name,
            )
            self.channel_room_name = (
                f"admin_support_group_{str(self.is_prop)}{self.thread_id}"
            )
            await self.send_message_to_user({"message": self.prev_messages})

        # admin want to only recieve admin request messages
        else:
            await self.channel_layer.group_add(
                f"switch_to_admin_request_{str(self.is_prop)}", self.channel_name
            )
            self.channel_room_name = f"switch_to_admin_request_{str(self.is_prop)}"
            await self.send_message_to_user({"message": self.request_messages})


    async def disconnect(self, close_code):

        await self.channel_layer.group_discard(
            self.channel_room_name, self.channel_name
        )

    async def receive(self, text_data):
        try:

            data = json.loads(text_data)
            message = data.get("message")

            def create_message(sender, content):
                return models.SupportMessage.objects.create(
                    thread=self.conversation,
                    sender=sender,
                    content=content,
                    admin_profile=self.admin_profile,
                    name=self.admin_profile.name if self.admin_profile else "",
                )

            message = await database_sync_to_async(create_message)("admin", message)
            # await database_sync_to_async(utils.send_assistant_message)(
            #     message, self.thread_id, self.conversation
            # )

            await database_sync_to_async(utils.reply_users_message)(
                self.thread_id, message, self.admin_profile
            )

        except json.JSONDecodeError:
            pass

    async def send_message_to_user(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({"message": message}))

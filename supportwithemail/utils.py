from typing import Optional, Any
from . import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .task import start_conversation
from django.core.serializers.json import DjangoJSONEncoder
import json


channel_layer = get_channel_layer()


def send_assistant_message(message, channel_room_name, conversation, message_id=None):

    response = None
    conversation = models.SupportThread.objects.get(thread_id=conversation.thread_id)
    print(
        channel_room_name,
        conversation,
        "HEYYYY111",
        conversation.switched_to_admin_support,
    )
    if conversation.switched_to_admin_support:
        print("to admin user.....")

        message = models.SupportMessage.objects.get(id=message_id)
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
            "chat_switched_to_admin": message.thread.switched_to_admin_support,
        }

        async_to_sync(channel_layer.group_send)(
            f"admin_support_group_{conversation.thread_id}",
            {
                "type": "send_message_to_user",
                "message": user_message_data,
            },
        )
        # send to message to update side bar as well.
        async_to_sync(channel_layer.group_send)(
            "switch_to_admin_request",
            {
                "type": "send_message_to_user",
                "message": user_message_data,
            },
        )
        return

    else:

        # if message == "I'm looking to do something else":
        #     message = f"{message}. Note: do not connect user to admin yet, rather ask the user about what they would like to do. You can suggest what they can do as well."

        response = start_conversation(
            thread_id=conversation.thread_id,
            user=conversation.email,
            new_message=message,
        )

    if response["success"]:

        assistant_message = models.SupportMessage.objects.create(
            sender="assistant", thread=conversation, content=response["message"]
        )
        conversation = models.SupportThread.objects.get(
            thread_id=conversation.thread_id
        )

        assistant_message_data = {
            "id": assistant_message.id,
            "sender": assistant_message.sender,
            "content": assistant_message.content,
            "fullname": assistant_message.name,
            "created": str(assistant_message.created),
            "updated": str(assistant_message.updated),
            "thread": assistant_message.thread.id,
            "user_name": assistant_message.user_name,
            "user_pics": str(assistant_message.user_pics),
            "thread_value": assistant_message.thread_value,
            "chat_switched_to_admin": conversation.switched_to_admin_support,
        }

        async_to_sync(channel_layer.group_send)(
            channel_room_name,
            {
                "type": "send_message_to_user",
                "message": assistant_message_data,
            },
        )
        return


def reply_users_message(thread_id, message, admin_profile=None):

    admin_message_data = {
        "id": message.id,
        "sender": message.sender,
        "content": message.content,
        "fullname": message.name,
        "created": str(message.created),
        "updated": str(message.updated),
        "thread": message.thread.id,
        "user_name": message.user_name,
        "user_pics": str(message.admin_profile_url),
        "thread_value": message.thread_value,
        "chat_switched_to_admin": message.thread.switched_to_admin_support,
    }

    room_name = f"email_{thread_id}_bot"
    print(f"Sending message to room: {room_name}")

    async_to_sync(channel_layer.group_send)(
        room_name,
        {
            "type": "send_message_to_user",
            "message": admin_message_data,
        },
    )

    return


# def reply_users_message(thread_id, message):

#     # thread = models.SupportThread.objects.filter(thread_id=thread_id).first()
#     # admin_message = models.SupportMessage.objects.create(
#     #     sender="admin",
#     #     thread=thread,
#     #     content=message
#     # )
#     admin_message = message

#     admin_message_data = {
#             "id": admin_message.id,
#             "sender": admin_message.sender,
#             "content": admin_message.content,
#             "created": str(admin_message.created),
#             "updated": str(admin_message.updated),
#             "thread": admin_message.thread.id,
#             "user_name": admin_message.user_name,
#             "user_pics": str(admin_message.user_pics),
#             "thread_value": admin_message.thread_value,

#         }
#     print("Hellll", thread_id)
#     room_name = f'email_{thread_id}_bot'
#     print(room_name, "this is the room name...")
#     async_to_sync(channel_layer.group_send)(
#             room_name,
#             {
#                 'type': 'send_message_to_user',
#                 'message': admin_message_data,
#             }
#         )

#     return

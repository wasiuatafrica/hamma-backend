from . import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from openai import OpenAI
from django.conf import settings
from typing import Optional, Any
from django.contrib.auth import get_user_model

import time as timer
import json
import concurrent.futures
from datetime import datetime, time
from zoneinfo import ZoneInfo

from notifications.utils import save_and_send_notification
from django.core.serializers.json import DjangoJSONEncoder
import json


User = get_user_model()
channel_layer = get_channel_layer()

client = OpenAI()


def start_conversation(
    thread_id: Optional[str] = None,
    user: Any = None,
    new_message: str = "Hello",
    assistant_id="asst_MJ9ZqMIyzQqgjvm5sUwGZI7E",
    # assistant_id="asst_3UNWJs0OcbkltT3dYr4vdrNe",
) -> Optional[dict]:

    if thread_id is None:
        thread_id = client.beta.threads.create().id

    client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=new_message
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,  # Use the dynamically created assistant ID
    )

    completed = False
    start_time = timer.time()

    while not completed:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        print(run.status)
        print(run.required_action)
        if run.status == "completed":
            completed = True
            break
        elif run.status == "requires_action":

            def process_tool_call(tool_call):
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                if name == "get_current_price":
                    symbol = arguments["symbol"]
                    price = get_price(symbol)
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"price": price}),
                    }
                if name == "switch_to_human_assistant":
                    message = switch_to_human_assistant(thread_id, new_message)
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"message": message}),
                    }

                if name == "get_price_by_date":
                    symbol = arguments["symbol"]
                    date = arguments["date"]
                    price = get_price_by_date(date, symbol)
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"price": price}),
                    }

            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(process_tool_call, tool_call)
                    for tool_call in tool_calls
                ]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        print(result, "result")
                        tool_outputs.append(result)
                    except Exception as e:
                        print(f"Exception: {e}")

            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )
        elif run.status in ["cancelling", "cancelled", "failed", "expired"]:
            return {
                "main_response": "Error occurred, please start a new conversation",
                "extracted_data": [],
            }
        else:
            timer.sleep(0.5)

        elapsed_time = timer.time() - start_time

        if elapsed_time >= 30:
            break

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread_id)

        assistant_message = next(
            (msg for msg in messages.data if msg.role == "assistant"), None
        )

        if assistant_message:
            for content_block in assistant_message.content:
                if content_block.type == "text":
                    return {
                        "status": 200,
                        "run_status": run.status,
                        "success": True,
                        "message": content_block.text.value,
                        "thread_id": thread_id,
                    }
        else:
            return {
                "status": 500,
                "success": False,
                "run_status": run.status,
                "message": "",
            }

    return {"status": 500, "success": False, "run_status": run.status, "message": ""}


def is_within_working_hours():
    # Set the timezone to Nigeria (West Africa Time)
    current_time = datetime.now(ZoneInfo("Africa/Lagos"))
    current_day = current_time.weekday()
    current_time = current_time.time()

    # Check if it's Monday to Friday (0-4) and between 9 AM and 5 PM
    return 0 <= current_day <= 4 and time(9, 0) <= current_time <= time(17, 0)


def switch_to_human_assistant(thread_id, message=None):

    if not is_within_working_hours():
        return "I apologize, but human support is only available from 9 AM to 5 PM, Monday to Friday, Nigerian time. Is there anything else I can help you with?"

    #   update thread
    thread = models.SupportThread.objects.get(thread_id=thread_id)
    thread.switched_to_admin_support = True
    thread.save()

    print("switch to admin func called..")

    # check if the converstion is from email_ai_support

    if thread.user:

        # # create activity log
        # UserActivityLog.objects.create(
        #     user=thread.user,
        #     action_type="admin_support",
        #     description="User requested for an admin support.",
        # )
        pass

    # send notification to support admins
    admin_users = User.objects.filter(is_staff=True)
    for user in admin_users:
        # send notification
        save_and_send_notification(
            user.id,
            f"{thread.user.firstname if thread.user else thread.email} just requested admin support.",
        )

    # send the message to the admin message request room
    message = models.SupportMessage.objects.get(
        thread=thread, sender="user", content=message
    )
    message.is_first_admin_request_message = True
    message.save()
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
        f"switch_to_admin_request_{str(thread.is_prop)}",
        {
            "type": "send_message_to_user",
            "message": json.dumps(user_message_data, cls=DjangoJSONEncoder),
        },
    )
    return "Your request for human support has been received. An admin will be with you shortly."

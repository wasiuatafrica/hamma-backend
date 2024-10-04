import json
from datetime import datetime, timedelta

import pytz
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management import call_command
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from notifications.utils import save_and_send_notification
from portfolio.utils import get_price

from .models import (Alert, AlertAI, AlertAITracker, Conversation, Message,
                     Stock)
from .utils import get_alert_data, get_alerts

User= get_user_model()

logger = get_task_logger(__name__)
channel_layer = get_channel_layer()


@shared_task
def create_alert_schedule(id):
    alert=Alert.objects.get(id=id)
    print('Alert object gotten')
    schedule = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )[0]
    
    
    PeriodicTask.objects.create(
            interval=schedule,
            name=alert.task_name,
            task='portfolio.tasks.check_alert',
            args=json.dumps([alert.id])
        )
    save_and_send_notification(alert.user.id, f"You created alert for {alert.stock.symbol}")
    print(f"Alert created for {alert.user} on {alert.stock}")
    
def send_alert_email(user,symbol,alert_type,action,to_price):
    # Send token to users email
    context={
        "firstname":user.firstname,
        "symbol":symbol,
        "alert_type":alert_type.title(),
        'action':action,
        'to_price':to_price
    }
    html_message = render_to_string('portfolio/price_alert.html', context)
    plain_message = ""
    subject = 'Trade Alert'
    from_email = "hello@gohamma.com"
    recipient_list = [user.email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
    
    
@shared_task

def check_alert(id):
    
    try:
        alert=Alert.objects.get(id=id)
        print(f"{alert.alert_name} object gotten")
    except Alert.DoesNotExist:
        alert=None
    # print(alert.created.month )
    
    if alert:
        lagos_tz = pytz.timezone('Africa/Lagos')
        
        current_month = timezone.now().astimezone(lagos_tz).month
        if alert.created.astimezone(lagos_tz).month != current_month:
            print(f"Alert {alert.alert_name} was not created in the current month. Disabling the periodic task.")
            task = PeriodicTask.objects.get(name=alert.alert_name)
            task.enabled = False
            task.save()
            return
        
        current_time = timezone.now().astimezone(lagos_tz)
        print(current_time )
        if current_time.weekday() < 5 and current_time.time() >= datetime.strptime('9:30 AM', '%I:%M %p').time() and current_time.time() <= datetime.strptime('2:30 PM', '%I:%M %p').time():
            if timezone.now().astimezone(lagos_tz) < alert.expire:
                if not alert.trigerred:
                    data = get_price(alert.stock.symbol)
                    if alert.alert_type == 'price':
                        price = data['current_price']
                        if alert.action == 'below':
                            if alert.to_price is not None:
                                if price < alert.to_price:
                                    if (alert.last_email_sent and (timezone.now().astimezone(lagos_tz) - alert.last_email_sent) >= timedelta(minutes=30)) or not alert.last_email_sent:
                                        send_alert_email(alert.user, alert.stock.symbol, alert.alert_type, alert.action, alert.to_price)
                                        print('sent')
                                        save_and_send_notification(alert.user.id, f'{alert.stock} price has gone below {alert.to_price} for the {alert.alert_name}.')
                                        if alert.frequency in ['Once', 'once']:
                                            alert.trigerred = True
                                            alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                            alert.save()
                                        else:
                                            alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                            alert.save()
                                            return
                        elif alert.action == 'above':
                            if alert.to_price is not None:
                            
                                if price > alert.to_price:
                                    if (alert.last_email_sent and (timezone.now().astimezone(lagos_tz) - alert.last_email_sent) >= timedelta(minutes=30)) or not alert.last_email_sent:
                                        send_alert_email(alert.user, alert.stock.symbol, alert.alert_type, alert.action, alert.to_price)
                                        save_and_send_notification(alert.user.id, f'{alert.stock} price has gone above {alert.to_price} for the {alert.alert_name}.')
                                        if alert.frequency in ['Once', 'once']:
                                            alert.trigerred = True
                                            alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                            alert.save()
                                        else:
                                            alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                            alert.save()
                                            return

                    elif alert.alert_type == 'volume':
                        price=data['volume']
                        if alert.action == 'below':
                            if price < alert.to_volume:
                                if (alert.last_email_sent and (timezone.now().astimezone(lagos_tz) - alert.last_email_sent) >= timedelta(minutes=30)) or not alert.last_email_sent:
                                    send_alert_email(alert.user, alert.stock.symbol,alert.alert_type,alert.action, alert.to_volume)
                                    save_and_send_notification(alert.user.id, f'stock {alert.stock} volume has gone below {alert.to_volume} for the {alert.alert_name}.')
                                    if alert.frequency in ['Once', 'once']:
                                        alert.trigerred = True
                                        alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                        alert.save()
                                    else:
                                        alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                        alert.save()
                                        return

                        elif alert.action == 'above':
                            if price > alert.to_volume:
                                if (alert.last_email_sent and (timezone.now().astimezone(lagos_tz) - alert.last_email_sent) >= timedelta(minutes=30)) or not alert.last_email_sent:
                                    send_alert_email(alert.user, alert.stock.symbol,alert.alert_type,alert.action, alert.to_volume)
                                    save_and_send_notification(alert.user.id, f'stock {alert.stock} volume has gone above {alert.to_volume} for the {alert.alert_name}.')
                                    if alert.frequency in ['Once', 'once']:
                                        alert.trigerred = True
                                        alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                        alert.save()
                                    else:
                                        alert.last_email_sent = timezone.now().astimezone(lagos_tz)
                                        alert.save()
                                        return

                else:
                    task = PeriodicTask.objects.get(name=alert.task_name )
                    task.enabled = False
                    task.save()
            else:
                task = PeriodicTask.objects.get(name=alert.task_name)
                task.enabled = False
                task.save()
            print(f'Checking for alert {alert.task_name} completed')
  
@shared_task
def get_data_prompt(prompt):
    data = get_alert_data(prompt)
    print(data)
    return data

@shared_task
def process_alert_data(prompt, convsersation_id, user_id, channel_name):
    print(prompt)
    loaded_data = get_data_prompt(prompt)
    user= User.objects.get(id=user_id)
    conversation = Conversation.objects.get(name=convsersation_id)
    extracted_data = json.loads(loaded_data)
    
    counter = AlertAITracker.objects.get_or_create(user=user)[0]

    if counter.count >= 10:
        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"You have reached the maximum limit of 10 alerts for this month."})
        Message.objects.create(user =user, sender='bot',room=conversation, content=f"You have reached the maximum limit of 10 alerts for this month.")
    else:
        
        alertai = AlertAI.objects.create(user=user,prompt=prompt,extracted_parameters=loaded_data)
        
        if isinstance(extracted_data, dict):
            if 'stock' in extracted_data and 'alert_type' in extracted_data and 'action' in extracted_data:
                stock = get_object_or_404(Stock, symbol=extracted_data['stock'].upper())
                alert_type = extracted_data['alert_type']
                action= extracted_data['action']
                frequency = extracted_data['frequency'] if 'frequency' in extracted_data else 'Once'
                description = prompt
                # expire = datetime.fromisoformat(extracted_data['expire']) if'expire' in extracted_data else timezone.now() + timedelta(weeks=2)
                if 'to_price' in extracted_data:
                    to_price = float(extracted_data['to_price'])
                    alert_name = f"Alert for {stock.symbol} {action} {to_price}"
                    
                    alert = Alert.objects.create(user=user, stock=stock, alert_type=alert_type, alert_name=alert_name, to_price=to_price, frequency=frequency,description=description)
                    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Alert created for {stock.symbol} when {alert_type} is {action} {to_price}. Frequency: {alert.frequency}"})
                    
                    Message.objects.create(user =user, sender='bot',room=conversation, content=f"Alert created for {stock.symbol} when {alert_type} is {action} {to_price}. Frequency: {alert.frequency}")
                    
                    
                    alertai.alert_created= True
                    alertai.save()
                    print('price alert created')
                    
                    counter.count += 1
                    counter.save()
                    
                elif 'to_volume' in extracted_data:
                    to_volume = float(extracted_data['to_volume'])
                    alert_name = f"Alert for {stock.symbol} {action} {to_volume}"
                    
                    alert = Alert.objects.create(user=user, stock=stock, alert_type=alert_type, alert_name=alert_name, to_volume=to_volume, frequency=frequency,description=description)
                
                    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message','message': f"Alert created for {stock.symbol} when {alert_type} is {action} {to_volume}. Frequency: {alert.frequency}" })
                    Message.objects.create(user =user, sender='bot',room=conversation, content=f"Alert created for {stock.symbol} when {alert_type} is {action} {to_volume}. Frequency: {alert.frequency}")
                    
                    
                    alertai.alert_created= True
                    alertai.save()
                    print('volume alert created')
                    
                    counter.count += 1
                    counter.save()
                    
            else:
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message','message': "Your prompt does not contain stock symbol or you didn't specify if you are creating price or volume alert, or you didn't state if its above or below target price or volume" })
                Message.objects.create(user =user, sender='bot',room=conversation, content="Your prompt does not contain stock symbol or you didn't specify if you are creating price or volume alert, or you didn't state if its above or below target price or volume")
                
        else:
            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message','message': "Your prompt does not contain stock symbol or you didn't specify if you are creating price or volume alert, or you didn't state if its above or below target price or volume" })
            Message.objects.create(user =user, sender='bot',room=conversation, content="Your prompt does not contain stock symbol or you didn't specify if you are creating price or volume alert, or you didn't state if its above or below target price or volume")
  
import concurrent.futures
import time

from openai import OpenAI

client = OpenAI()

def conversation_response(thread_id, prompt,user):
    assistant_id = "asst_4VILqMpHdsPOzs5HMQm9EwrN"
    
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    
    completed = False
    start_time = time.time()
    
    while not completed:
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        print(run.status)
        print(run.required_action)
        if run.status == 'completed':
            completed = True
            break
        elif run.status == 'requires_action':
            def process_tool_call(tool_call):
                name = tool_call.function.name
                
                if name == 'get_current_stock_price':
                    arguments = json.loads(tool_call.function.arguments)
                    symbol = arguments['symbol']
                    price = get_price(symbol)
                    
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps([str(price)]),
                    }
                elif name == 'get_alerts':
                    alerts = get_alerts(user)
                    
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps([alerts]),
                    }
            
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs= []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(process_tool_call, tool_call) for tool_call in tool_calls]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        tool_outputs.append(result)
                    except Exception as e:
                        print(f"Exception: {e}")
            # print('alerts:',tool_outputs)
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
                )
        elif run.status in  ["cancelling", "cancelled", "failed", "expired"]:
            return '{"main_response": "Error occured, please start new conversation", "extracted_data": []}'   
        else:
            time.sleep(0.5)
            
        elapsed_time = time.time() - start_time
        
        if elapsed_time >= 30:
            break
    # print(completed)  
    if completed:
        messages = client.beta.threads.messages.list(thread_id=thread_id,order="asc", after=message.id)
        
        return messages.data[0].content[0].text.value
    else:
        return '{"main_response": "Error occured, please start new conversation", "extracted_data": []}'

        
@shared_task
def process_alert_data2(prompt, convsersation_id, user_id, channel_name):
    print(prompt)
    
    conversation = Conversation.objects.get(name=convsersation_id)
    # loaded_data = conversation_response(conversation.thread_id, prompt)
    user= User.objects.get(id=user_id)
    
    
    counter = AlertAITracker.objects.get_or_create(user=user)[0]

    if counter.count >= 10:
        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"You have reached the maximum limit of 10 alerts for this month."})
        Message.objects.create(user =user, sender='bot',room=conversation, content=f"You have reached the maximum limit of 10 alerts for this month.")
    else:
        loaded_data = conversation_response(conversation.thread_id, prompt, user)
        print(loaded_data)
        try:
            response_dict = json.loads(loaded_data)
        except json.decoder.JSONDecodeError:
            response_dict = loaded_data
            
        # response_dict = json.loads(loaded_data)
        print(response_dict)
        if isinstance(response_dict, str):
            response_dict = {"main_response": response_dict, "extracted_data": []}
        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': response_dict["main_response"]})
        Message.objects.create(user =user, sender='bot',room=conversation, content=response_dict['main_response'])
        
        if response_dict['extracted_data']:
            for extracted_data in response_dict['extracted_data']:
            # extracted_data = response_dict['extracted_data']
                alertai = AlertAI.objects.create(user=user,prompt=prompt,extracted_parameters=loaded_data)
                timestamp = datetime.now().timestamp()
                if isinstance(extracted_data, dict):
                    if 'stock' in extracted_data and 'alert_type' in extracted_data and 'action' in extracted_data:
                        stock = get_object_or_404(Stock, symbol=extracted_data['stock'].upper())
                        alert_type = extracted_data['alert_type']
                        action= extracted_data['action']
                        frequency = extracted_data['frequency'] if 'frequency' in extracted_data else 'Once'
                        description = prompt
                        # expire = datetime.fromisoformat(extracted_data['expire']) if'expire' in extracted_data else timezone.now() + timedelta(weeks=2)
                        if 'to_price' in extracted_data:
                            to_price = round(float(extracted_data['to_price']),2)
                            alert_name = f"{stock.symbol} {action} {to_price} " + str(int(timestamp))
                            
                            alert = Alert.objects.create(user=user, stock=stock, alert_type=alert_type, alert_name=alert_name, to_price=to_price, frequency=frequency,description=description, action=action)
                            done = f"Price alert for {alert.stock.symbol} has been created when price goes {alert.action} {alert.to_price}"
                            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': done})
                            
                            
                            
                            
                            alertai.alert_created= True
                            alertai.save()
                            print('price alert created')
                            
                            counter.count += 1
                            counter.save()
                            
                        elif 'to_volume' in extracted_data:
                            to_volume = round(float(extracted_data['to_volume']),2)
                            alert_name = f"{stock.symbol} {action} {to_volume} " + str(int(timestamp))
                            
                            alert = Alert.objects.create(user=user, stock=stock, alert_type=alert_type, alert_name=alert_name, to_volume=to_volume, frequency=frequency,description=description, action=action)
                        
                            done = f"Volume alert for {alert.stock.symbol} has been created when volume goes {alert.action} {alert.to_volume}"
                            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': done})
                            
                            alertai.alert_created= True
                            alertai.save()
                            print('volume alert created')
                            
                            counter.count += 1
                            counter.save()
                            
               


@shared_task
def disable_old_periodic_tasks():
    """Disables all PeriodicTask objects not created in the current month and year."""
    # Get the current month and year
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # Find PeriodicTask objects not created in the current month and year
    old_periodic_tasks = PeriodicTask.objects.filter(
        ~Q(date_changed__month=current_month) | ~Q(date_changed__year=current_year)
    )

    # Disable these old periodic tasks
    old_periodic_tasks.update(enabled=False)

    # Return the count of tasks that were disabled
    return old_periodic_tasks.count()

@shared_task
def get_company_details():
    call_command("company-details",)
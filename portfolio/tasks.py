from celery import shared_task
from celery.utils.log import get_task_logger
from .models import Alert, Conversation
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json
from datetime import datetime, timedelta
from portfolio.utils import get_price
from notifications.utils import save_and_send_notification
from django.utils import timezone
from .utils import get_alert_data
from django.contrib.auth import get_user_model
from .models import Alert, AlertAI,Stock, AlertAITracker, Message
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail

User= get_user_model()

logger = get_task_logger(__name__)
channel_layer = get_channel_layer()


@shared_task
def create_alert_schedule(id):
    alert=Alert.objects.get(id=id)
    print('Alert object gotten')
    schedule, created = IntervalSchedule.objects.get_or_create(
            every=2,
            period=IntervalSchedule.MINUTES,
        )
    
    task = PeriodicTask.objects.create(
            interval=schedule,
            name=alert.alert_name,
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
    
    alert=Alert.objects.get(id=id)
    print(f"{alert.id} object gotten")
    print(alert.created.month )
    
    current_month = datetime.now().month
    if alert.created.month != current_month:
        print(f"Alert {alert.alert_name} was not created in the current month. Disabling the periodic task.")
        task = PeriodicTask.objects.get(name=alert.alert_name)
        task.enabled = False
        task.save()
        return
    
    if timezone.now() < alert.expire:
        if not alert.trigerred:
            data =get_price(alert.stock.symbol)
            if alert.alert_type == 'price':
                price=data['current_price']
                if alert.action == 'below':
                    if price < alert.to_price:
                        send_alert_email(alert.user, alert.stock.symbol,alert.alert_type,alert.action, alert.to_price)
                        save_and_send_notification(alert.user.id, f'{alert.stock} price has gone below {alert.to_price} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
                elif alert.action == 'above':
                    if price > alert.to_price:
                        send_alert_email(alert.user, alert.stock.symbol,alert.alert_type,alert.action, alert.to_price)
                        save_and_send_notification(alert.user.id, f'{alert.stock} price has gone above {alert.to_price} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
            elif alert.alert_type == 'volume':
                price=data['volume']
                if alert.action == 'below':
                    if price < alert.to_volume:
                        send_alert_email(alert.user, alert.stock.symbol,alert.alert_type,alert.action, alert.to_volume)
                        save_and_send_notification(alert.user.id, f'stock {alert.stock} volume has gone below {alert.to_volume} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
                elif alert.action == 'above':
                    if price > alert.to_volume:
                        send_alert_email(alert.user, alert.stock.symbol,alert.alert_type,alert.action, alert.to_volume)
                        save_and_send_notification(alert.user.id, f'stock {alert.stock} volume has gone above {alert.to_volume} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
        else:
            task = PeriodicTask.objects.get(name=alert.alert_name )
            task.enabled = False
            task.save()
    else:
        task = PeriodicTask.objects.get(name=alert.alert_name)
        task.enabled = False
        task.save()
    print(f'Checking for alert {alert.alert_name} completed')
    
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
  
from openai import OpenAI
import time

client = OpenAI()

def conversation_response(thread_id, prompt):
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
    while not completed:
        run2 = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        print(run2.completed_at)
        if run2.completed_at is not None:
            completed = True
            break
        else:
            time.sleep(1)
    
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    
    return messages.data[0].content[0].text.value

        
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
        loaded_data = conversation_response(conversation.thread_id, prompt)
        print(loaded_data)
        print(type(loaded_data))
        response_dict = json.loads(loaded_data)
        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': response_dict['main_response']})
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
                            to_price = float(extracted_data['to_price'])
                            alert_name = f"{stock.symbol} {action} {to_price}" + str(timestamp)
                            
                            alert = Alert.objects.create(user=user, stock=stock, alert_type=alert_type, alert_name=alert_name, to_price=to_price, frequency=frequency,description=description)
                            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': "Done"})
                            
                            
                            
                            
                            alertai.alert_created= True
                            alertai.save()
                            print('price alert created')
                            
                            counter.count += 1
                            counter.save()
                            
                        elif 'to_volume' in extracted_data:
                            to_volume = float(extracted_data['to_volume'])
                            alert_name = f"{stock.symbol} {action} {to_volume}" + str(timestamp)
                            
                            alert = Alert.objects.create(user=user, stock=stock, alert_type=alert_type, alert_name=alert_name, to_volume=to_volume, frequency=frequency,description=description)
                        
                            # async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message','message': f"Alert created for {stock.symbol} when {alert_type} is {action} {to_volume}. Frequency: {alert.frequency}" })
                            # Message.objects.create(user =user, sender='bot',room=conversation, content=f"Alert created for {stock.symbol} when {alert_type} is {action} {to_volume}. Frequency: {alert.frequency}")
                            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': "Done"})
                            
                            alertai.alert_created= True
                            alertai.save()
                            print('volume alert created')
                            
                            counter.count += 1
                            counter.save()
                            
               
                    
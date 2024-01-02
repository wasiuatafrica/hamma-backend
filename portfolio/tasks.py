from celery import shared_task
from celery.utils.log import get_task_logger
from .models import Alert
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json
from datetime import datetime
from portfolio.utils import get_price
from notifications.utils import save_and_send_notification
from django.utils import timezone
from django.core.management import call_command

logger = get_task_logger(__name__)


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
            name=f"Alert Schedule  for {alert.alert_name}",
            task='portfolio.tasks.check_alert',
            args=json.dumps([alert.id])
        )
    save_and_send_notification(alert.user.id, f"You created alert for {alert.stock.symbol}")
    print(f"Alert created for {alert.user} on {alert.stock}")
    
def send_alert_email(email,description):
    pass
    
@shared_task
def check_alert(id):
    
    alert=Alert.objects.get(id=id)
    print(f"{alert.id} object gotten")
    if timezone.now() < alert.expire:
        if not alert.trigerred:
            data =get_price(alert.stock.symbol)
            if alert.alert_type == 'price':
                price=data['current_price']
                if alert.action == 'below':
                    if price < alert.to_price:
                        send_alert_email(alert.user, alert.description)
                        save_and_send_notification(alert.user.id, f'{alert.stock} price has gone below {alert.to_price} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
                elif alert.action == 'above':
                    if price > alert.to_price:
                        send_alert_email(alert.user, alert.description)
                        save_and_send_notification(alert.user.id, f'{alert.stock} price has gone above {alert.to_price} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
            elif alert.alert_type == 'volume':
                price=data['volume']
                if alert.action == 'below':
                    if price < alert.to_volume:
                        send_alert_email(alert.user, alert.description)
                        save_and_send_notification(alert.user.id, f'{alert.stock} volume has gone below {alert.to_volume} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
                elif alert.action == 'above':
                    if price > alert.to_volume:
                        send_alert_email(alert.user, alert.description)
                        save_and_send_notification(alert.user.id, f'{alert.stock} volume has gone above {alert.to_volume} for the {alert.alert_name}.')
                        if alert.frequency == 'Once':
                            alert.trigerred=True
                            alert.save()
        else:
            task = PeriodicTask.objects.get(name=f"Alert Schedule  for {alert.alert_name}")
            task.enabled = False
            task.save()
    else:
        task = PeriodicTask.objects.get(name=f"Alert Schedule  for {alert.alert_name}")
        task.enabled = False
        task.save()
    print(f'Checking for alert {alert.alert_name} completed')
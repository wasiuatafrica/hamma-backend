# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from django.db.models import Q
from portfolio.models import Alert
from datetime import datetime, timedelta
from notifications.utils import save_and_send_notification
from django.utils import timezone
from portfolio.market_hours import is_trading_time
from portfolio.prices import PriceUnavailable
from portfolio.utils import get_price
from portfolio.tasks import send_alert_email
class Command(BaseCommand):
    help = 'check alert'

    def handle(self, *args, **options):
        current_month = datetime.now().month
        current_year = datetime.now().year
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        
        alerts = Alert.objects.filter(
            created__month=current_month,
            created__year=current_year,
            trigerred=False
        ).filter(
            Q(last_email_sent__isnull=True) | Q(last_email_sent__lte=thirty_minutes_ago)
        )
        print(len(alerts))
        for alert in alerts:
            print(alert.frequency, alert.trigerred,alert.last_email_sent)
            current_time = timezone.now()
            
            if is_trading_time(current_time):
                if timezone.now() < alert.expire:
                    try:
                        data = get_price(alert.stock.symbol)
                    except PriceUnavailable:
                        continue  # never evaluate alerts against a missing/0 price
                    print(data)
                    if alert.alert_type == 'price':
                        price = data['current_price']
                        if alert.action == 'below':
                            if price < alert.to_price:
                                if (alert.last_email_sent and (timezone.now() - alert.last_email_sent) >= timedelta(minutes=30)) or not alert.last_email_sent:
                                    send_alert_email(alert.user, alert.stock.symbol, alert.alert_type, alert.action, alert.to_price)
                                    print('sent')
                                    save_and_send_notification(alert.user.id, f'{alert.stock} price has gone below {alert.to_price} for the {alert.alert_name}.')
                                    if alert.frequency in ['Once', 'once']:
                                        alert.trigerred = True
                                        
                                        alert.last_email_sent = timezone.now()
                                        alert.save()
                                    else:
                                        alert.last_email_sent = timezone.now()
                                        alert.save()
                        elif alert.action == 'above':
                            if price > alert.to_price:
                                if (alert.last_email_sent and (timezone.now() - alert.last_email_sent) >= timedelta(minutes=30)) or not alert.last_email_sent:
                                    send_alert_email(alert.user, alert.stock.symbol, alert.alert_type, alert.action, alert.to_price)
                                    print('sent')
                                    save_and_send_notification(alert.user.id, f'{alert.stock} price has gone above {alert.to_price} for the {alert.alert_name}.')
                                    if alert.frequency in ['Once', 'once']:
                                        alert.trigerred = True
                                        
                                        alert.last_email_sent = timezone.now()
                                        alert.save()
                                        print('saved')
                                        
                                    else:
                                        alert.last_email_sent = timezone.now()
                                        alert.save()
                                        print('saved')
                    elif alert.alert_type == 'volume':
                        price = data['volume']
                        if alert.action == 'below':
                            if price < alert.to_volume:
                                send_alert_email(alert.user, alert.stock.symbol, alert.alert_type, alert.action, alert.to_volume)
                                save_and_send_notification(alert.user.id, f'stock {alert.stock} volume has gone below {alert.to_volume} for the {alert.alert_name}.')
                                if alert.frequency in ['Once', 'once']:
                                        alert.trigerred = True
                                        
                                        alert.last_email_sent = timezone.now()
                                        alert.save()
                                else:
                                    alert.last_email_sent = timezone.now()
                                    alert.save()
                        elif alert.action == 'above':
                            if price > alert.to_volume:
                                send_alert_email(alert.user, alert.stock.symbol, alert.alert_type, alert.action, alert.to_volume)
                                save_and_send_notification(alert.user.id, f'stock {alert.stock} volume has gone above {alert.to_volume} for the {alert.alert_name}.')
                                if alert.frequency in ['Once', 'once']:
                                        alert.trigerred = True
                                        
                                        alert.last_email_sent = timezone.now()
                                        alert.save()
                                else:
                                    alert.last_email_sent = timezone.now()
                                    alert.save()
            
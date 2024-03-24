from django.core.management.base import BaseCommand
from api.models import TradeAccount, UserAccounts, SecondTradeAccount
from datetime import datetime
from django.contrib.auth import get_user_model

User =get_user_model()

from api.views import AccountDrawdownViolationNotification, get_fca_sca_records, get_first_trading_day
from api.models import TraderNotification, AsoAccountRequestTable
from leaderboard.leaderboard_utils import save_and_send_notification, get_notifications, update_notification


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        # user = User.objects.get(email='owenyakubu533@gmail.com')
        # print(user.id)
        # save_and_send_notification(38,'Testing here again as instructed but to check stuff')
        # save_and_send_notification(38,'Testing here second time')
        my_notifs = get_notifications(38)
        print(my_notifs)
        # for noti in my_notifs:
        #     print(type(noti['notification_id']))
        #     update_notification(12,str(noti['notification_id']))
        # my_notifs2 = get_notifications(12)
        # print(my_notifs2) 
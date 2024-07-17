from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model
from competition.tasks import trading_rule_task, trading_ideas_task
from competition.start_competition_mails import send_trade_reminder, send_daily_trade_confirmation, send_trading_rules, send_trading_idea

from django.utils import timezone

from portfolio.models import DashboardFeed
User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        user = User.objects.get(email='nexxyb@gmail.com')
        # user = User.objects.get(email='teamgohamma@gmail.com')
        # user = User.objects.get(email='teamft9ja@gmail.com')
        # user = User.objects.get(email='ideafabulous@gmail.com')
        
        # print(user.firstname)
        # send_trade_reminder(user)
    #     context ={
    #     'first_name':'Team',
    #     'date':datetime.now(),  
    #     'stock':'ZENITHBANK',  
    #     'type':'Buy',
    #     'price':'12',  
    #     'quantity':150000,
    #     'id':'ki78844d11'
    # }
    #     send_daily_trade_confirmation(user,context)
        # send_trading_rules(user)
        
        feed = DashboardFeed.objects.last()
        # print(feed.stock.logo_url)
        context = {
        'topic':feed.topic,
        'symbol_url':feed.stock.logo_url,
        'posted_date':feed.published_date,
        'title':feed.title,
        'image_url':feed.image.url,
        'image_caption':feed.image_caption,
        'point1':feed.bullet_1,
        'point2':feed.bullet_2,
        'point3':feed.bullet_3,
    }
        print(context)
        send_trading_idea(user, context)
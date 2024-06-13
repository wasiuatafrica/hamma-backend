from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.management import call_command
from django.shortcuts import get_object_or_404

from execution.utils import competition_daily_returns4, daily_returns5, get_positions, daily_returns3, competition_daily_returns3
from .serializers import DemoPositionSerializer
from anyon.views import User
from portfolio.models import Message, Conversation, Stock, MarketAI,DemoTransaction
from .models import   DemoPortfolio,DemoPosition, DemoDailyReturns, DemoCumulativeReturns
from random import uniform
from django.db import transaction
from time import sleep
from decimal import Decimal
from datetime import datetime, timedelta,time
from portfolio.utils import get_price, get_stockdata2
from notifications.utils import save_and_send_notification
from django_celery_beat.models import PeriodicTask
from django.utils import timezone
import pytz
from accounts.models import  UserActivityLog 
import json
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import shortuuid
import time as timer
from competition.models import Competition, CompetitionPortfolio, CompetitionPosition, CompetitionTransaction, CompetitionDailyReturns, CompetitionCumulativeReturns
import pandas as pd
import os
from pymongo import MongoClient

logger = get_task_logger(__name__)
channel_layer = get_channel_layer()

MONGO_URL = os.environ.get('MONGO_STRING')
mongo_client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
db_merged = mongo_client["livelake3"]
collection_merged = db_merged["merged_live_price"]

BANK_HOLIDAYS = [
    datetime(2024, 1, 1),   # New Year's Day
    datetime(2024, 4, 7),   # Good Friday
    datetime(2024, 4, 10),  # Easter Monday
    datetime(2024, 5, 1),   # Workers' Day
    datetime(2024, 5, 27),  # Children's Day
    datetime(2024, 6, 17),  
    datetime(2024, 6, 18),  
    datetime(2024, 10, 1),  # Independence Day
    datetime(2024, 12, 25), # Christmas Day
    
]

lagos_tz = pytz.timezone('Africa/Lagos')
BANK_HOLIDAYS = [lagos_tz.localize(date) for date in BANK_HOLIDAYS]
# print(BANK_HOLIDAYS)
def get_equity_data(user):
        portfolio = DemoPortfolio.objects.get(user=user)
        
        equity = portfolio.equity
        
        positions_query = DemoPosition.objects.filter(portfolio=portfolio)
        
        def calc_pnl(position):
            cost = position.average_price * position.quantity
            current = position.current_price * position.quantity
            return float(Decimal(current) - cost)
        
        def market_returns(current_portfolio_value, days=7):
            volatility_factor = 15  

            market_returns = [round(float(Decimal(uniform(-volatility_factor, volatility_factor)) + current_portfolio_value), 2) for _ in range(days)]
            portfolio_returns = [round(float(Decimal((1 + market_return)) + current_portfolio_value),2) for market_return in market_returns]

            end_date = datetime.now().date()
            date_list = [(end_date - timedelta(days=i)).isoformat() for i in range(days)][::-1]

            result_data = [
                {"date": date, "portfolio_returns": portfolio, "market_returns": market}
                for date, portfolio, market in zip(date_list, portfolio_returns, market_returns)
            ]

            return result_data
        positions = [{
            'date':position.created.isoformat(),
            'pnl':calc_pnl(position)
        } for position in positions_query]
        
        print(portfolio.calculate_portfolio_return())
        overview = market_returns(portfolio.calculate_portfolio_return())
        
        data =    {"equity":float(equity), "positions":positions, "overview":overview}
        
        return data

@shared_task
def update_equity(user_id,type):
    user= User.objects.get(id=user_id)
    
    if type == 'demo':
        
        data =get_equity_data(user)
        
        async_to_sync(channel_layer.group_send)(
                f'demo-equity-{user_id}',
                {
                    'type': 'send_message',
                    'data': data,
                }
            )
        
@shared_task
def process_limit_order(id, in_competition=False):
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    competition = Competition.objects.filter(status='current').first()

    # Check if the current time is between 9:30 AM and 2:30 PM WAT and it's a weekday
    if current_time_lagos.time() >= datetime.strptime('9:30 AM', '%I:%M %p').time() and current_time_lagos.time() <= datetime.strptime('2:30 PM', '%I:%M %p').time() and current_time_lagos.weekday() < 5:
        if in_competition and timezone.now() > competition.start_date:
            position = get_object_or_404(CompetitionPosition, id=id)
            
            user = position.portfolio.user
            
            expired = False
            
            target = time(14, 30)  # 14 is the hour, 30 is the minute
            target_time = datetime.combine(current_time_lagos.date(), target).astimezone(lagos_timezone)
            
            # target_time = datetime.combine(datetime.today(), datetime.strptime('14:30', '%H:%M').time())
            if position.status == 'pending':
            
                if position.time_in_force== 'day':
                    

                    # Check if the current time is before 2:30 PM
                    if current_time_lagos > target_time:
                        task = PeriodicTask.objects.get(name=position.alert_name)
                        task.enabled = False
                        task.save()
                        
                        position.status= 'cancelled'
                        position.save()
                        
                        expired =True
                        save_and_send_notification(user.id,f'COMPETITION: Your pending order has been cancelled because the position cannot be filled before close of trade session today.')
                        
                        
                elif position.time_in_force== 'week':

                    # Check if the current time is before 2:30 PM
                    if timezone.now().astimezone(lagos_timezone).weekday() == 4 and current_time_lagos > target_time:
                        task = PeriodicTask.objects.get(name=position.alert_name)
                        task.enabled = False
                        task.save()
                        
                        position.status= 'cancelled'
                        position.save()
                        
                        expired =True
                        
                        save_and_send_notification(user.id,f'COMPETITION: Your pending order has been cancelled because the position cannot be filled before close of trade session.')
                        
                if not expired and current_time_lagos < target_time:
                    
                    data =get_price(position.stock.symbol)
                    price=data['current_price']
                    balance =  position.portfolio.balance
                    
                    if position.action == 'buy':
                        if price <= position.limit_price:
                            
                            amount = round(Decimal(price) * position.quantity,2)
                            trade_commission = round(Decimal(0.00435) * amount, 2) + 200
                    
                            total= amount + trade_commission
                            
                            if balance >= total:
                                position.status= 'open'
                                position.open_price = Decimal(price)
                                position.amount_invested = amount
                                position.save()
                            
                                CompetitionTransaction.objects.create(
                                        user=user,
                                        transaction_type='open trade',
                                        amount=position.amount_invested,
                                        status='completed'
                                    )
                                
                                CompetitionTransaction.objects.create(
                                        user=user,
                                        transaction_type='trade commission',
                                        amount=trade_commission,
                                        status='completed'
                                    )
                                
                                position.portfolio.balance -= total
                                position.portfolio.save()
                                
                                activity=UserActivityLog.objects.create(user=user, action_type="competition_open_trade",description=f"User opened competition trade with  {position.amount_invested}naira on {position.stock.symbol}.")
                                
                                save_and_send_notification(user.id,f' COMPETITION: You opened position {position.quantity} units of {position.stock.symbol} at {price} per unit. Total value:{position.amount_invested}naira ')
                            else:
                                save_and_send_notification(user.id,f' COMPETITION: Your pending order:  {position.quantity} units of {position.stock.symbol}  cannot be filled because you do not have sufficient funds.')
                                

                    elif position.action == 'sell':
                        if price >= position.limit_price:
                            amount = round(Decimal(price) * position.quantity,2)
                            trade_commission = round(Decimal(0.00435) * amount, 2) + 200
                    
                            total= amount + trade_commission
                            
                            if balance >= total:
                                position.status= 'open'
                                position.open_price = Decimal(price)
                                position.amount_invested = amount
                                position.save()
                            
                                CompetitionTransaction.objects.create(
                                        user=user,
                                        transaction_type='open trade',
                                        amount=position.amount_invested,
                                        status='completed'
                                    )
                                
                                CompetitionTransaction.objects.create(
                                        user=user,
                                        transaction_type='trade commission',
                                        amount=trade_commission,
                                        status='completed'
                                    )
                                
                                position.portfolio.balance -= total
                                position.portfolio.save()
                                
                                activity=UserActivityLog.objects.create(user=user, action_type="competition_open_trade",description=f"User opened competition trade with  {position.amount_invested}naira on {position.stock.symbol}.")
                                
                                save_and_send_notification(user.id,f' COMPETITION: You opened position {position.quantity} units of {position.stock.symbol} at {price} per unit. Total value:{position.amount_invested}naira ')
                            else:
                                save_and_send_notification(user.id,f' COMPETITION: Your pending order:  {position.quantity} units of {position.stock.symbol}  cannot be filled because you do not have sufficient funds.')
                                
                    print(f"limit order {position.alert_name} checked")
            else:
                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()
                
        else:
            position = get_object_or_404(DemoPosition, id=id)
            
            user = position.portfolio.user
            
            expired = False
            
            lagos_timezone = pytz.timezone('Africa/Lagos')
            current_time_lagos = timezone.now().astimezone(lagos_timezone).time()

            target_time = time(14, 30)  # 14 is the hour, 30 is the minute
            # target_time = datetime.combine(datetime.today(), datetime.strptime('14:30', '%H:%M').time())
            if position.status == 'pending':
            
                if position.time_in_force== 'day':
                    

                    # Check if the current time is before 2:30 PM
                    if current_time_lagos > target_time:
                        task = PeriodicTask.objects.get(name=position.alert_name)
                        task.enabled = False
                        task.save()
                        
                        position.status= 'cancelled'
                        position.save()
                        
                        expired =True
                        save_and_send_notification(user.id,f'DEMO: Your pending order has been cancelled because the position cannot be filled before close of trade session today.')
                        
                        
                elif position.time_in_force== 'week':

                    # Check if the current time is before 2:30 PM
                    if timezone.now().astimezone(lagos_timezone).weekday() == 4 and current_time_lagos > target_time:
                        task = PeriodicTask.objects.get(name=position.alert_name)
                        task.enabled = False
                        task.save()
                        
                        position.status= 'cancelled'
                        position.save()
                        
                        expired =True
                        
                        save_and_send_notification(user.id,f'DEMO: Your pending order has been cancelled because the position cannot be filled before close of trade session.')
                        
                if not expired and current_time_lagos < target_time:
                    
                    data =get_price(position.stock.symbol)
                    price=data['current_price']
                    if position.action == 'buy':
                        if price <= position.limit_price:
                            position.status= 'open'
                            position.open_price = Decimal(price)
                            position.amount_invested = round(Decimal(price) * position.quantity,2)
                            position.save()
                        
                            DemoTransaction.objects.create(
                                    user=user,
                                    transaction_type='open trade',
                                    amount=position.amount_invested,
                                    status='completed'
                                )
                            activity=UserActivityLog.objects.create(user=user, action_type="demo_open_trade",description=f"User opened demo trade with  {position.amount_invested}naira on {position.stock.symbol}.")
                            
                            save_and_send_notification(user.id,f' DEMO: You opened position {position.quantity} units of {position.stock.symbol} at {price} per unit. Total value:{position.amount_invested}naira ')

                    elif position.action == 'sell':
                        if price >= position.limit_price:
                            position.status= 'open'
                            position.open_price = Decimal(price)
                            position.amount_invested = round(Decimal(price) * position.quantity, 2)
                            position.save()
                        
                            DemoTransaction.objects.create(
                                    user=user,
                                    transaction_type='open trade',
                                    amount=position.amount_invested,
                                    status='completed'
                                )
                            save_and_send_notification(user.id,f' DEMO: You opened position {position.quantity} units of {position.stock.symbol} at {price} per unit. Total value:{position.amount_invested}naira ')
                    print(f"limit order {position.alert_name} checked")
            else:
                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()
    else:
        print("Outside trading hours")
            


@shared_task
def get_daily_profit_loss():
    today = datetime.now().weekday()
    if today < 5:
        users = User.objects.all()
        for user in users:
            positions = DemoPosition.objects.filter(portfolio__user=user,status='open')
            if positions:
                total_invested  = sum([post.amount_invested for post in positions])
                position_shares = []
                for position in positions:
                    pl,value,price = position.calculate_profit_loss() 
                    returned =  (Decimal(value)/position.amount_invested) - 1
                    weight = (position.amount_invested/total_invested )
                    
                    position_shares.append(returned*weight)
                shares = round(sum(position_shares)*100,2)
                print('return', shares)
                # DemoDailyReturns.objects.create(user=user, portfolio_returns=shares)
                print(f"{user.email} daily profit/loss calculated")
    else:
        print("Not running on weekends.")

@shared_task
def daily_returns():
    today1 = datetime.now()
    today = today1.weekday()
    
    if today < 5:
        users = User.objects.all()
        data = get_price('ASI')
        pr = data['current_price']
        print(data)
        # pr = 24.15
        
        for user in users:
            positions = DemoPosition.objects.filter(portfolio__user=user,status='close')
            
            
            if positions:
                
                    
                total_invested  = sum([post.amount_invested for post in positions])
                position_shares = []
                for position in positions:
                    # pl,value,price = position.calculate_profit_loss() 
                    value = position.amount_invested + position.profit_loss
                    returned =  (Decimal(value)/position.amount_invested) - 1
                    weight = (position.amount_invested/total_invested )
                    
                    position_shares.append(returned*weight)
                shares = round(sum(position_shares)*100,2)
                
                last_ngx_query = DemoDailyReturns.objects.filter(user=user).last()
                # print(last_ngx_query.ngx_price)
                if last_ngx_query:
                    last_ngx = last_ngx_query.ngx_price
                    market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                
                    print('return', shares)
                else:
                    market_returns = 0
                # last_ngx = 25.5
                
                # market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                    
                DemoDailyReturns.objects.create(user=user, portfolio_returns=shares, market_returns =market_returns, ngx_price=pr)
                print(f"{user.email} daily profit/loss calculated")
            
    else:
        print("Not running on weekends.")

@shared_task
def cumulative_returns():
    today1 = datetime.now()
    today = today1.weekday()
    
    if today < 5:
        users = User.objects.all()
        data = get_price('ASI')
        pr = data['current_price']
        print(data)
        # pr = 24.15
        
        for user in users:
            positions = DemoPosition.objects.filter(portfolio__user=user,status='close')
            
            
            if positions:
                
                    
                total_invested  = sum([post.amount_invested for post in positions])
                position_shares = []
                for position in positions:
                    pl,value,current_price = position.calculate_profit_loss() 
                    returned =  (Decimal(current_price)/position.open_price) - 1
                    
                    weight = (position.amount_invested/total_invested ) 
                    
                    position_shares.append(returned*weight)
                shares = round(sum(position_shares)*100,2)
                
                last_ngx_query = DemoCumulativeReturns.objects.filter(user=user).first()
                # print(last_ngx_query.ngx_price)
                if last_ngx_query:
                    last_ngx = last_ngx_query.ngx_price
                    market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                
                    print('return', shares)
                else:
                    market_returns = 0
                # last_ngx = 25.5
                
                # market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                    
                DemoCumulativeReturns.objects.create(user=user, portfolio_returns=shares, market_returns =market_returns, ngx_price=pr)
                print(f"{user.email} daily profit/loss calculated")
            
    else:
        print("Not running on weekends.")

@shared_task
def competition_daily_returns():
    today = datetime.now().weekday()
    if today < 5:
        users = User.objects.all()
        data = get_price('ASI')
        pr = data['current_price']
        print(data)
        # pr = 24.15
        
        for user in users:
            portfolio =  CompetitionPortfolio.objects.filter(user=user, competition__status='current',active=True).first()
            if portfolio:
                positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='close',updated__date =datetime.now().date() )
            else:
                positions = None
            
            
            if positions:
                
                    
                total_invested  = sum([post.amount_invested for post in positions])
                position_shares = []
                for position in positions:
                    # pl,value,price = position.calculate_profit_loss() 
                    value = position.amount_invested + position.profit_loss
                    returned =  (Decimal(value)/position.amount_invested) - 1
                    weight = (position.amount_invested/total_invested )
                    
                    position_shares.append(returned*weight)
                shares = round(sum(position_shares)*100,2)
                
                last_ngx_query = CompetitionDailyReturns.objects.filter(user=user).last()
                # print(last_ngx_query.ngx_price)
                if last_ngx_query:
                    last_ngx = last_ngx_query.ngx_price
                    market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                
                    print('return', shares)
                else:
                    market_returns = 0
                # last_ngx = 25.5
                
                # market_returns = round(((pr - last_ngx)/last_ngx) *100,2)
                    
                CompetitionDailyReturns.objects.create(user=user, portfolio_returns=shares, market_returns =market_returns, ngx_price=pr,portfolio=portfolio)
                print(f"{user.email} daily profit/loss calculated")
            
                
                
    else:
        print("Not running on weekends.")
        
@shared_task                  
def update_latest_competition_cumulative_returns():
    today = datetime.now().weekday()
    if today < 5:
        users = User.objects.all()

        for user in users:
            portfolio =  CompetitionPortfolio.objects.filter(user=user, competition__status='current',active=True).first()
            if portfolio:
                latest_daily_return = CompetitionDailyReturns.objects.filter(user=user).order_by('-created').first()

                if latest_daily_return:
                    daily_returns = CompetitionDailyReturns.objects.filter(user=user, created__lte=latest_daily_return.created).order_by('created')
                    data = {
                        'portfolio_returns': [dr.portfolio_returns/100 for dr in daily_returns],
                        'market_returns': [dr.market_returns/100 for dr in daily_returns],
                        'ngx_price': [dr.ngx_price for dr in daily_returns],
                        'created': [dr.created for dr in daily_returns]
                    }
                    df = pd.DataFrame(data)

                    if len(df) > 1:
                        df['portfolio_cumulative'] = (1 + df['portfolio_returns']).cumprod() - 1
                        df['market_cumulative'] = (1 + df['market_returns']).cumprod() - 1
                        portfolio_cumulative = df['portfolio_cumulative'].iloc[-1]
                        market_cumulative = df['market_cumulative'].iloc[-1]
                    else:
                        portfolio_cumulative = latest_daily_return.portfolio_returns
                        market_cumulative = latest_daily_return.market_returns

                    ngx_price = df['ngx_price'].iloc[-1]

                    CompetitionCumulativeReturns.objects.create(
                        user=user,
                        created=latest_daily_return.created,
                        portfolio_returns= round(portfolio_cumulative*100,2),
                        market_returns=round(market_cumulative*100,2),
                        ngx_price=ngx_price,
                        portfolio=portfolio
                        
                    )
                

from openai import OpenAI
from .symbol_pair import pairs
def get_alert_data(prompt):
    client = OpenAI()

    model = '''
    class DemoPosition(auto_prefetch.Model):
    OPEN = 'open'
    CLOSED = 'close'
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    
    STATE_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
        (PENDING,'Pending'),
        (CANCELLED, 'Cancel')
    ]
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, related_name='demopositions2')
    quantity = models.PositiveIntegerField(default=0)
    limit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    action = models.CharField(max_length=20, default='buy')
    time_in_force = models.CharField(max_length=20, default='day')
        
    '''
    # prompt = '''
    # notify me for ZENITHBANK stock everytime the volume goes below 9320 before 7 january 2024 3pm
    # '''
    # prompt = '''
    # alert me everytime WEMABANK price goes below 93.20 before 7 january 2024 3pm
    # '''

    response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful django software development assistant helping in creating auto trading system."},
        {"role": "user", "content": f''' i have company name and symbol pairing {pairs} useful for getting appropriate symbol that will be value of "stocks". 
         i want to extract parameters from - {prompt} - to create django model {model}. can you 
            extract the needed parameter in python dictionary  format only as the response, the expected dict keys are model field names.
            don't write write any explanation before or after the dictionary,all keys and values must be string and in double quotation marks. 
            I only want the dictionary as response, nothing else, dont explain anything even if you made assumptions.
            '''}
    ]
    )


    # print(response)
    # print(response['choices'][0]['message']['content'])
    return response.choices[0].message.content



@shared_task
def get_data_prompt(prompt):
    data = get_alert_data(prompt)
    print(data)
    return data
   
@shared_task
def process_market_data(prompt, convsersation_id, user_id, channel_name):
    print(prompt)
    loaded_data = get_data_prompt(prompt)
    user= User.objects.get(id=user_id)
    
    portfolio =get_object_or_404(DemoPortfolio, user=user)
    conversation = Conversation.objects.get(name=convsersation_id)
    extracted_data = json.loads(loaded_data)
    
    print(extracted_data)
        
    marketai = MarketAI.objects.create(user=user,prompt=prompt,extracted_parameters=loaded_data)
        
    if isinstance(extracted_data, dict):
        if 'stock' in extracted_data and 'quantity' in extracted_data and 'action' in extracted_data and 'limit_price' in extracted_data:
            if not extracted_data['quantity'] or int(extracted_data['quantity']) <= 0 :
                message = f"You must provide quantity to be traded and must be greater than 100."
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
                return
            
            if extracted_data['action'] not in ['buy', 'sell']:
                message = f"You must provide action to be traded and must be buy or sell."
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
                return
            if not extracted_data['limit_price'] or float(extracted_data['limit_price']) <= 0 :
                stock = get_object_or_404(Stock, symbol=extracted_data['stock'].upper())
                quantity = int(extracted_data['quantity'])
                open_price = get_price(stock.symbol)['current_price']
                action= extracted_data['action']
                
                balance =portfolio.balance
                
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Checking your balance..."})
                
                timer.sleep(2)
                
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Sufficient balance."})
                
                timer.sleep(1)
                
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Creating order..."})
                
                position = DemoPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    quantity=quantity,
                    open_price=open_price,
                    action=action, 
                    alert_name=shortuuid.uuid() + f" {user.email}",
                    amount_invested=quantity * Decimal(open_price),
                )
                
                timer.sleep(1)
                
                message = f"Position opened for {position.stock.symbol} at price of  {position.open_price}, total invested = {position.quantity * float(position.open_price)} naira"
                
                
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
                UserActivityLog.objects.create(user=user, action_type="demo_open_trade",description=f"User opened demo trade with amount {position.amount_invested} on symbol {position.stock.symbol}.")
               
                Message.objects.create(user =user, sender='bot',room=conversation, content=message)
                save_and_send_notification(user.id,f' DEMO: You opened position {position.quantity} units of {position.stock.symbol} at {position.open_price} per unit. Total value:{position.quantity * position.open_price} naira ')
                
                marketai.position_created= True
                marketai.save()
                return
            
            portfolio =get_object_or_404(DemoPortfolio, user=user)
            stock = get_object_or_404(Stock, symbol=extracted_data['stock'].upper())
            quantity = extracted_data['quantity'] 
            limit_price = extracted_data['limit_price'] 
            status= "pending"
            action= extracted_data['action']
            
            balance =portfolio.balance
            
            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Checking your balance..."})
            
            timer.sleep(2)
            
            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Sufficient balance."})
            
            timer.sleep(1)
            
            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Creating order..."})
            
            position = DemoPosition.objects.create(
                portfolio=portfolio,
                stock=stock,
                quantity=quantity,
                limit_price=limit_price,
                status=status,
                action=action, 
                alert_name=shortuuid.uuid() + f" {user.email}",
                time_in_force='week',
                order_type='limit'
            )
            
            timer.sleep(1)
            
            if position.action == 'buy':
                message = f"Order to buy {position.stock.symbol} created and position will be opened when price is below or equal to {position.limit_price} naira."
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
            elif position.action == 'sell':
                message = f"Order to sell {position.stock.symbol} created and position will be opened when price is above or equal to {position.limit_price} naira."
                async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
            
            Message.objects.create(user =user, sender='bot',room=conversation, content=message)
            
            
            marketai.position_created= True
            marketai.save()
            
            schedule, created = IntervalSchedule.objects.get_or_create(
                    every=3,
                    period=IntervalSchedule.MINUTES,
                )
            
            task = PeriodicTask.objects.create(
                    interval=schedule,
                    name=position.alert_name,
                    task='execution.tasks.process_limit_order',
                    args=json.dumps([position.id])
                )
            print('demo position created')
                
            
                
        else:
            async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message','message': "Your prompt does not contain stock symbol, limit price, either to buy or sell,  or you didn't specify quantity." })
            Message.objects.create(user =user, sender='bot',room=conversation, content="Your prompt does not contain stock symbol, limit price, either to buy or sell,  or you didn't specify quantity.")
            
    else:
        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message','message': "Your prompt does not contain stock symbol, limit price, either to buy or sell,  or you didn't specify quantity." })
        Message.objects.create(user =user, sender='bot',room=conversation, content="Your prompt does not contain stock symbol, limit price, either to buy or sell,  or you didn't specify quantity.")

from openai import OpenAI
# import time
import concurrent.futures

client = OpenAI()

def conversation_response(thread_id, prompt,user):
    assistant_id = "asst_5dMX8Zzdmf0NTNoMqV6pNsPH"
    
        
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content= prompt
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    
    completed = False
    start_time = timer.time()
    
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
                arguments = json.loads(tool_call.function.arguments)
                if name == 'get_current_stock_price':
                    
                    symbol = arguments['symbol']
                    price = get_price(symbol)
                    
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps([str(price)]),
                    }
                elif name == 'get_trade_positions':
                    status = arguments['status']
                    positions = get_positions(user, status  )
                    
                    return {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps([positions]),
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

            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
                )
        elif run.status in  ["cancelling", "cancelled", "failed", "expired"]:
            return '{"main_response": "Error occured, please start new conversation", "extracted_data": []}'
        else:
            timer.sleep(0.5)
            
        elapsed_time = timer.time() - start_time
        
        if elapsed_time >= 30:
            break
    # print(completed)  
    if completed:
        messages = client.beta.threads.messages.list(thread_id=thread_id,order="asc", after=message.id)
        
        return messages.data[0].content[0].text.value
    else:
        return '{"main_response": "Error occured, please start new conversation", "extracted_data": []}'



@shared_task
def process_market_data2(prompt, convsersation_id, user_id, channel_name):
    print(prompt)
    # loaded_data = get_data_prompt(prompt)
    user= User.objects.get(id=user_id)
    
    portfolio =get_object_or_404(DemoPortfolio, user=user)
    # positions_query = DemoPosition.objects.filter(portfolio=portfolio)
    # positions = DemoPositionSerializer (positions_query, many=True).data 
    
    conversation = Conversation.objects.get(name=convsersation_id)
    loaded_data = conversation_response(conversation.thread_id, prompt, user)
    
    try:
        response_dict = json.loads(loaded_data)
    except json.decoder.JSONDecodeError:
        response_dict = loaded_data
        
    # response_dict = json.loads(loaded_data)
    print(response_dict)
    if isinstance(response_dict, str):
        response_dict = {"main_response": response_dict, "extracted_data": []}
    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': response_dict['main_response']})
    Message.objects.create(user =user, sender='bot',room=conversation, content=response_dict['main_response'])
    
        
    if response_dict['extracted_data']:
        marketai = MarketAI.objects.create(user=user,prompt=prompt,extracted_parameters=loaded_data)
        for extracted_data in response_dict['extracted_data']:
        
 
            if 'stock' in extracted_data and 'quantity' in extracted_data and 'action' in extracted_data:
                if not extracted_data['quantity'] or int(extracted_data['quantity']) <= 0 :
                    message = f"You must provide quantity to be traded and must be greater than 100."
                    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
                    return
                
                if extracted_data['action'] not in ['buy', 'sell']:
                    message = f"You must provide action to be traded and must be buy or sell."
                    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': message})
                    return
                
                if 'limit_price' in extracted_data and  extracted_data['limit_price'] and float(extracted_data['limit_price']) >= 0 :
                    
                    stock = get_object_or_404(Stock, symbol=extracted_data['stock'].upper())
                    quantity = int(extracted_data['quantity'])
                    limit_price = extracted_data['limit_price'] 
                    status= "pending"
                    action= extracted_data['action']
                    
                    # balance =portfolio.balance
                    
                    # async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Checking your balance..."})
                    
                    # timer.sleep(2)
                    
                    # async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Sufficient balance."})
                    
                    timer.sleep(2)
                    
                    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Creating order..."})
                    
                    position = DemoPosition.objects.create(
                        portfolio=portfolio,
                        stock=stock,
                        quantity=quantity,
                        limit_price=limit_price,
                        status=status,
                        action=action, 
                        alert_name=shortuuid.uuid() + f" {user.email}",
                        time_in_force='week',
                        order_type='limit'
                    )
                    
                    async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"DEMO: {position.quantity} units of {position.stock.symbol} has been scheduled to open when the price gets to {position.limit_price}."})
                                        
                    marketai.position_created= True
                    marketai.save()
                    
                    schedule, created = IntervalSchedule.objects.get_or_create(
                            every=3,
                            period=IntervalSchedule.MINUTES,
                        )
                    
                    task = PeriodicTask.objects.create(
                            interval=schedule,
                            name=position.alert_name,
                            task='execution.tasks.process_limit_order',
                            args=json.dumps([position.id])
                        )
                    print('demo position created')
                else:
                    if 'limit_price' not in extracted_data or not extracted_data['limit_price']:
                        stock = get_object_or_404(Stock, symbol=extracted_data['stock'].upper())
                        quantity = int(extracted_data['quantity'])
                        open_price = get_price(stock.symbol)['current_price']
                        action= extracted_data['action']
                        
                        # balance =portfolio.balance
                        
                        # async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Checking your balance..."})
                        
                        # timer.sleep(2)
                        
                        # async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Sufficient balance."})
                        
                        timer.sleep(2)
                        
                        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Creating order..."})
                        
                        position = DemoPosition.objects.create(
                            portfolio=portfolio,
                            stock=stock,
                            quantity=quantity,
                            open_price=open_price,
                            action=action, 
                            alert_name=shortuuid.uuid() + f" {user.email}",
                            amount_invested=quantity * Decimal(open_price),
                        )
                        
               
                        async_to_sync(channel_layer.send)(channel_name, {'type': 'send_message', 'message': f"Demo Position opened. {position.quantity} unit of {position.stock.symbol} has been opened at {position.open_price}."})
                        UserActivityLog.objects.create(user=user, action_type="demo_open_trade",description=f"User opened demo trade with amount {position.amount_invested} on symbol {position.stock.symbol}.")
                    
                        # Message.objects.create(user =user, sender='bot',room=conversation, content=message)
                        save_and_send_notification(user.id,f' DEMO: You opened position on {position.quantity} units of {position.stock.symbol} at {position.open_price} per unit. Total value:{position.quantity * position.open_price} naira ')
                        
                        marketai.position_created= True
                        marketai.save()
                        
@shared_task                  
def update_latest_cumulative_returns():
    """
    Updates the cumulative returns for the latest day for each user in the DailyReturns table
    and stores the results in the CumulativeReturns model.
    """
    today = datetime.now().weekday()
    if today < 5:
        users = User.objects.all()

        for user in users:
            latest_daily_return = DemoDailyReturns.objects.filter(user=user).order_by('-created').first()

            if latest_daily_return:
                daily_returns = DemoDailyReturns.objects.filter(user=user, created__lte=latest_daily_return.created).order_by('created')
                data = {
                    'portfolio_returns': [dr.portfolio_returns/100 for dr in daily_returns],
                    'market_returns': [dr.market_returns/100 for dr in daily_returns],
                    'ngx_price': [dr.ngx_price for dr in daily_returns],
                    'created': [dr.created for dr in daily_returns]
                }
                df = pd.DataFrame(data)

                if len(df) > 1:
                    df['portfolio_cumulative'] = (1 + df['portfolio_returns']).cumprod() - 1
                    df['market_cumulative'] = (1 + df['market_returns']).cumprod() - 1
                    portfolio_cumulative = df['portfolio_cumulative'].iloc[-1]
                    market_cumulative = df['market_cumulative'].iloc[-1]
                else:
                    portfolio_cumulative = latest_daily_return.portfolio_returns
                    market_cumulative = latest_daily_return.market_returns

                ngx_price = df['ngx_price'].iloc[-1]

                DemoCumulativeReturns.objects.create(
                    user=user,
                    created=latest_daily_return.created,
                    portfolio_returns= round(portfolio_cumulative*100,2),
                    market_returns=round(market_cumulative*100,2),
                    ngx_price=ngx_price
                    
                )
                
@shared_task                
def returns3():
    daily_returns3()
    
@shared_task                
def returns5():
    daily_returns5()
    
@shared_task                
def competition_returns3():
    competition_daily_returns3()
    
@shared_task                
def competition_returns4():
    competition_daily_returns4()



def update_document(symbol,dbase, new_data):

    
    db = mongo_client[dbase]
    if symbol not in db.list_collection_names():
        db.create_collection(symbol)
    
    collection = db[symbol]

    # Find the document to update
    existing_document = collection.find_one()

    if existing_document:
        id = existing_document['_id']
        # Update each list in the document with new values
        for key in ['t', 'o', 'h', 'l', 'c', 'v']:
            if key in new_data:
                if key in existing_document:
                    existing_document[key].extend(new_data[key])
                else:
                    existing_document[key] = new_data[key]

        # Update the document in the collection
        collection.update_one({"_id": id}, {"$set": existing_document})
    else:
        # If no existing document found, insert the new data
        print('created',new_data)
        collection.insert_one(new_data)

    # Close the MongoDB connection
    # mongo_client.close()
    
def retrieve_today_live(symbol, interval):
  
    

    lagos_tz = pytz.timezone("Africa/Lagos")
    today = datetime.now(lagos_tz).date()
    # date_string = "2024-05-20"
    # today = datetime.strptime(date_string, "%Y-%m-%d").date()

    pipeline = [
        {
            "$project": {
                "_id": 0,
                "documents": {
                    "$objectToArray": "$$ROOT"
                }
            }
        },
        {
            "$unwind": "$documents"
        },
        {
            "$match": {
                "$expr": {
                    "$eq": [
                        {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": {
                                    "$toDate": "$documents.v.datetime"
                                },
                                "timezone": "Africa/Lagos"
                            }
                        },
                        today.strftime("%Y-%m-%d")
                    ]
                },
                "documents.k": symbol  # Match documents for the given symbol only
            }
        },
        {
            "$replaceRoot": {
                "newRoot": "$documents.v"
            }
        }
    ]


    cursor = collection_merged.aggregate(pipeline)

    data = list(cursor)
    
    if data:  
        df = pd.DataFrame(data)

        df.drop(["change", "percentage_change", "current_price", "volatility", "momentum"], axis=1, inplace=True)

        df['timestamp'] = pd.to_datetime(df['datetime']).apply(lambda dt: dt.timestamp())

        df_filtered = df.sort_values(['symbol', 'timestamp'])
        df_filtered['volume_diff'] = df_filtered['volume'].diff()
        df_filtered = df_filtered[df_filtered['volume_diff'] != 0]
        # df_filtered.drop('volume_diff', axis=1, inplace=True)
        
        df_filtered.dropna(inplace=True)
        
        return df_filtered
    
        
       
@shared_task
def update_live_1m():
    lagos_tz = pytz.timezone("Africa/Lagos")
    today = datetime.now(lagos_tz).date()
    
    if today in [holiday.date() for holiday in BANK_HOLIDAYS]:
        print(f"Today {today} is a bank holiday. Skipping update_live_1m task.")
        return
    
    stocks = [stock.symbol for stock in Stock.objects.filter(active=True).order_by('symbol')]
    for symbol in stocks:
        print(symbol)
        df = retrieve_today_live(symbol,"1")
        # print('df',df)
        if df is None or df.empty:
            continue
        
        new_data = {
            "t": df["timestamp"].tolist(), 
            "o": df["open"].tolist(),  
            "h": df["high"].tolist(),  
            "l": df["low"].tolist(),  
            "c": df["close"].tolist(),  
            "v": df["volume_diff"].tolist(), 
        }


        update_document(symbol,'chartdata_5', new_data) 
        print('updated 1m', symbol)

def last_data(last_item,symbol):
    
    
    lagos_tz = pytz.timezone("Africa/Lagos")
    today = datetime.now(lagos_tz).date()
    # today = "2024-05-20"
    date_string = f"{today} 14:30"
    dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M")

    symbol_data = last_item[symbol]
    if symbol_data['high'] is not None and symbol_data['low'] is not None:
        timestamp = dt.timestamp()
        open_value = symbol_data['open']
        high_value = symbol_data['high'] 
        low_value = symbol_data['low'] 
        close_value = symbol_data['close']
        volume_value = symbol_data['volume']

        new_data = {
            "timestamp": [timestamp], 
            "open": [open_value],  
            "high": [high_value],  
            "low": [low_value],  
            "close": [close_value],  
            "volume": [volume_value], 
        }

        return pd.DataFrame(new_data)
        
        

@shared_task
def update_live_1d():
    
    lagos_tz = pytz.timezone("Africa/Lagos")
    today2 = datetime.now(lagos_tz).date()
    
    if today2 in [holiday.date() for holiday in BANK_HOLIDAYS]:
        print(f"Today {today} is a bank holiday. Skipping update_live_1d  task.")
        return
    
    stocks = [stock.symbol for stock in Stock.objects.filter(active=True).order_by('symbol')]
    today = timezone.now()
    
    
    last_item = collection_merged.find_one(sort=[('_id', -1)])
    
    for symbol in stocks:
        df = last_data(last_item, symbol)
        if df is None or df.empty:
            print(f"No data available for {symbol} today")
            continue

        t = df["timestamp"].tolist()[-1]
        o = df["open"].tolist()[-1]
        h = df["high"].tolist()[-1]
        l = df["low"].tolist()[-1] 
        c = df["close"].tolist()[-1]  
        v = df["volume"].tolist()[-1]

        new_data = {
            "t": [t], 
            "o": [o],  
            "h": [h],  
            "l": [l],  
            "c": [c],  
            "v": [v], 
        }

        print(new_data)

        # update_document(symbol, 'chartdata_5', new_data) 
        # print('updated 5m', symbol)
        update_document(symbol, 'chartdata_1D', new_data) 
        print('updated 1D', symbol)
        if today.weekday() == 0:  # Monday
            update_document(symbol, 'chartdata_1W', new_data)
            print('updated 1W', symbol)
       
        
@shared_task
def calc_take_profit():
    today = timezone.now().date()
     
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    # print(current_time_lagos)
    
    if current_time_lagos.time() >= datetime.strptime('10:02 AM', '%I:%M %p').time() and current_time_lagos.time() <= datetime.strptime('2:31 PM', '%I:%M %p').time() and current_time_lagos.weekday() < 5:
        demopositions = DemoPosition.objects.filter(status='open')
        composition = CompetitionPosition.objects.filter(status='open')
        
        positions = list(demopositions) + list(composition)
        all_prices = get_stockdata2()
        for position in positions:
            if position.take_profit and not position.trailing_stop_loss:
                symbol = position.stock.symbol
                current_price = all_prices[symbol]['current_price']
                if position.action == 'buy':
                    if current_price >= position.take_profit:
                        print('take profit triggered')
                        
                        current_value = round(position.quantity * current_price,2)
                        profit_loss = Decimal(current_value) - position.amount_invested
                        
                        position.status = DemoPosition.CLOSED
                        position.close_price = Decimal(current_price)
                        position.profit_loss = profit_loss
                        position.save()
                        
                        CompetitionTransaction.objects.create(
                                    user=position.portfolio.user,
                                    transaction_type='close trade',
                                    amount=current_value,
                                    status='completed'
                                )
                        save_and_send_notification(position.portfolio.user.id, f"Take profit has been triggered for {position.stock.symbol}. Position is closed")
                        UserActivityLog.objects.create(user=position.portfolio.user, action_type="demo_closed_trade",description=f"User closed demo trade with symbol {position.stock.symbol}.")
                        position.portfolio.balance += position.amount_invested + position.profit_loss
                        position.portfolio.save()
                        
                elif position.action == 'sell':
                    if current_price <= position.take_profit:
                        current_value = round(position.quantity * current_price,2)
                        
                        profit_loss = position.amount_invested - Decimal(current_value)
                        
                        position.status = DemoPosition.CLOSED
                        position.close_price = Decimal(current_price)
                        position.profit_loss = profit_loss
                        position.save()
                        
                        CompetitionTransaction.objects.create(
                                    user=position.portfolio.user,
                                    transaction_type='close trade',
                                    amount=current_value,
                                    status='completed'
                                )
                        save_and_send_notification(position.portfolio.user.id, f"Take profit has been triggered for {position.stock.symbol}. Position is closed")
                        UserActivityLog.objects.create(user=position.portfolio.user, action_type="demo_closed_trade",description=f"User closed demo trade with symbol {position.stock.symbol}.")
                        position.portfolio.balance += position.amount_invested + position.profit_loss
                        position.portfolio.save()
                        
@shared_task
def calc_stop_loss():
    today = timezone.now().date()
     
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    # print(current_time_lagos)
    
    if current_time_lagos.time() >= datetime.strptime('10:02 AM', '%I:%M %p').time() and current_time_lagos.time() <= datetime.strptime('2:31 PM', '%I:%M %p').time() and current_time_lagos.weekday() < 5:
        demopositions = DemoPosition.objects.filter(status='open')
        composition = CompetitionPosition.objects.filter(status='open')
        
        positions = list(demopositions) + list(composition)
        all_prices = get_stockdata2()
        for position in positions:
            if position.stop_loss and not position.trailing_stop_loss:
                symbol = position.stock.symbol
                current_price = all_prices[symbol]['current_price']
                if position.action == 'buy':
                    if current_price <= position.stop_loss:
                        # print('stop loss triggered')
                        current_value = round(position.quantity * current_price,2)
                        profit_loss = Decimal(current_value) - position.amount_invested
                        
                        position.status = DemoPosition.CLOSED
                        position.close_price = Decimal(current_price)
                        position.profit_loss = profit_loss
                        position.save()
                        
                        CompetitionTransaction.objects.create(
                                    user=position.portfolio.user,
                                    transaction_type='close trade',
                                    amount=current_value,
                                    status='completed'
                                )
                        save_and_send_notification(position.portfolio.user.id, f"Stop loss has been triggered for {position.stock.symbol}. Position is closed")
                        UserActivityLog.objects.create(user=position.portfolio.user, action_type="demo_closed_trade",description=f"User closed demo trade with symbol {position.stock.symbol}.")
                        position.portfolio.balance += position.amount_invested + position.profit_loss
                        position.portfolio.save()
                        
                elif position.action == 'sell':
                    if current_price >= position.stop_loss:
                        current_value = round(position.quantity * current_price,2)
                        
                        profit_loss = position.amount_invested - Decimal(current_value)
                        
                        position.status = DemoPosition.CLOSED
                        position.close_price = Decimal(current_price)
                        position.profit_loss = profit_loss
                        position.save()
                        
                        CompetitionTransaction.objects.create(
                                    user=position.portfolio.user,
                                    transaction_type='close trade',
                                    amount=current_value,
                                    status='completed'
                                )
                        save_and_send_notification(position.portfolio.user.id, f"Stop loss has been triggered for {position.stock.symbol}. Position is closed")
                        UserActivityLog.objects.create(user=position.portfolio.user, action_type="demo_closed_trade",description=f"User closed demo trade with symbol {position.stock.symbol}.")
                        position.portfolio.balance += position.amount_invested + position.profit_loss
                        position.portfolio.save()
                        

@shared_task
def calc_tailing_sl():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    
    if (current_time_lagos.time() >= datetime.strptime('10:02 AM', '%I:%M %p').time() and 
        current_time_lagos.time() <= datetime.strptime('2:31 PM', '%I:%M %p').time() and 
        current_time_lagos.weekday() < 5):
        
        demopositions = DemoPosition.objects.filter(status='open')
        composition = CompetitionPosition.objects.filter(status='open')
        positions = list(demopositions) + list(composition)
        all_prices = get_stockdata2()

        for position in positions:
            if not position.trailing_stop_loss:
                continue

            symbol = position.stock.symbol
            current_price = all_prices[symbol]['current_price']

            if position.action == 'buy':
                if handle_buy_position(position, current_price):
                    continue  # Skip to the next position if the current one is closed
            elif position.action == 'sell':
                if handle_sell_position(position, current_price):
                    continue  # Skip to the next position if the current one is closed

            # Update last highest price for the next comparison
            position.last_price = max(position.last_price, current_price)
            position.save()

def handle_buy_position(position, current_price):
    if position.last_price and position.last_price > 0:
        # Calculate trailing stop loss threshold based on a fixed price difference
        trailing_stop_threshold = position.last_price - position.trailing_stop_loss
        if current_price <= trailing_stop_threshold:
            close_position(position, current_price)
            return True  # Indicate that the position was closed
    return False

def handle_sell_position(position, current_price):
    if position.last_price and position.last_price > 0:
        # Calculate trailing stop loss threshold based on a fixed price difference
        trailing_stop_threshold = position.last_price + position.trailing_stop_loss
        if current_price >= trailing_stop_threshold:
            close_position(position, current_price)
            return True  # Indicate that the position was closed
    return False

def close_position(position, current_price):
    current_value = round(position.quantity * current_price, 2)
    profit_loss = Decimal(current_value) - position.amount_invested

    # Update position status and details
    position.status = DemoPosition.CLOSED
    position.close_price = Decimal(current_price)
    position.profit_loss = profit_loss
    position.save()

    # Log transaction and notify user
    CompetitionTransaction.objects.create(
        user=position.portfolio.user,
        transaction_type='close trade',
        amount=current_value,
        status='completed'
    )
    save_and_send_notification(
        position.portfolio.user.id,
        f"Trailing stop loss has been triggered for {position.stock.symbol}. Position is closed"
    )
    UserActivityLog.objects.create(
        user=position.portfolio.user,
        action_type="demo_closed_trade",
        description=f"User closed demo trade with symbol {position.stock.symbol}."
    )

    # Update portfolio balance
    position.portfolio.balance += position.amount_invested + position.profit_loss
    position.portfolio.save()

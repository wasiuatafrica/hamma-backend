from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.management import call_command
from django.shortcuts import get_object_or_404

from execution.utils import get_positions, daily_returns3, competition_daily_returns3
from .serializers import DemoPositionSerializer
from anyon.views import User
from portfolio.models import Message, Conversation, Stock, MarketAI,DemoTransaction
from .models import   DemoPortfolio,DemoPosition, DemoDailyReturns, DemoCumulativeReturns
from random import uniform
from django.db import transaction
from time import sleep
from decimal import Decimal
from datetime import datetime, timedelta,time
from portfolio.utils import get_price
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

logger = get_task_logger(__name__)
channel_layer = get_channel_layer()



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
def competition_returns3():
    competition_daily_returns3()
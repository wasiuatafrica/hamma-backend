from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.management import call_command
from django.shortcuts import get_object_or_404
from anyon.views import User
from portfolio.models import  DemoTransaction, DemoTrade, DemoPortfolio
from random import uniform
from django.db import transaction
from time import sleep
from decimal import Decimal
from datetime import datetime, timedelta
from .models import DemoPosition, DemoDailyReturns
from portfolio.utils import get_price
from notifications.utils import save_and_send_notification
from django_celery_beat.models import PeriodicTask
from django.utils import timezone
from datetime import datetime, time
import pytz

logger = get_task_logger(__name__)
channel_layer = get_channel_layer()


@shared_task
def process_trade(trade_id, time_in_force):
    try:
        trade = DemoTrade.objects.get(id=trade_id)
        with transaction.atomic():
            handle_trade(trade, time_in_force)
    except DemoTrade.DoesNotExist:
        pass

def handle_trade(trade, time_in_force):
    try:
        user = trade.user
        holding = trade.holding
        stock = holding.stock
        quantity = trade.quantity
        price = trade.price
        order_type = trade.order_type
        position, created = DemoPosition.objects.get_or_create(
            portfolio=holding.portfolio,
            stock=stock,
            defaults={'quantity': 0, 'average_price': 0.0}
        )
        print('Position created')
        if order_type == 'buy':
            position.quantity += quantity
            position.average_price = ((position.average_price * position.quantity) + (price * quantity)) / (position.quantity + quantity)
        elif order_type == 'sell':
            # Ensure the quantity doesn't go below zero
            if position.quantity < quantity:
                raise ValueError("Attempt to sell more shares than available.")
            position.quantity -= quantity

        position.save()

        # print('position saved')
        # Simulate market fluctuations
        # price = simulate_price_fluctuation(stock.symbol, price)

        # Simulate trade settlement delay
        simulate_trade_settlement_delay(time_in_force)

        holding.portfolio.update_equity()

        # print('Demo to be created')
        DemoTransaction.objects.create(
            user=user,
            transaction_type='buy' if order_type == 'buy' else 'sell',
            amount=quantity * price,
            status='completed'
        )
        trade.status = 'completed'
        trade.save()

        print('trade completed')
        # Simulate partial order filling
        if order_type == 'buy':
            cancel_pending_opposite_order(trade)

        # Simulate price matching for limit orders
        if order_type == 'sell':
            matching_buy_orders = DemoTrade.objects.filter(
                holding=trade.holding,
                order_type='buy',
                price__gte=price,
                status='pending'
            ).order_by('price')

            for matching_order in matching_buy_orders:
                if quantity == 0:
                    break
                if matching_order.quantity <= quantity:
                    quantity -= matching_order.quantity
                    matching_order.status = 'completed'
                else:
                    matching_order.quantity -= quantity
                    break
                matching_order.save()
        update_equity(user.id, 'demo')
        
    except Exception as e:
        print(f"Error processing trade (id={trade.id}): {e}")
        trade.status = 'failed'
        trade.save()

# Simulate market fluctuations by adding random fluctuations
def simulate_price_fluctuation(symbol, current_price):
    # Add some random fluctuation
    fluctuation = uniform(-1, 1) * Decimal(0.05) * current_price  # 5% fluctuation
    return round(current_price + fluctuation, 2)

# Simulate trade settlement delay
def simulate_trade_settlement_delay(time_in_force):
    if time_in_force != 'GTC':
        # Simulate settlement delay, adjust delay as needed
        sleep(20)  # Assuming a 2-second settlement delay


def cancel_pending_opposite_order(trade):
    opposite_order_type = 'sell' if trade.order_type == 'buy' else 'buy'
    opposite_order = DemoTrade.objects.filter(
        user=trade.user,
        holding=trade.holding,
        order_type=opposite_order_type,
        status='pending'
    ).first()

    if opposite_order:
        # Cancel the pending opposite order
        opposite_order.status = 'canceled'
        opposite_order.save()

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
def process_limit_order(id):
    position = get_object_or_404(DemoPosition, id=id)
    
    if position.status == 'open':
    
        if position.time_in_force== 'day':
            lagos_timezone = pytz.timezone('Africa/Lagos')
            current_time_lagos = timezone.now().astimezone(lagos_timezone).time()

            target_time = time(14, 30)  # 14 is the hour, 30 is the minute

            # Check if the current time is before 2:30 PM
            if current_time_lagos > target_time:
                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()
                
                position.status= 'cancelled'
                position.save()
                
                save_and_send_notification(user.id,f'DEMO: Your pending order has been cancelled because the position cannot be filled before close of trade session.')
                
                
        elif position.time_in_force== 'week':
            lagos_timezone = pytz.timezone('Africa/Lagos')
            current_time_lagos = timezone.now().astimezone(lagos_timezone).time()

            target_time = time(14, 30)  # 14 is the hour, 30 is the minute

            # Check if the current time is before 2:30 PM
            if timezone.now().astimezone(lagos_timezone).weekday() == 4 and current_time_lagos > target_time:
                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()
                
                position.status= 'cancelled'
                position.save()
                
                save_and_send_notification(user.id,f'DEMO: Your pending order has been cancelled because the position cannot be filled before close of trade session.')
                
        else:
            user = position.portfolio.user
            data =get_price(position.stock.symbol)
            price=data['current_price']
            if position.action == 'buy':
                if price <= position.limit_price:
                    position.status= 'open'
                    position.amount_invested = Decimal(price) * position.quantity
                    position.save()
                
                    DemoTransaction.objects.create(
                            user=user,
                            transaction_type='open trade',
                            amount=position.amount_invested,
                            status='completed'
                        )
                    save_and_send_notification(user.id,f' DEMO: You opened position {position.quantity} units of {position.stock.symbol} at {price} per unit. Total value:{position.amount_invested}naira ')

            elif position.action == 'sell':
                if price >= position.limit_price:
                    position.status= 'open'
                    position.amount_invested = Decimal(price) * position.quantity
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
        
# @shared_task
# def get_daily_profit_loss():
#     today = datetime.now().weekday()
#     if today < 5:
#         users = User.objects.all()
#         for user in users:
#             positions = DemoPosition.objects.filter(portfolio__user=user,status='open')
#             total = 0.0
#             for position in positions:
#                 pl,value,price = position.calculate_profit_loss() 
#                 total += float(pl)
                
#             DemoProfitLoss.objects.create(user=user, profit_loss=total)
#             print(f"{user.email} daily profit/loss calculated")
#     else:
#         print("Not running on weekends.")

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
    today = datetime.now().weekday()
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
                    pl,value,price = position.calculate_profit_loss() 
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
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.management import call_command
from anyon.views import User
from portfolio.models import DemoPosition, DemoTransaction, DemoTrade, DemoPortfolio
from random import uniform
from django.db import transaction
from time import sleep
from decimal import Decimal
from datetime import datetime, timedelta

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
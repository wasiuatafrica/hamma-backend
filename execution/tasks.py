from celery import shared_task
from celery.utils.log import get_task_logger

from django.core.management import call_command

logger = get_task_logger(__name__)


from portfolio.models import DemoPosition, DemoTransaction, DemoTrade

@shared_task
def process_trade(trade_id, time_in_force):
    try:
        trade = DemoTrade.objects.get(id=trade_id,)
        
        # Call the function to handle trade processing (create positions, update equity, etc.)
        handle_trade(trade,time_in_force)

    except DemoTrade.DoesNotExist:
        # Handle the case where the trade does not exist
        pass


def handle_trade(trade, time_in_force):
    try:
        user = trade.user
        holding = trade.holding
        stock = holding.stock
        quantity = trade.quantity
        price = trade.price
        order_type = trade.order_type

        # Generate position
        position, created = DemoPosition.objects.get_or_create(
            portfolio=holding.portfolio,
            stock=stock,
            defaults={'quantity': 0, 'average_price': 0.0}
        )

        # Update position based on order type
        if order_type == 'buy':
            position.quantity += quantity
            position.average_price = ((position.average_price * position.quantity) + (price * quantity)) / (position.quantity + quantity)
        elif order_type == 'sell':
            position.quantity -= quantity

        # Save the updated position
        position.save()

        # Update equity in the portfolio
        # holding.portfolio.update_equity()

        
        # Record the transaction
        DemoTransaction.objects.create(
            user=user,
            transaction_type='buy' if order_type == 'buy' else 'sell',
            amount=quantity * price
        )

        # Set trade status to 'completed'
        trade.status = 'completed'
        trade.save()

        # Handle time in force
        if time_in_force == 'IOC' and trade.status == 'completed':
            # If Immediate or Cancel (IOC) and trade is completed, cancel any pending opposite order
            cancel_pending_opposite_order(trade)

    except Exception as e:
        # Handle exceptions appropriately (logging, notifying administrators, etc.)
        print(f"Error processing trade (id={trade.id}): {e}")
        # Set trade status to 'failed'
        trade.status = 'failed'
        trade.save()

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

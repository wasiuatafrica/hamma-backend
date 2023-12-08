import random
from portfolio.models import Stock, Trade, Wallet, Holding, Portfolio, Transaction
from notifications.utils import save_and_send_notification
from decimal import Decimal

def simulate_trades(user):
    stocks = Stock.objects.all()
    
    wallet = Wallet.objects.get(user=user)
    wallet.balance += Decimal(500000)
    wallet.save()
    Transaction.objects.create(user=user, transaction_type='deposit', amount=Decimal(500000))
    
    portfolio = Portfolio.objects.get(user=user)

    for _ in range(10):
        # Simulate Buy
        quantity = random.randint(1, 150)
        price = Decimal(round(random.uniform(100, 500), 2))
        stock = random.choice(stocks)
        holding = Holding.objects.get_or_create(portfolio=portfolio, stock=stock)[0]

        if wallet.balance >= quantity * price:
            Trade.objects.create(
                user=user,
                holding=holding,
                quantity=quantity,
                price=price,
                order_type='buy',
                status='completed'
            )

            holding.quantity += quantity
            holding.save()

            wallet.balance -= quantity * price
            wallet.save()

            Transaction.objects.create(user=user, transaction_type='buy', amount=quantity * price)
            save_and_send_notification(user.id,f'You bought {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
            
    print('buy simulated')
    for _ in range(10):
        # Simulate Sell
        quantity = random.randint(1, 50)
        price = Decimal(round(random.uniform(100, 500), 2))
        stock = random.choice(stocks)

        holding = Holding.objects.get_or_create(portfolio=portfolio, stock=stock)[0]

        if holding.quantity >= quantity:
            Trade.objects.create(
                user=user,
                holding=holding,
                quantity=quantity,
                price=price,
                status='completed',
                order_type='sell',
            )

            holding.quantity -= quantity
            holding.save()

            wallet.balance += quantity * price
            wallet.save()

            Transaction.objects.create(user=user, transaction_type='sell', amount=quantity * price)
            save_and_send_notification(user.id,f'You sold {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
            

    print('sell simulated')

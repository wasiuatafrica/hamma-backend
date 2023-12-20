import random
from portfolio.models import Stock, Trade, Wallet, Holding, Portfolio, Transaction
from notifications.utils import save_and_send_notification
from decimal import Decimal
from accounts.models import Referral
from portfolio.models import Transaction
from affilate.models import ReferralWallet,RewardActivities


def simulate_trades(user):
    stocks = Stock.objects.all()
    
    wallet = Wallet.objects.get(user=user)
    wallet.balance += Decimal(500000)
    wallet.save()
    Transaction.objects.create(user=user, transaction_type='deposit', amount=Decimal(500000))
    
    refer_object=Referral.objects.filter(person_referred=wallet.user).first()
    
    if refer_object and refer_object.converted == False:
        sum_user_trans=sum(trans.amount for trans in Transaction.objects.filter(user=wallet.user, transaction_type = 'deposit'))
        if sum_user_trans >= 50000 :
            referal_wallet = ReferralWallet.objects.get_or_create(user=refer_object.user)[0]
            referal_wallet.balance += Decimal(5000)
            referal_wallet.save()
            
            refer_object.converted == True
            refer_object.save()
            
            
            RewardActivities.objects.create(trader=wallet.user, amount=5000, reward_type="Deposit Referral Commission", user=refer_object.user)
    
    portfolio = Portfolio.objects.get(user=user)

    for _ in range(20):
        # Simulate Buy
        quantity = random.randint(1, 150)
        price = round(Decimal(random.uniform(100, 500)),2)
        
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
            save_and_send_notification(user.id,f'You bought {quantity} units of {stock.symbol} stocks at {price} per unit. Total value:{round(quantity * price, 2)}naira ')
            
    print('buy simulated')
    for _ in range(20):
        # Simulate Sell
        quantity = random.randint(1, 50)
        price = round(Decimal(random.uniform(100, 500)),2)
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
            save_and_send_notification(user.id,f'You sold {quantity} units of {stock.symbol} stocks at {price} per unit. Total value:{round(quantity * price, 2)}naira ')
            

    print('sell simulated')
    holding2 = Holding.objects.filter(portfolio=portfolio,quantity=0)
    if holding2:
        for hol in holding2:
            hol.delete()

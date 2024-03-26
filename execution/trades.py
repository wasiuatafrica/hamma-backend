# import random
# from portfolio.models import Stock, Transaction, Wallet
# from .models import  DemoHolding, DemoPortfolio,  Holding, Portfolio
# from notifications.utils import save_and_send_notification
# from decimal import Decimal
# from accounts.models import Referral
# from affilate.models import ReferralWallet,RewardActivities,BrokageCommission

# from django.shortcuts import get_object_or_404
# from accounts.utils import get_referrer


def simulate_trades(user):
    pass
#     stocks = Stock.objects.all()
#     portfolio = DemoPortfolio.objects.get_or_create(user=user)[0]
    
    

#     for _ in range(3):
#         # Simulate Buy
#         quantity = random.randint(1, 150)
#         price = round(Decimal(random.uniform(0, 100)),2)
        
#         stock = random.choice(stocks)
#         holding = DemoHolding.objects.get_or_create(portfolio=portfolio, stock=stock)[0]
        
#         trade_amount= quantity * price
#         # master_commission = round(Decimal(0.01) * trade_amount,2)
#         # brokerage_commission = round(Decimal(0.1) * master_commission,2)

#         # if wallet.balance >= quantity * price:
#         trade = DemoTrade.objects.create(
#             user=user,
#             holding=holding,
#             quantity=quantity,
#             price=price,
#             order_type='buy',
#             status='completed'
#         )

#         holding.quantity += quantity
#         holding.save()

           
#     print('buy simulated')
#     for _ in range(3):
#         # Simulate Sell
#         quantity = random.randint(1, 50)
#         price = round(Decimal(random.uniform(100, 500)),2)
#         stock = random.choice(stocks)

#         holding = DemoHolding.objects.get_or_create(portfolio=portfolio, stock=stock)[0]
        
#         trade_amount= quantity * price
#         # master_commission = round(Decimal(0.01) * trade_amount,2)
#         # brokerage_commission = round(Decimal(0.1) * master_commission,2)

#         if holding.quantity >= quantity:
#             DemoTrade.objects.create(
#                 user=user,
#                 holding=holding,
#                 quantity=quantity,
#                 price=price,
#                 status='completed',
#                 order_type='sell',
#             )

#             holding.quantity -= quantity
#             holding.save()

#             # wallet.balance += quantity * price
#             # wallet.save()

#             # Transaction.objects.create(user=user, transaction_type='sell', amount=quantity * price)
#             # save_and_send_notification(user.id,f'You sold {quantity} units of {stock.symbol} stocks at {price} per unit. Total value:{round(quantity * price, 2)}naira ')
            
#             # referrer = get_referrer(user)
#             # if referrer:
#             #     BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade,person_referred=user)
#             #     RewardActivities.objects.create(user=referrer, trader=user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
#             #     ref_wallet = get_object_or_404(ReferralWallet, user=referrer)
#             #     ref_wallet.balance += round(Decimal(brokerage_commission),2)
#             #     ref_wallet.save()
                
#             #     save_and_send_notification(referrer.id, f"Your {brokerage_commission} as brokerage commsion")

#     print('sell simulated')
#     holding2 = DemoHolding.objects.filter(portfolio=portfolio,quantity=0)
#     if holding2:
#         for hol in holding2:
#             hol.delete()


# def simulate_trades2(user):
#     stocks = Stock.objects.all()
#     portfolio = Portfolio.objects.get_or_create(user=user)[0]
    
#     wallet = Wallet.objects.get(user=user)
#     wallet.balance += Decimal(500000)
#     wallet.save()
#     Transaction.objects.create(user=user, transaction_type='deposit', amount=Decimal(500000))
    
#     refer_object=Referral.objects.filter(person_referred=wallet.user).first()
    
#     if refer_object and refer_object.converted == False:
#         sum_user_trans=sum(trans.amount for trans in Transaction.objects.filter(user=wallet.user, transaction_type = 'deposit'))
#         if sum_user_trans >= 50000 :
#             referal_wallet = ReferralWallet.objects.get_or_create(user=refer_object.user)[0]
#             referal_wallet.balance += Decimal(5000)
#             referal_wallet.save()
            
#             refer_object.converted == True
#             refer_object.save()
            
            
#             RewardActivities.objects.create(trader=wallet.user, amount=5000, reward_type="Deposit Referral Commission", user=refer_object.user)
    

#     for _ in range(10):
#         # Simulate Buy
#         quantity = random.randint(1, 150)
#         price = round(Decimal(random.uniform(0, 100)),2)
        
#         stock = random.choice(stocks)
#         holding = Holding.objects.get_or_create(portfolio=portfolio, stock=stock)[0]
        
#         trade_amount= quantity * price
#         master_commission = round(Decimal(0.01) * trade_amount,2)
#         brokerage_commission = round(Decimal(0.1) * master_commission,2)

#         # if wallet.balance >= quantity * price:
#         trade = Trade.objects.create(
#             user=user,
#             holding=holding,
#             quantity=quantity,
#             price=price,
#             order_type='buy',
#             status='completed'
#         )

#         holding.quantity += quantity
#         holding.save()

#         wallet.balance -= quantity * price
#         wallet.save()

#         Transaction.objects.create(user=user, transaction_type='buy', amount=quantity * price)
#         # save_and_send_notification(user.id,f'You bought {quantity} units of {stock.symbol} stocks at {price} per unit. Total value:{round(quantity * price, 2)}naira ')
        
#         referrer = get_referrer(user)
#         if referrer:
#             BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade,person_refferred=user)
#             RewardActivities.objects.create(user=referrer, trader=user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
#             ref_wallet = get_object_or_404(ReferralWallet, user=referrer)
#             ref_wallet.balance += round(Decimal(brokerage_commission),2)
#             ref_wallet.save()
            
#             #     save_and_send_notification(referrer.id, f"Your {brokerage_commission} as brokerage commsion")
#     print('buy simulated')
#     for _ in range(5):
#         # Simulate Sell
#         quantity = random.randint(1, 50)
#         price = round(Decimal(random.uniform(100, 500)),2)
#         stock = random.choice(stocks)

#         holding = Holding.objects.get_or_create(portfolio=portfolio, stock=stock)[0]
        
#         trade_amount= quantity * price
#         master_commission = round(Decimal(0.01) * trade_amount,2)
#         brokerage_commission = round(Decimal(0.1) * master_commission,2)

#         if holding.quantity >= quantity:
#             Trade.objects.create(
#                 user=user,
#                 holding=holding,
#                 quantity=quantity,
#                 price=price,
#                 status='completed',
#                 order_type='sell',
#             )

#             holding.quantity -= quantity
#             holding.save()

#             wallet.balance += quantity * price
#             wallet.save()

#             Transaction.objects.create(user=user, transaction_type='sell', amount=quantity * price)
#             # save_and_send_notification(user.id,f'You sold {quantity} units of {stock.symbol} stocks at {price} per unit. Total value:{round(quantity * price, 2)}naira ')
            
#             referrer = get_referrer(user)
#             if referrer:
#                 BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade,person_refferred=user)
#                 RewardActivities.objects.create(user=referrer, trader=user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
#                 ref_wallet = get_object_or_404(ReferralWallet, user=referrer)
#                 ref_wallet.balance += round(Decimal(brokerage_commission),2)
#                 ref_wallet.save()
                
#             #     save_and_send_notification(referrer.id, f"Your {brokerage_commission} as brokerage commsion")

#     print('sell simulated')
#     holding2 = Holding.objects.filter(portfolio=portfolio,quantity=0)
#     if holding2:
#         for hol in holding2:
#             hol.delete()

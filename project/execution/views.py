from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from portfolio.models import Stock, Trade, Wallet, Holding, Portfolio, Transaction
from notifications.utils import save_and_send_notification
from rest_framework.permissions import IsAuthenticated
from accounts.utils import get_referrer
from affilate.models import BrokageCommission,RewardActivities


class TradeAPIView(APIView):
    permission_classes = [IsAuthenticated]


    def post(self, request):
        symbol = request.data.get('symbol')
        quantity = int(request.data.get('quantity'))
        price = float(request.data.get('price'))
        is_buy = request.data.get('action') == 'buy'

        stock = get_object_or_404(Stock, symbol=symbol)
        wallet = get_object_or_404(Wallet, user=request.user)
        portfolio= get_object_or_404(Portfolio, user=request.user)
        
        trade_amount= quantity * price
        brokerage_commission = 0.1 * trade_amount
        
        if is_buy and wallet.balance >= trade_amount:
            holding = Holding.objects.get_or_create(
                portfolio=portfolio,
                stock=stock,
            )[0]
            trade = Trade.objects.create(
                user=request.user,
                holding=holding,
                quantity=quantity,
                price=price,
                order_type='buy',
                status='completed',
            )
                        
            holding.quantity +=quantity
            holding.save()
            
            wallet.balance -= quantity * price
            wallet.save()
            
            Transaction.objects.create(user=request.user,transaction_type='buy',amount=quantity * price)
            save_and_send_notification(request.user.id,f'You bought {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
            
            referrer = get_referrer(request.user)
            if referrer:
                BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade)
                RewardActivities.objects.create(user=referrer, trader=request.user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
            
            return Response({'message': 'Buy order executed successfully.'}, status=status.HTTP_201_CREATED)
        elif not is_buy:
            holding = Holding.objects.get(
                portfolio=portfolio,
                stock=stock,
            )

            if holding.quantity >= quantity:
                trade = Trade.objects.create(
                    user=request.user,
                    holding=holding,
                    quantity=quantity,
                    price=price,
                    order_type='sell',
                    status='completed',
                )
                holding.quantity -= quantity
                holding.save()
                
                wallet.balance += quantity * price
                wallet.save()
                
                Transaction.objects.create(user=request.user,transaction_type='sell',amount=quantity * price)
                save_and_send_notification(request.user.id,f'You sold {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
                
                referrer = get_referrer(request.user)
                if referrer:
                    BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade)
                    RewardActivities.objects.create(user=referrer, trader=request.user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
                
                return Response({'message': 'Sell order executed successfully.'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'error': 'Not enough stocks to sell.'}, status=status.HTTP_400_BAD_REQUEST)

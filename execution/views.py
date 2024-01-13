from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from portfolio.models import Stock, DemoTrade, Wallet, DemoHolding, DemoPortfolio, DemoTransaction, DemoPosition
from notifications.utils import save_and_send_notification
from rest_framework.permissions import IsAuthenticated
from accounts.utils import get_referrer
from affilate.models import BrokageCommission,RewardActivities, ReferralWallet
from decimal import Decimal
from .tasks import process_trade, update_equity
from portfolio.utils import get_price

# class DemoTradeAPIView(APIView):
#     permission_classes = [IsAuthenticated]


#     def post(self, request):
#         symbol = request.data.get('symbol')
#         quantity = int(request.data.get('quantity'))
#         price = float(request.data.get('price'))
#         is_buy = request.data.get('action') == 'buy'

#         stock = get_object_or_404(Stock, symbol=symbol)
#         wallet = get_object_or_404(Wallet, user=request.user)
#         portfolio= get_object_or_404(Portfolio, user=request.user)
        
#         trade_amount= quantity * price
#         master_commission = round(Decimal(0.01) * trade_amount, 2)
#         brokerage_commission = round(Decimal(0.1) * master_commission,2)
        
#         if is_buy:
            
#             if wallet.balance >= trade_amount + master_commission:
#                 holding = Holding.objects.get_or_create(
#                     portfolio=portfolio,
#                     stock=stock,
#                 )[0]
#                 trade = DemoTrade.objects.create(
#                     user=request.user,
#                     holding=holding,
#                     quantity=quantity,
#                     price=price,
#                     order_type='buy',
#                     status='completed',
#                 )
                            
#                 holding.quantity +=quantity
#                 holding.save()
                
#                 wallet.balance -= quantity * price
#                 wallet.save()
                
#                 Transaction.objects.create(user=request.user,transaction_type='buy',amount=quantity * price)
#                 save_and_send_notification(request.user.id,f'You bought {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
                
#                 referrer = get_referrer(request.user)
#                 if referrer:
#                     BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade, person_referred=request.user)
#                     RewardActivities.objects.create(user=referrer, trader=request.user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
#                     ref_wallet = get_object_or_404(ReferralWallet, user=referrer)
#                     ref_wallet.balance += round(Decimal(brokerage_commission),2)
#                     ref_wallet.save()
                    
#                     save_and_send_notification(referrer.id, f"Your {brokerage_commission} as brokerage commsion")
                    
                
#                 return Response({'message': 'Buy order executed successfully.'}, status=status.HTTP_201_CREATED)
#             else:
#                 return Response({'error': 'Insufficient funds to buy stocks.'}, status=status.HTTP_400_BAD_REQUEST)
#         elif not is_buy:
#             holding = Holding.objects.get(
#                 portfolio=portfolio,
#                 stock=stock,
#             )

#             if holding.quantity >= quantity:
#                 trade = DemoTrade.objects.create(
#                     user=request.user,
#                     holding=holding,
#                     quantity=quantity,
#                     price=price,
#                     order_type='sell',
#                     status='completed',
#                 )
#                 holding.quantity -= quantity
#                 holding.save()
                
#                 wallet.balance += quantity * price
#                 wallet.save()
                
#                 Transaction.objects.create(user=request.user,transaction_type='sell',amount=quantity * price)
#                 save_and_send_notification(request.user.id,f'You sold {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
                
#                 referrer = get_referrer(request.user)
#                 if referrer:
#                     BrokageCommission.objects.create(user=referrer, commission= brokerage_commission, trade = trade,person_referred=request.user)
#                     RewardActivities.objects.create(user=referrer, trader=request.user, reward_type = '10% Brokerage Commission', amount=brokerage_commission, status='completed')
#                     ref_wallet = get_object_or_404(ReferralWallet, user=referrer)
#                     ref_wallet.balance += round(Decimal(brokerage_commission),2)
#                     ref_wallet.save()
                    
#                     save_and_send_notification(referrer.id, f"Your {brokerage_commission} as brokerage commsion")
                    
                
#                 return Response({'message': 'Sell order executed successfully.'}, status=status.HTTP_201_CREATED)
#             else:
#                 return Response({'error': 'Not enough stocks to sell.'}, status=status.HTTP_400_BAD_REQUEST)


class DemoTradeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        mode = self.kwargs.get('mode')
        
        symbol = request.data.get('symbol')
        quantity = int(request.data.get('quantity'))
        if request.data.get('price'):
            price = float(request.data.get('price'))
        action = request.data.get('action')
        time_in_force = request.data.get('time_in_force', 'GTC')  # Default to Good 'Til Canceled
        is_buy = action == 'buy'
        order_type = request.data.get('order_type')
        
        stock = get_object_or_404(Stock, symbol=symbol)
        
        if mode == 'demo':
            portfolio = get_object_or_404(DemoPortfolio, user=request.user)


            if order_type == 'market':
                market_price = round(Decimal(get_price(symbol)['current_price']), 2)

                holding, created1 = DemoHolding.objects.get_or_create(
                    portfolio=portfolio,
                    stock=stock,
                )

                position, created = DemoPosition.objects.get_or_create(
                    portfolio=holding.portfolio,
                    stock=stock,
                    state=DemoPosition.OPEN,  # Only consider open positions
                    defaults={'quantity': 0, 'average_price': 0.0}
                )

                if is_buy:
                    holding.quantity += quantity
                    position.quantity += quantity
                    if not created:
                        position.average_price = (
                            (position.average_price * position.quantity) + (market_price * quantity)
                        ) / (position.quantity + quantity)
                    trade_order_type = 'buy'
                else:
                    if not created1 and holding.quantity < quantity:
                        return Response("You don't have enough stocks to sell.")

                    position.quantity -= quantity
                    trade_order_type = 'sell'

                    # If selling all stocks, close the position
                    if position.quantity == 0:
                        position.close_position()

                holding.save()
                position.save()

                trade = DemoTrade.objects.create(
                    user=request.user,
                    holding=holding,
                    quantity=quantity,
                    price=market_price,
                    order_type=trade_order_type,
                    status='completed',
                )

                # Update equity in the portfolio
                # holding.portfolio.update_equity()


                # Record the transaction
                DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type='buy' if order_type == 'buy' else 'sell',
                    amount=quantity * market_price,
                    status='completed'
                )
                

                # Set trade status to 'completed'
                trade.status = 'completed'
                trade.save()
                
                update_equity.delay(request.user.id, 'demo')
                
                return Response({'message': f'{action.title()} order placed successfully.'}, status=status.HTTP_201_CREATED)

            elif order_type == 'limit':
            
                if is_buy:
                    # Check if it's a market order or limit order
                    if time_in_force == 'GTC':
                        # Good 'Til Canceled order
                        holding = DemoHolding.objects.get_or_create(
                            portfolio=portfolio,
                            stock=stock,
                        )[0]
                        
                        holding.quantity = quantity
                        holding.save()
                
                        trade = DemoTrade.objects.create(
                            user=request.user,
                            holding=holding,
                            quantity=quantity,
                            price=price,
                            order_type='buy',
                            status='pending',  # Set status to pending for background processing
                        )

                        # Asynchronously process the trade in the background
                        process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

                        return Response({'message': 'Buy order placed successfully.'}, status=status.HTTP_201_CREATED)
                        # else:
                        #     return Response({'error': 'Insufficient funds to buy stocks.'}, status=status.HTTP_400_BAD_REQUEST)
                    elif time_in_force == 'IOC':
                        # Immediate or Cancel order (Not supported for buy orders)
                        return Response({'error': 'Immediate or Cancel (IOC) not supported for buy orders.'}, status=status.HTTP_400_BAD_REQUEST)
                    elif time_in_force == 'FOK':
                        # Fill or Kill order (Not supported for buy orders)
                        return Response({'error': 'Fill or Kill (FOK) not supported for buy orders.'}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'error': 'Invalid time in force.'}, status=status.HTTP_400_BAD_REQUEST)

                elif not is_buy:
                    holding = DemoHolding.objects.get(
                        portfolio=portfolio,
                        stock=stock,
                    )

                    # Check if it's a market order or limit order
                    if time_in_force == 'GTC':
                        # Good 'Til Canceled order
                        if holding.quantity >= quantity:
                            trade = DemoTrade.objects.create(
                                user=request.user,
                                holding=holding,
                                quantity=quantity,
                                price=price,
                                order_type='sell',
                                status='pending',  # Set status to pending for background processing
                            )

                            # Asynchronously process the trade in the background
                            process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

                            return Response({'message': 'Sell order placed successfully.'}, status=status.HTTP_201_CREATED)
                        else:
                            return Response({'error': 'Not enough stocks to sell.'}, status=status.HTTP_400_BAD_REQUEST)
                    elif time_in_force == 'IOC':
                        # Immediate or Cancel order
                        if holding.quantity >= quantity:
                            trade = DemoTrade.objects.create(
                                user=request.user,
                                holding=holding,
                                quantity=quantity,
                                price=price,
                                order_type='sell',
                                status='pending',  # Set status to pending for background processing
                            )

                            # Asynchronously process the trade in the background
                            process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

                            return Response({'message': 'Sell order placed successfully.'}, status=status.HTTP_201_CREATED)
                        else:
                            return Response({'error': 'Not enough stocks to sell.'}, status=status.HTTP_400_BAD_REQUEST)
                    elif time_in_force == 'FOK':
                        # Fill or Kill order
                        if holding.quantity >= quantity:
                            trade = DemoTrade.objects.create(
                                user=request.user,
                                holding=holding,
                                quantity=quantity,
                                price=price,
                                order_type='sell',
                                status='pending',  # Set status to pending for background processing
                            )

                            # Asynchronously process the trade in the background
                            process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

                            return Response({'message': 'Sell order placed successfully.'}, status=status.HTTP_201_CREATED)
                        
                        else:
                            return Response({'error': 'FOK sell order rejected due to insufficient stocks.'}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'error': 'Invalid time in force.'}, status=status.HTTP_400_BAD_REQUEST)
        elif mode == 'live':
            return Response('Under Construction')

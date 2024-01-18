from turtle import position
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import portfolio
from portfolio.models import Stock, Wallet,DemoTransaction
from notifications.utils import save_and_send_notification
from rest_framework.permissions import IsAuthenticated
from accounts.utils import get_referrer
from affilate.models import BrokageCommission,RewardActivities, ReferralWallet
from decimal import Decimal
from .tasks import process_trade, update_equity
from portfolio.utils import get_price
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from django.db.models import Sum

from .models import DemoPosition, DemoPortfolio
from .serializers import DemoPositionSerializer

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
        portfolio = DemoPortfolio.objects.get_or_create(user=request.user)[0]
         
        if mode == 'demo':


            if order_type == 'market':
                market_price = round(Decimal(get_price(symbol)['current_price']), 2)
                amount = quantity * market_price
                
                position = DemoPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=DemoPosition.OPEN, 
                    open_price = market_price,
                    quantity=quantity,
                    amount_invested = amount
                    
                    
                )

                if is_buy:
                    trade_order_type = 'buy'
                else:
                    trade_order_type = 'sell'
                    position.order_type = 'sell'
                    position.save()

                # trade = DemoTrade.objects.create(
                #     user=request.user,
                #     position=position,
                #     quantity=quantity,
                #     price=market_price,
                #     order_type=trade_order_type,
                #     status='completed',
                # )

                # Record the transaction
                DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type='open trade',
                    amount=quantity * market_price,
                    status='completed'
                )
                position_data_list = []
                
                positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
                for position in positions:
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    
                    percent = round((pl/position.amount_invested) * 100,2)
                    data1 = {
                        'id':position.id,
                        'symbol':symbol,
                        'open_pl':pl,
                        'pl_percent': percent,
                        'created':position.created
                    }
                    position_data_list.append(data1)
                    
                
                return Response({'message': f'{action.title()} order placed successfully.', 'positions':position_data_list}, status=status.HTTP_201_CREATED)

            # elif order_type == 'limit':
            
            #     if is_buy:
            #         # Check if it's a market order or limit order
            #         if time_in_force == 'GTC':
            #             # Good 'Til Canceled order
            #             holding = DemoHolding.objects.get_or_create(
            #                 portfolio=portfolio,
            #                 stock=stock,
            #             )[0]
                        
            #             holding.quantity = quantity
            #             holding.save()
                
            #             trade = DemoTrade.objects.create(
            #                 user=request.user,
            #                 holding=holding,
            #                 quantity=quantity,
            #                 price=price,
            #                 order_type='buy',
            #                 status='pending',  # Set status to pending for background processing
            #             )

            #             # Asynchronously process the trade in the background
            #             process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

            #             return Response({'message': 'Buy order placed successfully.'}, status=status.HTTP_201_CREATED)
            #             # else:
            #             #     return Response({'error': 'Insufficient funds to buy stocks.'}, status=status.HTTP_400_BAD_REQUEST)
            #         elif time_in_force == 'IOC':
            #             # Immediate or Cancel order (Not supported for buy orders)
            #             return Response({'error': 'Immediate or Cancel (IOC) not supported for buy orders.'}, status=status.HTTP_400_BAD_REQUEST)
            #         elif time_in_force == 'FOK':
            #             # Fill or Kill order (Not supported for buy orders)
            #             return Response({'error': 'Fill or Kill (FOK) not supported for buy orders.'}, status=status.HTTP_400_BAD_REQUEST)
            #         else:
            #             return Response({'error': 'Invalid time in force.'}, status=status.HTTP_400_BAD_REQUEST)

            #     elif not is_buy:
            #         holding = DemoHolding.objects.get(
            #             portfolio=portfolio,
            #             stock=stock,
            #         )

            #         # Check if it's a market order or limit order
            #         if time_in_force == 'GTC':
            #             # Good 'Til Canceled order
            #             if holding.quantity >= quantity:
            #                 trade = DemoTrade.objects.create(
            #                     user=request.user,
            #                     holding=holding,
            #                     quantity=quantity,
            #                     price=price,
            #                     order_type='sell',
            #                     status='pending',  # Set status to pending for background processing
            #                 )

            #                 # Asynchronously process the trade in the background
            #                 process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

            #                 return Response({'message': 'Sell order placed successfully.'}, status=status.HTTP_201_CREATED)
            #             else:
            #                 return Response({'error': 'Not enough stocks to sell.'}, status=status.HTTP_400_BAD_REQUEST)
            #         elif time_in_force == 'IOC':
            #             # Immediate or Cancel order
            #             if holding.quantity >= quantity:
            #                 trade = DemoTrade.objects.create(
            #                     user=request.user,
            #                     holding=holding,
            #                     quantity=quantity,
            #                     price=price,
            #                     order_type='sell',
            #                     status='pending',  # Set status to pending for background processing
            #                 )

            #                 # Asynchronously process the trade in the background
            #                 process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

            #                 return Response({'message': 'Sell order placed successfully.'}, status=status.HTTP_201_CREATED)
            #             else:
            #                 return Response({'error': 'Not enough stocks to sell.'}, status=status.HTTP_400_BAD_REQUEST)
            #         elif time_in_force == 'FOK':
            #             # Fill or Kill order
            #             if holding.quantity >= quantity:
            #                 trade = DemoTrade.objects.create(
            #                     user=request.user,
            #                     holding=holding,
            #                     quantity=quantity,
            #                     price=price,
            #                     order_type='sell',
            #                     status='pending',  # Set status to pending for background processing
            #                 )

            #                 # Asynchronously process the trade in the background
            #                 process_trade.apply_async(args=[trade.id], kwargs={'time_in_force': time_in_force}, countdown=0)

            #                 return Response({'message': 'Sell order placed successfully.'}, status=status.HTTP_201_CREATED)
                        
            #             else:
            #                 return Response({'error': 'FOK sell order rejected due to insufficient stocks.'}, status=status.HTTP_400_BAD_REQUEST)
            #         else:
            #             return Response({'error': 'Invalid time in force.'}, status=status.HTTP_400_BAD_REQUEST)
        
        elif mode == 'live':
            return Response('Under Construction')

class Home(APIView):
    def get(self, request, *args, **kwargs):
        mode = self.kwargs.get('mode')
        if mode == 'demo':
            portfolio = DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
            
            balance = portfolio.equity
            
            profit_loss_list = []
            position_data_list = []
            current_value_list = []
            
            if positions:
                for position in positions:
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    profit_loss_list.append(pl)
                    
                    percent = round((pl/position.amount_invested) * 100,2)
                    data1 = {
                        'id':position.id,
                        'symbol':symbol,
                        'open_pl':pl,
                        'pl_percent': percent,
                        'created':position.created
                    }
                    position_data_list.append(data1)
                    
                    data2 =  {
                        'stock':symbol,
                        'current_value':round(cur_val,2)
                    }
                    current_value_list.append(data2)
                    
            profit_loss = sum(profit_loss_list) if profit_loss_list else 0
            
            
            def market_returns(current_portfolio_value, days=7):
                volatility_factor = 0.1  

                market_returns = [round(float(random.uniform(-volatility_factor, volatility_factor) + current_portfolio_value), 2) for _ in range(days)]
                portfolio_returns = [round(float((1 + market_return) + current_portfolio_value),2) for market_return in market_returns]

                end_date = datetime.now().date()
                date_list = [(end_date - timedelta(days=i)).isoformat() for i in range(days)][::-1]

                result_data = [
                    {"date": date, "portfolio_returns": portfolio, "market_returns": market}
                    for date, portfolio, market in zip(date_list, portfolio_returns, market_returns)
                ]

                return result_data
            
            total_current_value = 0

            # Iterate through the list of dictionaries
            if current_value_list:
                for data in current_value_list:
                    if 'current_value' in data:
                        total_current_value += data['current_value']
            
            overview = market_returns(total_current_value)
            
            data = {
                'balance':round(balance,2),
                'equity':round(balance + profit_loss,2),
                'floating_pl' : profit_loss,
                'positions': position_data_list,
                'current_value':current_value_list,
                "overview":overview
            }
            
            return Response(data)
        
class DemoCloseTrade(APIView):
    def post(self, request, *args, **kwargs):
        id= self.kwargs.get('id')
        position =  get_object_or_404(DemoPosition, id=id)
        if position.status == 'open':
            pl, cur_val,price = position.calculate_profit_loss()
            
            position.status = 'close'
            position.close_price = Decimal(price)
            position.profit_loss =pl
            position.save()
            
            DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type='close trade',
                    amount=cur_val,
                    status='completed'
                )
            data = {
                'id':position.id,
                'stock':position.stock.symbol,
                'quantity':position.quantity,
                'open_price':position.open_price,
                'close_price':position.close_price,
                'open_time':position.created.isoformat(),
                'close_time':position.updated.isoformat(),
                'profit_loss': position.profit_loss,
            }
            return Response(data)
        else:
            return Response("Position is already closed")
            
class DemoHolding(APIView):
    def get(self,request):
        portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
        positions =  DemoPosition.objects.filter(portfolio=portfolio).order_by("-updated")
        if positions:
            
            def get_position(position):
                pl, value, price= position.calculate_profit_loss()
                percent_change = round(pl/position.amount_invested *100,2)
                data = {
                    'id':position.id,
                    'stock':position.stock.symbol,
                    'shares':position.quantity,
                    'avg_cost':position.open_price,
                    'close_price':position.close_price,
                    'ltp':price,
                    'open_time':position.created.isoformat(),
                    'close_time':position.updated.isoformat(),
                    'change': pl,
                    "percent_change":percent_change,
                    'cur_val':value,
                    "avg_volume":'3300',
                    "volume":'66000',
                    'status':position.status,
                    'invested':position.amount_invested
                    
                    }
                return data

            # total_profit_loss, total_amount_invested = calculate_sum_of_profits_and_investments(port_positions)

            with ThreadPoolExecutor() as executor:
                futures = executor.map(get_position, positions)
                positions_data = [result for result in futures if result]

            portfolio_value = sum([data['cur_val'] for data in positions_data if data['status']=='close'])
            total_profit_loss = sum([data['change'] for data in positions_data if data['status']=='close'])
            total_amount_invested = sum([data['invested'] for data in positions_data if data['status']=='close'])
            
            
            hold_data ={
                'portfolio_value':portfolio_value,
                'profit_loss':total_profit_loss,
                'total_invested':total_amount_invested,
                'holdings':positions_data
                
            }
            
            return Response(hold_data)
        else:
            hold_data ={
                'portfolio_value':0,
                'profit_loss':0,
                'total_invested':0,
                'holdings':[]
                
            }
            
            return Response(hold_data)
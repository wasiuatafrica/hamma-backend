from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import portfolio
from portfolio.models import Portfolio, Stock, Wallet,DemoTransaction
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
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import shortuuid
import json

from .models import DemoPosition, DemoPortfolio, DemoProfitLoss
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

    def post(self, request):
        
        symbol = request.data.get('symbol')
        quantity = int(request.data.get('quantity'))
        if request.data.get('price'):
            price = float(request.data.get('price'))
        action = request.data.get('action')
        time_in_force = request.data.get('time_in_force', 'day')  # Default to Good 'Til Canceled
        is_buy = action == 'buy'
        order_type = request.data.get('order_type')
        
        print(order_type)
        
        stock = get_object_or_404(Stock, symbol=symbol)
        portfolio = DemoPortfolio.objects.get_or_create(user=request.user)[0]
         
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

            if not is_buy:
                position.action = 'sell'
                position.save()

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
                
            save_and_send_notification(request.user.id,f' DEMO: You opened position {quantity} units of {stock.symbol} at {price} per unit. Total value:{quantity * price}naira ')
            
            return Response({'message': f'{action.title()} order placed successfully.', 'positions':position_data_list}, status=status.HTTP_201_CREATED)

        elif order_type == 'limit':
            print('here1')    
            
            position = DemoPosition.objects.create(
                portfolio=portfolio,
                stock=stock,
                status=DemoPosition.PENDING, 
                limit_price = price,
                quantity=quantity,
                alert_name = shortuuid.uuid(),
                time_in_force=time_in_force
                
                
            )
            print('here2')    
            
            schedule, created = IntervalSchedule.objects.get_or_create(
                    every=3,
                    period=IntervalSchedule.MINUTES,
                )
            
            if not is_buy:
                position.action = 'sell'
                position.save()
                
            task = PeriodicTask.objects.create(
                    interval=schedule,
                    name=position.alert_name,
                    task='execution.tasks.process_limit_order',
                    args=json.dumps([position.id])
                )
            print('here3')    
            
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
                
            save_and_send_notification(request.user.id,f' DEMO: Your order will be opened when the condition you set met.')
            
            return Response({'message': f'{action.title()} order scheduled successfully.', 'positions':position_data_list}, status=status.HTTP_201_CREATED)

            

class Home(APIView):
    def get(self, request, *args, **kwargs):
        mode = self.kwargs.get('mode')
        if mode == 'demo':
            portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
            
            balance = portfolio.equity
            
            profit_loss_list = []
            current_value_list = []
            
            if positions:
                for position in positions:
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    print(pl)
                    profit_loss_list.append(pl) 
                    
                    
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
            daily_profitloss= DemoProfitLoss.objects.filter(user=request.user)
            if daily_profitloss:
                position_data_list = [
                    {
                        'profit_loss':daily.profit_loss,
                        'date':daily.created.date()
                    } for daily in daily_profitloss
                ]
            else:
                position_data_list =[]
                
            equity1 = round(balance + profit_loss,2)
            equity = equity1 if equity1 >= 0 else 0
            data = {
                'balance':round(balance,2),
                'equity':equity,
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
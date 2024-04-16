from re import U
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import competition
from portfolio.models import Stock, DemoTransaction
from notifications.utils import save_and_send_notification
from rest_framework.permissions import IsAuthenticated
from accounts.utils import User, get_referrer
from affilate.models import BrokageCommission,RewardActivities, ReferralWallet
from decimal import Decimal
# from .tasks import process_trade, update_equity
from portfolio.utils import get_price
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from django.db.models import Sum
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import shortuuid
import json
from django.utils import timezone
from accounts.models import  UserActivityLog 

from .models import DemoCumulativeReturns, DemoPosition, DemoPortfolio, DemoDailyReturns, DemoDailyReturns2, MarketReturns, CumulativeMarketReturns
from  competition.models import CompetitionCumulativeReturns, CompetitionPosition,CompetitionDailyReturns,CompetitionPortfolio,CompetitionTransaction
from django.contrib.auth.models import User
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

    def get(self,request):
        portfolio =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
        if portfolio:
            positions = CompetitionPosition.objects.filter(portfolio=portfolio, status='open')
        else:
            positions = DemoPosition.objects.filter(portfolio__user=request.user,status='open')
        
        def get_position(position):
                # print(position.id)
                pl, cur_val,price = position.calculate_profit_loss()
                symbol=position.stock.symbol
                
                if position.amount_invested != 0:
                    percent = round((pl/position.amount_invested) * 100,2)
                    data1 = {
                        'id':position.id,
                        'symbol':symbol,
                        'open_pl':round(pl,2),
                        'pl_percent': percent,
                        'created':position.created,
                        'status':position.status,
                        'open_price': position.open_price,
                        'order_id':position.order_id,
                    }
                    
                else:
                    data1 = {
                        'id':position.id,
                        'symbol':symbol,
                        'open_pl':0,
                        'pl_percent': 0,
                        'created':position.created,
                        'status':position.status,
                        'open_price': position.open_price,
                        'order_id':position.order_id,
                    }
                return data1
            
        with ThreadPoolExecutor() as executor:
            futures = executor.map(get_position, positions)
            position_data_list = [result for result in futures if result]
            
            return Response(position_data_list)
    
    def post(self, request):
        
        symbol = request.data.get('symbol')
        order_id = request.data.get('order_id')
        quantity = int(request.data.get('quantity'))
        if request.data.get('price'):
            price = float(request.data.get('price'))
        action = request.data.get('action')
        time_in_force = request.data.get('time_in_force', 'day')  # Default to Good 'Til Canceled
        is_buy = action == 'buy'
        order_type = request.data.get('order_type')
        
        # print(order_type)
        
        stock = get_object_or_404(Stock, symbol=symbol)
        
        in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
        if in_competition:
            portfolio = in_competition
            if order_type == 'market':
                market_price = round(Decimal(get_price(symbol)['current_price']), 2)
                amount = quantity * market_price
                
                balance =  portfolio.balance
                trade_commission = round(Decimal(0.00435) * amount, 2) + 200
                
                total= amount + trade_commission
                if balance >= total:
                    position = CompetitionPosition.objects.create(
                        portfolio=portfolio,
                        stock=stock,
                        status=CompetitionPosition.OPEN, 
                        open_price = market_price,
                        quantity=quantity,
                        amount_invested = amount,
                        order_id=order_id
                    )

                    if not is_buy:
                        position.action = 'sell'
                        position.save()

                    CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type='open trade',
                        amount=amount,
                        status='completed'
                    )
                    CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type='trade commission',
                        amount=trade_commission,
                        status='completed'
                    )
                    
                    portfolio.balance -= total
                    portfolio.save()
                    
                    
                    activity=UserActivityLog.objects.create(user=request.user, action_type="competition_open_trade",description=f"User opened competition trade with amount {amount} on symbol {symbol}.")
                    positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='open')
                    
                    def get_position(position):
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
                        return data1
                    
                    # with ThreadPoolExecutor() as executor:
                    #     futures = executor.map(get_position, positions)
                    #     position_data_list = [result for result in futures if result]
                    
                        
                    save_and_send_notification(request.user.id,f' COMPETITION: You opened position {quantity} units of {stock.symbol} at {position.open_price} per unit. Total value:{quantity * position.open_price}naira ')
                    
                    return Response({'message': f'{action.title()} order placed successfully.'}, status=status.HTTP_201_CREATED)
                else:
                    return Response({'error': 'Insufficient funds to trade.'}, status=status.HTTP_400_BAD_REQUEST)

            elif order_type == 'limit':
                
                position = CompetitionPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=CompetitionPosition.PENDING, 
                    limit_price = price,
                    quantity=quantity,
                    alert_name = 'pending trade' + shortuuid.uuid(),
                    time_in_force=time_in_force,
                    order_id=order_id
                    
                    
                )  
                
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
                        args=json.dumps([position.id, True])
                    )
                
                positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='open',active=True)
                
                def get_position(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    
                    percent = round((pl/position.amount_invested) * 100,2)
                    data1 = {
                        'id':position.id,
                        'symbol':symbol,
                        'open_pl':pl,
                        'pl_percent': percent,
                        'created':position.created,
                        'order_id':position.order_id,
                        
                    }
                    return data1
                
                # with ThreadPoolExecutor() as executor:
                #     futures = executor.map(get_position, positions)
                #     position_data_list = [result for result in futures if result]
                    
                save_and_send_notification(request.user.id,f' COMPETITION: Your limit order will be opened when the condition you set is met.')
                
                return Response({'message': f'{action.title()} order scheduled successfully.'}, status=status.HTTP_201_CREATED)

        else:
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
                    amount_invested = amount,
                    order_id=order_id
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
                activity=UserActivityLog.objects.create(user=request.user, action_type="demo_open_trade",description=f"User opened demo trade with amount {amount} on symbol {symbol}.")
                positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
                
                def get_position(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    if position.amount_invested != 0:
                        percent = round((pl/position.amount_invested) * 100,2)
                        data1 = {
                            'id':position.id,
                            'symbol':symbol,
                            'open_pl':pl,
                            'pl_percent': percent,
                            'created':position.created
                        }
                    else:
                        data1 = {
                            'id':position.id,
                            'symbol':symbol,
                            'open_pl':0,
                            'pl_percent': 0,
                            'created':position.created
                        }
                    return data1
                
                # with ThreadPoolExecutor() as executor:
                #     futures = executor.map(get_position, positions)
                #     position_data_list = [result for result in futures if result]
                
                    
                save_and_send_notification(request.user.id,f' DEMO: You opened position {quantity} units of {stock.symbol} at {position.open_price} per unit. Total value:{quantity * position.open_price}naira ')
                
                return Response({'message': f'{action.title()} order placed successfully.'}, status=status.HTTP_201_CREATED)

            elif order_type == 'limit':
                
                position = DemoPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=DemoPosition.PENDING, 
                    limit_price = price,
                    quantity=quantity,
                    alert_name = shortuuid.uuid(),
                    time_in_force=time_in_force,
                    order_id=order_id
                    
                    
                )  
                
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
                
                positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
                
                def get_position(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    
                    if position.amount_invested != 0:
                        percent = round((pl/position.amount_invested) * 100,2)
                        data1 = {
                            'id':position.id,
                            'symbol':symbol,
                            'open_pl':pl,
                            'pl_percent': percent,
                            'created':position.created,
                            'order_id':position.order_id,
                            
                        }
                    else:
                        data1 = {
                            'id':position.id,
                            'symbol':symbol,
                            'open_pl':0,
                            'pl_percent': 0,
                            'created':position.created,
                            'order_id':position.order_id,

                        }
                    return data1
                
                # with ThreadPoolExecutor() as executor:
                #     futures = executor.map(get_position, positions)
                #     position_data_list = [result for result in futures if result]
                    
                save_and_send_notification(request.user.id,f' DEMO: Your limit order will be opened when the condition you set is met.')
                
                return Response({'message': f'{action.title()} order scheduled successfully.'}, status=status.HTTP_201_CREATED)

            

class Home(APIView):
    def get(self, request, *args, **kwargs):
        mode = self.kwargs.get('mode')
        if mode == 'demo':
            in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
            if in_competition:
                portfolio = in_competition
                
                positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='open')
                positions2 = CompetitionPosition.objects.filter(portfolio=portfolio,status='close')
                
                today = timezone.now()
                position_data_dict = {}

                for daily in positions2:
                    if daily.updated.month == today.month:
                        date_key = daily.updated.date()
                        if date_key in position_data_dict:
                            position_data_dict[date_key] += daily.profit_loss
                        else:
                            position_data_dict[date_key] = daily.profit_loss

                position_data_list2 = [
                    {'profit_loss': profit_loss, 'date': date} 
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item['date'] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {'profit_loss': position_data_dict.get(date, 0), 'date': date.strftime('%Y-%m-%d')}
                    for date in (start_date + timedelta(n) for n in range((today.date() - start_date).days + 1) if (start_date + timedelta(n)).weekday() < 5) 
                ]
                profit_loss2= sum([pos.profit_loss for pos in positions2])
                
                balance = portfolio.balance
                
                def pl_cv(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    print(pl)
                    data2 =  {
                            'stock':symbol,
                            'current_value':round(cur_val,2)
                        }
                    
                    return pl, data2
                
                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]
                
                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]
                        
                profit_loss = sum(profit_loss_list) if profit_loss_list else 0
                
                
                daily_profitloss= CompetitionDailyReturns.objects.filter(user=request.user, portfolio=in_competition)
                cumulative_profitloss= CompetitionCumulativeReturns .objects.filter(user=request.user, portfolio=in_competition)
                if daily_profitloss:
                    today = timezone.now()

                    overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': daily.market_returns,
                            'date': daily.created.date()
                        } for daily in daily_profitloss 
                    ]

                else:
                    position_data_list =[]
                    overview = []
                    
                if cumulative_profitloss:
                    today = timezone.now()

                    cumulative_overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': daily.market_returns,
                            'date': daily.created.date()
                        } for daily in cumulative_profitloss 
                    ]

                else:
                    cumulative_overview = []
                
                balance2 = sum([pos.amount_invested for pos in positions])
                  
                # equity1 = round(balance + profit_loss,2)
                equity2 = round(balance2 + profit_loss,2)
                
                # equity = equity1 if equity1 >= 0 else 0
                equity = equity2 if equity2 >= 0 else 0
                
                
                data = {
                    'balance':round(balance2,2),
                    'equity':equity,
                    'floating_pl' : profit_loss,
                    'closed_pl' : profit_loss2,
                    # 'positions': position_data_list2,
                    'positions': final_list,
                    # 'open_positions': position_data_list,
                    'current_value':current_value_list,
                    "overview":overview,
                    "cumulative_overview":cumulative_overview
                }
                
                return Response(data)
            else:
                portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
                positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
                positions2 = DemoPosition.objects.filter(portfolio=portfolio,status='close')
                
                today = timezone.now()
                position_data_dict = {}

                for daily in positions2:
                    if daily.updated.month == today.month:
                        date_key = daily.updated.date()
                        if date_key in position_data_dict:
                            position_data_dict[date_key] += daily.profit_loss
                        else:
                            position_data_dict[date_key] = daily.profit_loss

                position_data_list2 = [
                    {'profit_loss': profit_loss, 'date': date} 
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item['date'] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {'profit_loss': position_data_dict.get(date, 0), 'date': date.strftime('%Y-%m-%d')}
                    for date in (start_date + timedelta(n) for n in range((today.date() - start_date).days + 1) if (start_date + timedelta(n)).weekday() < 5) 
                ]
                profit_loss2= sum([pos.profit_loss for pos in positions2])
                
                balance = portfolio.balance
                
                # profit_loss_list = []
                # current_value_list = []
                
                # if positions:
                #     for position in positions:
                #         pl, cur_val,price = position.calculate_profit_loss()
                #         symbol=position.stock.symbol
                #         print(pl)
                #         profit_loss_list.append(pl) 
                        
                        
                #         data2 =  {
                #             'stock':symbol,
                #             'current_value':round(cur_val,2)
                #         }
                #         current_value_list.append(data2)
                def pl_cv(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    print(pl)
                    data2 =  {
                            'stock':symbol,
                            'current_value':round(cur_val,2)
                        }
                    
                    return pl, data2
                
                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]
                
                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]
                        
                profit_loss = sum(profit_loss_list) if profit_loss_list else 0
                
                
                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss= DemoDailyReturns2.objects.filter(user=request.user)
                cumulative_profitloss= DemoCumulativeReturns.objects.filter(user=request.user)
                
                market= MarketReturns.objects.all()
                cumulative_market = CumulativeMarketReturns.objects.all()
                
                if daily_profitloss:
                    today = timezone.now()
                    
                    overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': 0,
                            'date': daily.created.date()
                        } for daily in daily_profitloss 
                    ]

                    for num,item in enumerate(overview):
                        if num == 0:
                                item['market_returns'] = 0
                        for dr in market:
                           
                            if dr.created.date() == item['date']:
                                item['market_returns'] = dr.market_returns
                    
                else:
                    position_data_list =[]
                    overview = []
                
                if cumulative_profitloss:
                    today = timezone.now()

                    cumulative_overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': 0,
                            'date': daily.created.date()
                        } for daily in cumulative_profitloss 
                    ]
                    
                    for num, item in enumerate(cumulative_overview):
                        if num == 0:
                            item['market_returns'] = 0
                        for dr in cumulative_market:
                            
                            if dr.created.date() == item['date']:
                                item['market_returns'] = dr.market_returns

                else:
                    cumulative_overview = []
                
                equity1 = round(balance + profit_loss,2)
                equity = equity1 if equity1 >= 0 else 0
                
                
                data = {
                    'balance':round(balance,2),
                    'equity':equity,
                    'floating_pl' : profit_loss,
                    'closed_pl' : profit_loss2,
                    # 'positions': position_data_list2,
                    'positions': final_list,
                    # 'open_positions': position_data_list,
                    'current_value':current_value_list,
                    "overview":overview,
                    "cumulative_overview":cumulative_overview
                }
                
                return Response(data)
        
class SupportHome(APIView):
    def get(self, request, *args, **kwargs):
        mode = self.kwargs.get('mode')
        email = self.kwargs.get('email')
        user = User.objects.get(email=email)
        
        if mode == 'demo':
            in_competition =  CompetitionPortfolio.objects.filter(user=user, competition__status='current',active=True).first()
            if in_competition:
                portfolio = in_competition
                
                positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='open')
                positions2 = CompetitionPosition.objects.filter(portfolio=portfolio,status='close')
                
                today = timezone.now()
                position_data_dict = {}

                for daily in positions2:
                    if daily.updated.month == today.month:
                        date_key = daily.updated.date()
                        if date_key in position_data_dict:
                            position_data_dict[date_key] += daily.profit_loss
                        else:
                            position_data_dict[date_key] = daily.profit_loss

                position_data_list2 = [
                    {'profit_loss': profit_loss, 'date': date} 
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item['date'] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {'profit_loss': position_data_dict.get(date, 0), 'date': date.strftime('%Y-%m-%d')}
                    for date in (start_date + timedelta(n) for n in range((today.date() - start_date).days + 1) if (start_date + timedelta(n)).weekday() < 5) 
                ]
                profit_loss2= sum([pos.profit_loss for pos in positions2])
                
                balance = portfolio.balance
                
                def pl_cv(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    print(pl)
                    data2 =  {
                            'stock':symbol,
                            'current_value':round(cur_val,2)
                        }
                    
                    return pl, data2
                
                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]
                
                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]
                        
                profit_loss = sum(profit_loss_list) if profit_loss_list else 0
                
                
                daily_profitloss= CompetitionDailyReturns.objects.filter(user=user, portfolio=in_competition)
                cumulative_profitloss= CompetitionCumulativeReturns .objects.filter(user=user, portfolio=in_competition)
                if daily_profitloss:
                    today = timezone.now()

                    overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': daily.market_returns,
                            'date': daily.created.date()
                        } for daily in daily_profitloss 
                    ]

                else:
                    position_data_list =[]
                    overview = []
                    
                if cumulative_profitloss:
                    today = timezone.now()

                    cumulative_overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': daily.market_returns,
                            'date': daily.created.date()
                        } for daily in cumulative_profitloss 
                    ]

                else:
                    cumulative_overview = []
                
                balance2 = sum([pos.amount_invested for pos in positions])
                  
                # equity1 = round(balance + profit_loss,2)
                equity2 = round(balance2 + profit_loss,2)
                
                # equity = equity1 if equity1 >= 0 else 0
                equity = equity2 if equity2 >= 0 else 0
                
                
                data = {
                    'balance':round(balance2,2),
                    'equity':equity,
                    'floating_pl' : profit_loss,
                    'closed_pl' : profit_loss2,
                    # 'positions': position_data_list2,
                    'positions': final_list,
                    # 'open_positions': position_data_list,
                    'current_value':current_value_list,
                    "overview":overview,
                    "cumulative_overview":cumulative_overview
                }
                
                return Response(data)
            else:
                portfolio= DemoPortfolio.objects.get_or_create(user=user)[0]
                positions = DemoPosition.objects.filter(portfolio=portfolio,status='open')
                positions2 = DemoPosition.objects.filter(portfolio=portfolio,status='close')
                
                today = timezone.now()
                position_data_dict = {}

                for daily in positions2:
                    if daily.updated.month == today.month:
                        date_key = daily.updated.date()
                        if date_key in position_data_dict:
                            position_data_dict[date_key] += daily.profit_loss
                        else:
                            position_data_dict[date_key] = daily.profit_loss

                position_data_list2 = [
                    {'profit_loss': profit_loss, 'date': date} 
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item['date'] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {'profit_loss': position_data_dict.get(date, 0), 'date': date.strftime('%Y-%m-%d')}
                    for date in (start_date + timedelta(n) for n in range((today.date() - start_date).days + 1) if (start_date + timedelta(n)).weekday() < 5) 
                ]
                profit_loss2= sum([pos.profit_loss for pos in positions2])
                
                balance = portfolio.balance
                
                # profit_loss_list = []
                # current_value_list = []
                
                # if positions:
                #     for position in positions:
                #         pl, cur_val,price = position.calculate_profit_loss()
                #         symbol=position.stock.symbol
                #         print(pl)
                #         profit_loss_list.append(pl) 
                        
                        
                #         data2 =  {
                #             'stock':symbol,
                #             'current_value':round(cur_val,2)
                #         }
                #         current_value_list.append(data2)
                def pl_cv(position):
                    pl, cur_val,price = position.calculate_profit_loss()
                    symbol=position.stock.symbol
                    print(pl)
                    data2 =  {
                            'stock':symbol,
                            'current_value':round(cur_val,2)
                        }
                    
                    return pl, data2
                
                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]
                
                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]
                        
                profit_loss = sum(profit_loss_list) if profit_loss_list else 0
                
                
                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss= DemoDailyReturns2.objects.filter(user=user)
                cumulative_profitloss= DemoCumulativeReturns.objects.filter(user=user)
                
                market= MarketReturns.objects.all()
                cumulative_market = CumulativeMarketReturns.objects.all()
                
                if daily_profitloss:
                    today = timezone.now()
                    
                    overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': 0,
                            'date': daily.created.date()
                        } for daily in daily_profitloss 
                    ]

                    for num,item in enumerate(overview):
                        if num == 0:
                                item['market_returns'] = 0
                        for dr in market:
                           
                            if dr.created.date() == item['date']:
                                item['market_returns'] = dr.market_returns
                    
                else:
                    position_data_list =[]
                    overview = []
                
                if cumulative_profitloss:
                    today = timezone.now()

                    cumulative_overview = [
                        {
                            'portfolio_returns': daily.portfolio_returns,
                            'market_returns': 0,
                            'date': daily.created.date()
                        } for daily in cumulative_profitloss 
                    ]
                    
                    for num, item in enumerate(cumulative_overview):
                        if num == 0:
                            item['market_returns'] = 0
                        for dr in cumulative_market:
                            
                            if dr.created.date() == item['date']:
                                item['market_returns'] = dr.market_returns

                else:
                    cumulative_overview = []
                
                equity1 = round(balance + profit_loss,2)
                equity = equity1 if equity1 >= 0 else 0
                
                
                data = {
                    'balance':round(balance,2),
                    'equity':equity,
                    'floating_pl' : profit_loss,
                    'closed_pl' : profit_loss2,
                    # 'positions': position_data_list2,
                    'positions': final_list,
                    # 'open_positions': position_data_list,
                    'current_value':current_value_list,
                    "overview":overview,
                    "cumulative_overview":cumulative_overview
                }
                
                return Response(data)
  

class DemoCloseTrade(APIView):
    def post(self, request, *args, **kwargs):
        id= self.kwargs.get('id')
        in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
        if in_competition:
            position =  get_object_or_404(CompetitionPosition, id=id)
            if position.status == 'open':
                pl, cur_val,price = position.calculate_profit_loss()
                
                position.status = 'close'
                position.close_price = Decimal(price)
                position.profit_loss =pl
                position.save()
                
                CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type='close trade',
                        amount=cur_val,
                        status='completed'
                    )
                activity=UserActivityLog.objects.create(user=request.user, action_type="competition_closed_trade",description=f"User closed competition trade with symbol {position.stock.symbol}.")
                position.portfolio.balance += position.amount_invested + position.profit_loss
                position.portfolio.save()
                
                data = {
                    'id':position.id,
                    'stock':position.stock.symbol,
                    'quantity':position.quantity,
                    'open_price':position.open_price,
                    'close_price':position.close_price,
                    'open_time':position.created.isoformat(),
                    'close_time':position.updated.isoformat(),
                    'profit_loss': position.profit_loss,
                    'order_id':position.order_id
                }
                return Response(data)
            else:
                return Response("Position is already closed")
        else:
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
                activity=UserActivityLog.objects.create(user=request.user, action_type="demo_closed_trade",description=f"User closed demo trade with symbol {position.stock.symbol}.")
                position.portfolio.balance += position.amount_invested + position.profit_loss
                position.portfolio.save()
                
                data = {
                    'id':position.id,
                    'stock':position.stock.symbol,
                    'quantity':position.quantity,
                    'open_price':position.open_price,
                    'close_price':position.close_price,
                    'open_time':position.created.isoformat(),
                    'close_time':position.updated.isoformat(),
                    'profit_loss': position.profit_loss,
                    'order_id':position.order_id
                }
                return Response(data)
            else:
                return Response("Position is not open")
    
class DemoClosePendingTrade(APIView):
    def post(self, request, *args, **kwargs):
        id= self.kwargs.get('id')
        in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
        if in_competition:
            position =  get_object_or_404(CompetitionPosition, id=id)
            if position.status == 'pending':
                
                
                position.status = 'cancelled'
                position.save()
                
                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()
               
                activity=UserActivityLog.objects.create(user=request.user, action_type="competition_cancel_trade",description=f"User cancelled competition pending trade with symbol {position.stock.symbol}.")
                               
                data = {
                    'id':position.id,
                    'stock':position.stock.symbol,
                    'quantity':position.quantity,
                    'open_price':position.open_price,
                    'close_price':position.close_price,
                    'open_time':position.created.isoformat(),
                    'close_time':position.updated.isoformat(),
                    'profit_loss': position.profit_loss,
                    'order_id':position.order_id
                }
                return Response(data)
            else:
                return Response("Position is already cancelled")
        else:
            position =  get_object_or_404(DemoPosition, id=id)
            if position.status == 'pending':
               
                
                position.status = 'cancelled'
                
                position.save()
                
                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()
                
                UserActivityLog.objects.create(user=request.user, action_type="demo_closed_pending_trade",description=f"User cancelled  demo pending trade with symbol {position.stock.symbol}.")
               
                
                data = {
                    'id':position.id,
                    'stock':position.stock.symbol,
                    'quantity':position.quantity,
                    'open_price':position.open_price,
                    'close_price':position.close_price,
                    'open_time':position.created.isoformat(),
                    'close_time':position.updated.isoformat(),
                    'profit_loss': position.profit_loss,
                    'order_id':position.order_id
                }
                return Response(data)
            else:
                return Response("Position is not open")
    
        
class DemoHolding(APIView):
    def get(self,request):
        in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
        if in_competition:
            portfolio = in_competition
                
            positions =  CompetitionPosition.objects.filter(portfolio=portfolio).order_by("-updated")
            balance =  portfolio.balance
            
            if positions:
                
                def get_position(position):
                    
                    pl, value, price= position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl/position.amount_invested *100,2)
                    else:
                        percent_change = None
                        
                    
                    data = {
                        'id':position.id,
                        'stock':position.stock.symbol,
                        'shares':position.quantity,
                        'avg_cost':position.open_price,
                        'close_price':position.close_price,
                        'ltp':price,
                        'open_time':position.created.isoformat(),
                        'close_time':position.updated.isoformat() if position.updated != position.created else '-',
                        'change': pl,
                        "percent_change":percent_change,
                        'cur_val':value,
                        "avg_volume":'3300',
                        "volume":'66000',
                        'status':position.status,
                        'invested':position.amount_invested,
                        "profit_loss":position.profit_loss,
                        "side":position.action,
                        "order":position.order_type,
                        'order_id':position.order_id
                        
                        }
                    return data


                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum([data['change'] for data in positions_data if data['status']=='open'])
                closed_pl = sum([data['profit_loss'] for data in positions_data if data['status']=='close'])
                open_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='open'])
                # closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance
                
                hold_data ={
                    'balance':open_trade_sum ,
                    'floating_pl':floating_pl,
                    'closed_pl':closed_pl,
                    'equity':open_trade_sum  + floating_pl,
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
        else:
            portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions =  DemoPosition.objects.filter(portfolio=portfolio).order_by("-updated")
            balance =  portfolio.balance
            
            if positions:
                
                def get_position(position):
                    
                    pl, value, price= position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl/position.amount_invested *100,2)
                    else:
                        percent_change = None
                        
                    if position.status == 'open':
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        'id':position.id,
                        'stock':position.stock.symbol,
                        'shares':position.quantity,
                        'avg_cost':position.open_price,
                        'close_price':position.close_price,
                        'ltp':price,
                        'open_time':position.created.isoformat(),
                        'close_time':position.updated.isoformat() if position.updated != position.created else '-',
                        'change': pl,
                        "percent_change":percent_change,
                        'cur_val':value,
                        "avg_volume":'3300',
                        "volume":'66000',
                        'status':position.status,
                        'invested':position.amount_invested,
                        "profit_loss":profit_loss,
                        "side":position.action,
                        "order":position.order_type,
                        'order_id':position.order_id
                        
                        }
                    return data


                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum([data['change'] for data in positions_data if data['status']=='open'])
                closed_pl = sum([data['profit_loss'] for data in positions_data if data['status']=='close'])
                open_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='open'])
                closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance
                balance = open_trade_sum + closed_trade_sum + closed_pl 
                
                hold_data ={
                    'balance':balance,
                    'floating_pl':floating_pl,
                    'closed_pl':closed_pl,
                    'equity':balance  + floating_pl,
                    'holdings':positions_data
                    
                }
                
                return Response(hold_data)
            else:
                hold_data ={
                    'balance':0,
                    'floating_pl':0,
                    'closed_pl':0,
                    'equity':0,
                    'holdings':[]
                    
                }
                
                return Response(hold_data)
            
from accounts.models import CustomUser

class SupportDemoHolding(APIView):
    def get(self,request, *args, **kwargs):
        email = kwargs.get('email')
        print(email)
        user = CustomUser.objects.get(email=email)
        
        in_competition =  CompetitionPortfolio.objects.filter(user=user, competition__status='current',active=True).first()
        if in_competition:
            portfolio = in_competition
                
            positions =  CompetitionPosition.objects.filter(portfolio=portfolio).order_by("-updated")
            balance =  portfolio.balance
            
            if positions:
                
                def get_position(position):
                    
                    pl, value, price= position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl/position.amount_invested *100,2)
                    else:
                        percent_change = None
                        
                    
                    data = {
                        'id':position.id,
                        'stock':position.stock.symbol,
                        'shares':position.quantity,
                        'avg_cost':position.open_price,
                        'close_price':position.close_price,
                        'ltp':price,
                        'open_time':position.created.isoformat(),
                        'close_time':position.updated.isoformat() if position.updated != position.created else '-',
                        'change': pl,
                        "percent_change":percent_change,
                        'cur_val':value,
                        "avg_volume":'3300',
                        "volume":'66000',
                        'status':position.status,
                        'invested':position.amount_invested,
                        "profit_loss":position.profit_loss,
                        "side":position.action,
                        "order":position.order_type,
                        'order_id':position.order_id
                        
                        }
                    return data


                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum([data['change'] for data in positions_data if data['status']=='open'])
                closed_pl = sum([data['profit_loss'] for data in positions_data if data['status']=='close'])
                open_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='open'])
                # closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance
                
                hold_data ={
                    'balance':open_trade_sum ,
                    'floating_pl':floating_pl,
                    'closed_pl':closed_pl,
                    'equity':open_trade_sum  + floating_pl,
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
        else:
            portfolio= DemoPortfolio.objects.get_or_create(user=user)[0]
            positions =  DemoPosition.objects.filter(portfolio=portfolio).order_by("-updated")
            balance =  portfolio.balance
            
            if positions:
                
                def get_position(position):
                    
                    pl, value, price= position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl/position.amount_invested *100,2)
                    else:
                        percent_change = None
                        
                    if position.status == 'open':
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        'id':position.id,
                        'stock':position.stock.symbol,
                        'shares':position.quantity,
                        'avg_cost':position.open_price,
                        'close_price':position.close_price,
                        'ltp':price,
                        'open_time':position.created.isoformat(),
                        'close_time':position.updated.isoformat() if position.updated != position.created else '-',
                        'change': pl,
                        "percent_change":percent_change,
                        'cur_val':value,
                        "avg_volume":'3300',
                        "volume":'66000',
                        'status':position.status,
                        'invested':position.amount_invested,
                        "profit_loss":profit_loss,
                        "side":position.action,
                        "order":position.order_type,
                        'order_id':position.order_id
                        
                        }
                    return data


                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum([data['change'] for data in positions_data if data['status']=='open'])
                closed_pl = sum([data['profit_loss'] for data in positions_data if data['status']=='close'])
                open_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='open'])
                closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance
                balance = open_trade_sum + closed_trade_sum + closed_pl 
                
                hold_data ={
                    'balance':balance,
                    'floating_pl':floating_pl,
                    'closed_pl':closed_pl,
                    'equity':balance  + floating_pl,
                    'holdings':positions_data
                    
                }
                
                return Response(hold_data)
            else:
                hold_data ={
                    'balance':0,
                    'floating_pl':0,
                    'closed_pl':0,
                    'equity':0,
                    'holdings':[]
                    
                }
                
                return Response(hold_data)
            


class DemoHolding2(APIView):
    def get(self,request):
        def get_price():
            from portfolio.utils import connect_to_mongodb
            db = connect_to_mongodb("stock_prices")
            collection = db["price_combined"]
            last_item = collection.find_one(sort=[('_id', -1)])
            # print(symbol)
            return last_item
        
        all_prices = get_price()
        
        in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition__status='current',active=True).first()
        if in_competition:
            portfolio = in_competition
                
            positions =  CompetitionPosition.objects.filter(portfolio=portfolio).order_by("-updated")
            balance =  portfolio.balance
            
            if positions:
                
                def get_position(position):
                    if position.status == 'close':
                    # pl, value, price= position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                        pl = position.profit_loss
                    
                        if position.amount_invested != 0:
                            percent_change = round(pl/position.amount_invested *100,2)
                        else:
                            percent_change = None
                        price = all_prices[position.stock.symbol]['current_price']
                        value = round(position.quantity * price,2)
                        
                    
                        data = {
                            'id':position.id,
                            'stock':position.stock.symbol,
                            'shares':position.quantity,
                            'avg_cost':position.open_price,
                            'close_price':position.close_price,
                            'ltp':price,
                            'open_time':position.created.isoformat(),
                            'close_time':position.updated.isoformat() if position.updated != position.created else '-',
                            'change': pl,
                            "percent_change":percent_change,
                            'cur_val':value,
                            "avg_volume":'3300',
                            "volume":'66000',
                            'status':position.status,
                            'invested':position.amount_invested,
                            "profit_loss":position.profit_loss,
                            "side":position.action,
                            "order":position.order_type,
                            'order_id':position.order_id
                            
                            }
                    return data


                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum([data['change'] for data in positions_data if data['status']=='open'])
                closed_pl = sum([data['profit_loss'] for data in positions_data if data['status']=='close'])
                open_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='open'])
                # closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance
                
                hold_data ={
                    'balance':open_trade_sum ,
                    'floating_pl':floating_pl,
                    'closed_pl':closed_pl,
                    'equity':open_trade_sum  + floating_pl,
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
        else:
            portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions =  DemoPosition.objects.filter(portfolio=portfolio).order_by("-updated")
            balance =  portfolio.balance
            
            if positions:
                
                def get_position(position):
                    
                    pl, value, price= position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl/position.amount_invested *100,2)
                    else:
                        percent_change = None
                        
                    if position.status == 'open':
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        'id':position.id,
                        'stock':position.stock.symbol,
                        'shares':position.quantity,
                        'avg_cost':position.open_price,
                        'close_price':position.close_price,
                        'ltp':price,
                        'open_time':position.created.isoformat(),
                        'close_time':position.updated.isoformat() if position.updated != position.created else '-',
                        'change': pl,
                        "percent_change":percent_change,
                        'cur_val':value,
                        "avg_volume":'3300',
                        "volume":'66000',
                        'status':position.status,
                        'invested':position.amount_invested,
                        "profit_loss":profit_loss,
                        "side":position.action,
                        "order":position.order_type,
                        'order_id':position.order_id
                        
                        }
                    return data


                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum([data['change'] for data in positions_data if data['status']=='open'])
                closed_pl = sum([data['profit_loss'] for data in positions_data if data['status']=='close'])
                open_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='open'])
                # closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance
                
                hold_data ={
                    'balance':open_trade_sum ,
                    'floating_pl':floating_pl,
                    'closed_pl':closed_pl,
                    'equity':open_trade_sum  + floating_pl,
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
            

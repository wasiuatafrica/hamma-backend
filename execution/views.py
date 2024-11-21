from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import competition
import portfolio
from portfolio.models import Stock, DemoTransaction, Wallet
from notifications.utils import save_and_send_notification
from rest_framework.permissions import IsAuthenticated
from accounts.utils import User, get_referrer
from affilate.models import BrokageCommission, RewardActivities, ReferralWallet
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
from accounts.models import UserActivityLog
from waitlist import serializer

from .models import (
    CompetitionCumulativeMarketReturns,
    CompetitionMarketReturns,
    DailyReturns2,
    DemoCumulativeReturns,
    DemoPosition,
    DemoPortfolio,
    DemoDailyReturns2,
    MarketReturns,
    CumulativeMarketReturns,
    Portfolio,
    Position,
    CumulativeReturns,
)
from competition.models import (
    Competition,
    CompetitionCumulativeReturns,
    CompetitionCumulativeReturns2,
    CompetitionDailyReturns2,
    CompetitionPosition,
    CompetitionDailyReturns,
    CompetitionPortfolio,
    CompetitionTransaction,
)
from django.contrib.auth import get_user_model
from . import serializers as exec_serializer
from competition import (
    tasks as competition_task,
    models as competion_models,
    serializers as competition_serializer_module,
)
from portfolio.utils import get_stockdata2

User = get_user_model()
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

    def get(self, request):
        competition = Competition.objects.filter(status="current").first()
        portfolio = None

        if competition:
            portfolio = CompetitionPortfolio.objects.filter(
                user=request.user, competition=competition, active=True
            ).first()

        if portfolio and timezone.now() > competition.start_date:
            positions = CompetitionPosition.objects.filter(
                portfolio=portfolio, status="open"
            )
        else:
            positions = DemoPosition.objects.filter(
                portfolio__user=request.user, status="open"
            )

        def get_position(position):
            # print(position.id)
            pl, cur_val, price = position.calculate_profit_loss()
            symbol = position.stock.symbol

            if position.amount_invested != 0:
                percent = round((pl / position.amount_invested) * 100, 2)
                data1 = {
                    "id": position.id,
                    "symbol": symbol,
                    "open_pl": round(pl, 2),
                    "pl_percent": percent,
                    "created": position.created,
                    "status": position.status,
                    "open_price": position.open_price,
                    "order_id": position.order_id,
                }

            else:
                data1 = {
                    "id": position.id,
                    "symbol": symbol,
                    "open_pl": 0,
                    "pl_percent": 0,
                    "created": position.created,
                    "status": position.status,
                    "open_price": position.open_price,
                    "order_id": position.order_id,
                }
            return data1

        with ThreadPoolExecutor() as executor:
            futures = executor.map(get_position, positions)
            position_data_list = [result for result in futures if result]

            return Response(position_data_list)

    def post(self, request):

        symbol = request.data.get("symbol")
        order_id = request.data.get("order_id")
        quantity = int(request.data.get("quantity"))
        device_type = request.data.get("device_type", None)
        if request.data.get("price"):
            price = float(request.data.get("price"))
        action = request.data.get("action")
        time_in_force = request.data.get(
            "time_in_force", "day"
        )  # Default to Good 'Til Canceled
        is_buy = action == "buy"
        order_type = request.data.get("order_type")

        # print(order_type)

        stock = get_object_or_404(Stock, symbol=symbol)
        competition = Competition.objects.filter(status="current").first()

        in_competition = CompetitionPortfolio.objects.filter(
            user=request.user, competition=competition, active=True
        ).first()
        if in_competition and timezone.now() > competition.start_date:
            portfolio = in_competition
            if order_type == "market":
                market_price = round(Decimal(get_price(symbol)["current_price"]), 2)
                amount = quantity * market_price

                balance = portfolio.balance
                trade_commission = round(Decimal(0.00435) * amount, 2) + 200

                total = amount + trade_commission
                if balance >= total:
                    position = CompetitionPosition.objects.create(
                        portfolio=portfolio,
                        stock=stock,
                        status=CompetitionPosition.OPEN,
                        open_price=market_price,
                        quantity=quantity,
                        amount_invested=amount,
                        order_id=order_id,
                    )

                    if not is_buy:
                        position.action = "sell"
                        position.save()

                    CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type="open trade",
                        amount=amount,
                        status="completed",
                    )
                    CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type="trade commission",
                        amount=trade_commission,
                        status="completed",
                    )

                    portfolio.balance -= total
                    portfolio.save()

                    activity = UserActivityLog.objects.create(
                        user=request.user,
                        action_type="competition_open_trade",
                        description=f"User opened competition trade with amount {amount} on symbol {symbol}.",
                        device_type=device_type,
                    )
                    positions = CompetitionPosition.objects.filter(
                        portfolio=portfolio, status="open"
                    )

                    def get_position(position):
                        pl, cur_val, price = position.calculate_profit_loss()
                        symbol = position.stock.symbol

                        percent = round((pl / position.amount_invested) * 100, 2)
                        data1 = {
                            "id": position.id,
                            "symbol": symbol,
                            "open_pl": pl,
                            "pl_percent": percent,
                            "created": position.created,
                        }
                        return data1

                    # with ThreadPoolExecutor() as executor:
                    #     futures = executor.map(get_position, positions)
                    #     position_data_list = [result for result in futures if result]

                    save_and_send_notification(
                        request.user.id,
                        f" COMPETITION: You opened position {quantity} units of {stock.symbol} at {position.open_price} per unit. Total value:{quantity * position.open_price}naira ",
                    )

                    return Response(
                        {"message": f"{action.title()} order placed successfully."},
                        status=status.HTTP_201_CREATED,
                    )
                else:
                    return Response(
                        {"error": "Insufficient funds to trade."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif order_type == "limit":

                position = CompetitionPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=CompetitionPosition.PENDING,
                    limit_price=price,
                    quantity=quantity,
                    alert_name="pending trade" + shortuuid.uuid(),
                    time_in_force=time_in_force,
                    order_id=order_id,
                    order_type="limit",
                )

                # schedule, created = IntervalSchedule.objects.get_or_create(
                #     every=3,
                #     period=IntervalSchedule.MINUTES,
                # )

                # if not is_buy:
                #     position.action = "sell"
                #     position.save()

                # task = PeriodicTask.objects.create(
                #     interval=schedule,
                #     name=position.alert_name,
                #     task="execution.tasks.process_limit_order",
                #     args=json.dumps([position.id, True]),
                # )

                # positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='open',active=True)

                # def get_position(position):
                #     pl, cur_val,price = position.calculate_profit_loss()
                #     symbol=position.stock.symbol

                #     percent = round((pl/position.amount_invested) * 100,2)
                #     data1 = {
                #         'id':position.id,
                #         'symbol':symbol,
                #         'open_pl':pl,
                #         'pl_percent': percent,
                #         'created':position.created,
                #         'order_id':position.order_id,

                #     }
                #     return data1

                # with ThreadPoolExecutor() as executor:
                #     futures = executor.map(get_position, positions)
                #     position_data_list = [result for result in futures if result]

                save_and_send_notification(
                    request.user.id,
                    f" COMPETITION: Your limit order will be opened when the condition you set is met.",
                )

                return Response(
                    {"message": f"{action.title()} order scheduled successfully."},
                    status=status.HTTP_201_CREATED,
                )

        else:
            portfolio = DemoPortfolio.objects.filter(user=request.user).first()

            if order_type == "market":
                market_price = round(Decimal(get_price(symbol)["current_price"]), 2)
                amount = quantity * market_price

                position = DemoPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=DemoPosition.OPEN,
                    open_price=market_price,
                    quantity=quantity,
                    amount_invested=amount,
                    order_id=order_id,
                )

                if not is_buy:
                    position.action = "sell"
                    position.save()

                DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type="open trade",
                    amount=quantity * market_price,
                    status="completed",
                )
                activity = UserActivityLog.objects.create(
                    user=request.user,
                    action_type="demo_open_trade",
                    description=f"User opened demo trade with amount {amount} on symbol {symbol}.",
                    device_type=device_type,
                )
                positions = DemoPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )

                def get_position(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    if position.amount_invested != 0:
                        percent = round((pl / position.amount_invested) * 100, 2)
                        data1 = {
                            "id": position.id,
                            "symbol": symbol,
                            "open_pl": pl,
                            "pl_percent": percent,
                            "created": position.created,
                        }
                    else:
                        data1 = {
                            "id": position.id,
                            "symbol": symbol,
                            "open_pl": 0,
                            "pl_percent": 0,
                            "created": position.created,
                        }
                    return data1

                # with ThreadPoolExecutor() as executor:
                #     futures = executor.map(get_position, positions)
                #     position_data_list = [result for result in futures if result]

                save_and_send_notification(
                    request.user.id,
                    f" DEMO: You opened position {quantity} units of {stock.symbol} at {position.open_price} per unit. Total value:{quantity * position.open_price}naira ",
                )

                return Response(
                    {"message": f"{action.title()} order placed successfully."},
                    status=status.HTTP_201_CREATED,
                )

            elif order_type == "limit":

                position = DemoPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=DemoPosition.PENDING,
                    limit_price=price,
                    quantity=quantity,
                    alert_name=shortuuid.uuid(),
                    time_in_force=time_in_force,
                    order_id=order_id,
                    order_type="limit",
                )

                schedule, created = IntervalSchedule.objects.get_or_create(
                    every=3,
                    period=IntervalSchedule.MINUTES,
                )

                if not is_buy:
                    position.action = "sell"
                    position.save()

                task = PeriodicTask.objects.create(
                    interval=schedule,
                    name=position.alert_name,
                    task="execution.tasks.process_limit_order",
                    args=json.dumps([position.id]),
                )

                positions = DemoPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )

                def get_position(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol

                    if position.amount_invested != 0:
                        percent = round((pl / position.amount_invested) * 100, 2)
                        data1 = {
                            "id": position.id,
                            "symbol": symbol,
                            "open_pl": pl,
                            "pl_percent": percent,
                            "created": position.created,
                            "order_id": position.order_id,
                        }
                    else:
                        data1 = {
                            "id": position.id,
                            "symbol": symbol,
                            "open_pl": 0,
                            "pl_percent": 0,
                            "created": position.created,
                            "order_id": position.order_id,
                        }
                    return data1

                # with ThreadPoolExecutor() as executor:
                #     futures = executor.map(get_position, positions)
                #     position_data_list = [result for result in futures if result]

                save_and_send_notification(
                    request.user.id,
                    f" DEMO: Your limit order will be opened when the condition you set is met.",
                )

                return Response(
                    {"message": f"{action.title()} order scheduled successfully."},
                    status=status.HTTP_201_CREATED,
                )


class SupportDemoTradeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get("email")
        user = User.objects.get(email=email)

        competition = Competition.objects.filter(status="current").first()
        portfolio = None

        if competition:
            portfolio = CompetitionPortfolio.objects.filter(
                user=user, competition=competition, active=True
            ).first()

        if portfolio and timezone.now() > competition.start_date:
            positions = CompetitionPosition.objects.filter(
                portfolio=portfolio, status="open"
            )
        else:
            positions = DemoPosition.objects.filter(portfolio__user=user, status="open")

        def get_position(position):
            # print(position.id)
            pl, cur_val, price = position.calculate_profit_loss()
            symbol = position.stock.symbol

            if position.amount_invested != 0:
                percent = round((pl / position.amount_invested) * 100, 2)
                data1 = {
                    "id": position.id,
                    "symbol": symbol,
                    "open_pl": round(pl, 2),
                    "pl_percent": percent,
                    "created": position.created,
                    "status": position.status,
                    "open_price": position.open_price,
                    "order_id": position.order_id,
                }

            else:
                data1 = {
                    "id": position.id,
                    "symbol": symbol,
                    "open_pl": 0,
                    "pl_percent": 0,
                    "created": position.created,
                    "status": position.status,
                    "open_price": position.open_price,
                    "order_id": position.order_id,
                }
            return data1

        with ThreadPoolExecutor() as executor:
            futures = executor.map(get_position, positions)
            position_data_list = [result for result in futures if result]

            return Response(position_data_list)


class Home(APIView):
    def get(self, request, *args, **kwargs):
        mode = self.kwargs.get("mode")
        if mode == "demo":
            competition = Competition.objects.filter(status="current").first()

            in_competition = CompetitionPortfolio.objects.filter(
                user=request.user, competition=competition, active=True
            ).first()
            if in_competition and timezone.now() > competition.start_date:
                portfolio = in_competition

                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                positions2 = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    {"profit_loss": profit_loss, "date": date}
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item["date"] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {
                        "profit_loss": position_data_dict.get(date, 0),
                        "date": date.strftime("%Y-%m-%d"),
                    }
                    for date in (
                        start_date + timedelta(n)
                        for n in range((today.date() - start_date).days + 1)
                        if (start_date + timedelta(n)).weekday() < 5
                    )
                ]
                profit_loss2 = sum([pos.profit_loss for pos in positions2])

                balance = portfolio.balance

                def pl_cv(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    print(pl)
                    data2 = {"stock": symbol, "current_value": round(cur_val, 2)}

                    return pl, data2

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]

                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]

                profit_loss = sum(profit_loss_list) if profit_loss_list else 0

                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss = CompetitionDailyReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")
                cumulative_profitloss = CompetitionCumulativeReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")

                market = CompetitionMarketReturns.objects.all()
                cumulative_market = CompetitionCumulativeMarketReturns.objects.all()

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for daily in daily_profitloss:
                        for daily2 in market:
                            if daily.created.date() == daily2.created.date():
                                overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    if overview:
                        first = overview[0]
                        if first["portfolio_returns"] == 0:
                            first["market_returns"] = 0

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    # print('cpl', cumulative_profitloss)

                    for daily in cumulative_profitloss:
                        for daily2 in cumulative_market:
                            if daily.created.date() == daily2.created.date():
                                cumulative_overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    # print('cumu',cumulative_overview)
                    if cumulative_overview:
                        first_ = cumulative_overview[0]
                        if first_["portfolio_returns"] == 0:
                            first_["market_returns"] = 0

                equity1 = round(balance + profit_loss, 2)
                equity = equity1 if equity1 >= 0 else 0

                calendar = [
                    {
                        "date": daily.created.date(),
                        "return": daily.portfolio_returns,
                    }
                    for daily in daily_profitloss
                    if daily_profitloss.count() > 1
                    and daily.created > competition.start_date
                ]
                open_balance = sum([position.amount_invested for position in positions])
                data = {
                    "balance": round(balance + open_balance, 2),
                    "starting_balance": 1000000,
                    "equity": equity + open_balance,
                    "floating_pl": profit_loss,
                    "closed_pl": profit_loss2,
                    # 'positions': position_data_list2,
                    "positions": final_list,
                    # 'open_positions': position_data_list,
                    "current_value": current_value_list,
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                    "calendar": calendar,
                }

                return Response(data)
            else:
                portfolio = DemoPortfolio.objects.filter(user=request.user).first()
                positions = DemoPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                positions2 = DemoPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    {"profit_loss": profit_loss, "date": date}
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item["date"] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {
                        "profit_loss": position_data_dict.get(date, 0),
                        "date": date.strftime("%Y-%m-%d"),
                    }
                    for date in (
                        start_date + timedelta(n)
                        for n in range((today.date() - start_date).days + 1)
                        if (start_date + timedelta(n)).weekday() < 5
                    )
                ]
                profit_loss2 = sum([pos.profit_loss for pos in positions2])

                balance = portfolio.balance

                def pl_cv(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    print(pl)
                    data2 = {"stock": symbol, "current_value": round(cur_val, 2)}

                    return pl, data2

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]

                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]

                profit_loss = sum(profit_loss_list) if profit_loss_list else 0

                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss = DemoDailyReturns2.objects.filter(
                    user=request.user
                ).order_by("created")
                cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                    user=request.user
                ).order_by("created")

                market = MarketReturns.objects.all()
                cumulative_market = CumulativeMarketReturns.objects.all()

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for daily in daily_profitloss:
                        for daily2 in market:
                            if daily.created.date() == daily2.created.date():
                                overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    if overview:
                        first = overview[0]
                        if first["portfolio_returns"] == 0:
                            first["market_returns"] = 0

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    # print('cpl', cumulative_profitloss)

                    for daily in cumulative_profitloss:
                        for daily2 in cumulative_market:
                            if daily.created.date() == daily2.created.date():
                                cumulative_overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    # print('cumu',cumulative_overview)
                    if cumulative_overview:
                        first_ = cumulative_overview[0]
                        if first_["portfolio_returns"] == 0:
                            first_["market_returns"] = 0

                equity1 = round(balance + profit_loss, 2)
                equity = equity1 if equity1 >= 0 else 0

                calendar = [
                    {
                        "date": daily.created.date(),
                        "return": daily.portfolio_returns,
                    }
                    for daily in daily_profitloss
                ]
                open_balance = sum([position.amount_invested for position in positions])
                data = {
                    "balance": round(balance + open_balance, 2),
                    "starting_balance": None,
                    "equity": equity + open_balance,
                    "floating_pl": profit_loss,
                    "closed_pl": profit_loss2,
                    # 'positions': position_data_list2,
                    "positions": final_list,
                    # 'open_positions': position_data_list,
                    "current_value": current_value_list,
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                    "calendar": calendar,
                }

                return Response(data)


class SupportHome(APIView):
    def get(self, request, *args, **kwargs):
        mode = self.kwargs.get("mode")
        email = self.kwargs.get("email")
        user = User.objects.get(email=email)

        if mode == "demo":
            competition = Competition.objects.filter(status="current").first()

            in_competition = CompetitionPortfolio.objects.filter(
                user=user, competition=competition, active=True
            ).first()
            if in_competition and timezone.now() > competition.start_date:
                portfolio = in_competition

                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                positions2 = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    {"profit_loss": profit_loss, "date": date}
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item["date"] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {
                        "profit_loss": position_data_dict.get(date, 0),
                        "date": date.strftime("%Y-%m-%d"),
                    }
                    for date in (
                        start_date + timedelta(n)
                        for n in range((today.date() - start_date).days + 1)
                        if (start_date + timedelta(n)).weekday() < 5
                    )
                ]
                profit_loss2 = sum([pos.profit_loss for pos in positions2])

                balance = portfolio.balance

                def pl_cv(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    print(pl)
                    data2 = {"stock": symbol, "current_value": round(cur_val, 2)}

                    return pl, data2

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]

                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]

                profit_loss = sum(profit_loss_list) if profit_loss_list else 0

                daily_profitloss = CompetitionDailyReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")
                cumulative_profitloss = CompetitionCumulativeReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")

                market = CompetitionMarketReturns.objects.all()
                cumulative_market = CompetitionCumulativeMarketReturns.objects.all()

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for daily in daily_profitloss:
                        for daily2 in market:
                            if daily.created.date() == daily2.created.date():
                                overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    if overview:
                        first = overview[0]
                        if first["portfolio_returns"] == 0:
                            first["market_returns"] = 0

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    # print('cpl', cumulative_profitloss)

                    for daily in cumulative_profitloss:
                        for daily2 in cumulative_market:
                            if daily.created.date() == daily2.created.date():
                                cumulative_overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    # print('cumu',cumulative_overview)
                    if cumulative_overview:
                        first_ = cumulative_overview[0]
                        if first_["portfolio_returns"] == 0:
                            first_["market_returns"] = 0

                equity1 = round(balance + profit_loss, 2)
                equity = equity1 if equity1 >= 0 else 0

                calendar = [
                    {
                        "date": daily.created.date(),
                        "return": daily.portfolio_returns,
                    }
                    for daily in daily_profitloss
                    if daily_profitloss.count() > 1
                ]
                open_balance = sum([position.amount_invested for position in positions])
                data = {
                    "balance": round(balance + open_balance, 2),
                    "starting_balance": 1000000,
                    "equity": equity + open_balance,
                    "floating_pl": profit_loss,
                    "closed_pl": profit_loss2,
                    # 'positions': position_data_list2,
                    "positions": final_list,
                    # 'open_positions': position_data_list,
                    "current_value": current_value_list,
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                    "calendar": calendar,
                }

                return Response(data)

            else:
                portfolio = DemoPortfolio.objects.filter(user=user).first()
                positions = DemoPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                positions2 = DemoPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    {"profit_loss": profit_loss, "date": date}
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item["date"] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {
                        "profit_loss": position_data_dict.get(date, 0),
                        "date": date.strftime("%Y-%m-%d"),
                    }
                    for date in (
                        start_date + timedelta(n)
                        for n in range((today.date() - start_date).days + 1)
                        if (start_date + timedelta(n)).weekday() < 5
                    )
                ]
                profit_loss2 = sum([pos.profit_loss for pos in positions2])

                balance = portfolio.balance

                def pl_cv(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    print(pl)
                    data2 = {"stock": symbol, "current_value": round(cur_val, 2)}

                    return pl, data2

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]

                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]

                profit_loss = sum(profit_loss_list) if profit_loss_list else 0

                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss = DemoDailyReturns2.objects.filter(user=user)
                cumulative_profitloss = DemoCumulativeReturns.objects.filter(user=user)

                market = MarketReturns.objects.all()
                cumulative_market = CumulativeMarketReturns.objects.all()

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for daily in daily_profitloss:
                        for daily2 in market:
                            if daily.created.date() == daily2.created.date():
                                overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    if overview:
                        first = overview[0]
                        if first["portfolio_returns"] == 0:
                            first["market_returns"] = 0

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    # print('cpl', cumulative_profitloss)

                    for daily in cumulative_profitloss:
                        for daily2 in cumulative_market:
                            if daily.created.date() == daily2.created.date():
                                cumulative_overview.append(
                                    {
                                        "portfolio_returns": daily.portfolio_returns,
                                        "market_returns": daily2.market_returns,
                                        "date": daily.created.date(),
                                    }
                                )
                    # print('cumu',cumulative_overview)
                    if cumulative_overview:
                        first_ = cumulative_overview[0]
                        if first_["portfolio_returns"] == 0:
                            first_["market_returns"] = 0

                equity1 = round(balance + profit_loss, 2)
                equity = equity1 if equity1 >= 0 else 0

                calendar = [
                    {
                        "date": daily.created.date(),
                        "return": daily.portfolio_returns,
                    }
                    for daily in daily_profitloss
                    if daily_profitloss.count() > 1
                ]
                open_balance = sum([position.amount_invested for position in positions])
                data = {
                    "balance": round(balance + open_balance, 2),
                    "starting_balance": 1000000,
                    "equity": equity + open_balance,
                    "floating_pl": profit_loss,
                    "closed_pl": profit_loss2,
                    # 'positions': position_data_list2,
                    "positions": final_list,
                    # 'open_positions': position_data_list,
                    "current_value": current_value_list,
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                    "calendar": calendar,
                }

                return Response(data)


class DemoCloseTrade(APIView):
    def post(self, request, *args, **kwargs):
        id = self.kwargs.get("id")
        device_type = request.data.get("device_type", None)
        competition = Competition.objects.filter(status="current").first()

        in_competition = CompetitionPortfolio.objects.filter(
            user=request.user, competition=competition, active=True
        ).first()
        if in_competition and timezone.now() > competition.start_date:
            position = get_object_or_404(CompetitionPosition, id=id)
            if position.status == "open":
                pl, cur_val, price = position.calculate_profit_loss()

                position.status = "close"
                position.close_price = Decimal(price)
                position.profit_loss = pl
                position.save()

                CompetitionTransaction.objects.create(
                    user=request.user,
                    transaction_type="close trade",
                    amount=cur_val,
                    status="completed",
                )
                activity = UserActivityLog.objects.create(
                    user=request.user,
                    action_type="competition_closed_trade",
                    description=f"User closed competition trade with symbol {position.stock.symbol}.",
                    device_type=device_type,
                )
                position.portfolio.balance += (
                    position.amount_invested + position.profit_loss
                )
                position.portfolio.save()

                data = {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": position.close_price,
                    "open_time": position.created.isoformat(),
                    "close_time": position.updated.isoformat(),
                    "profit_loss": position.profit_loss,
                    "order_id": position.order_id,
                }
                return Response(data)
            else:
                return Response("Position is already closed")
        else:
            position = get_object_or_404(DemoPosition, id=id)
            if position.status == "open":
                pl, cur_val, price = position.calculate_profit_loss()

                position.status = "close"
                position.close_price = Decimal(price)
                position.profit_loss = pl
                position.save()

                DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type="close trade",
                    amount=cur_val,
                    status="completed",
                )
                activity = UserActivityLog.objects.create(
                    user=request.user,
                    action_type="demo_closed_trade",
                    description=f"User closed demo trade with symbol {position.stock.symbol}.",
                    device_type=device_type,
                )
                position.portfolio.balance += (
                    position.amount_invested + position.profit_loss
                )
                position.portfolio.save()

                data = {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": position.close_price,
                    "open_time": position.created.isoformat(),
                    "close_time": position.updated.isoformat(),
                    "profit_loss": position.profit_loss,
                    "order_id": position.order_id,
                }
                return Response(data)
            else:
                return Response("Position is not open")


class DemoClosePendingTrade(APIView):
    def post(self, request, *args, **kwargs):
        id = self.kwargs.get("id")
        device_type = request.data.get("device_type", None)
        competition = Competition.objects.filter(status="current").first()

        in_competition = CompetitionPortfolio.objects.filter(
            user=request.user, competition=competition, active=True
        ).first()
        if in_competition and timezone.now() > competition.start_date:
            position = get_object_or_404(CompetitionPosition, id=id)
            if position.status == "pending":

                position.status = "cancelled"
                position.save()

                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()

                activity = UserActivityLog.objects.create(
                    user=request.user,
                    action_type="competition_cancel_trade",
                    description=f"User cancelled competition pending trade with symbol {position.stock.symbol}.",
                    device_type=device_type,
                )

                data = {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": position.close_price,
                    "open_time": position.created.isoformat(),
                    "close_time": position.updated.isoformat(),
                    "profit_loss": position.profit_loss,
                    "order_id": position.order_id,
                }
                return Response(data)
            else:
                return Response("Position is already cancelled")
        else:
            position = get_object_or_404(DemoPosition, id=id)
            if position.status == "pending":

                position.status = "cancelled"

                position.save()

                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()

                UserActivityLog.objects.create(
                    user=request.user,
                    action_type="demo_closed_pending_trade",
                    description=f"User cancelled  demo pending trade with symbol {position.stock.symbol}.",
                    device_type=device_type,
                )

                data = {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": position.close_price,
                    "open_time": position.created.isoformat(),
                    "close_time": position.updated.isoformat(),
                    "profit_loss": position.profit_loss,
                    "order_id": position.order_id,
                }
                return Response(data)
            else:
                return Response("Position is not open")


class DemoHolding(APIView):
    def get(self, request):
        competition = Competition.objects.filter(status="current").first()

        in_competition = CompetitionPortfolio.objects.filter(
            user=request.user, competition=competition, active=True
        ).first()
        if in_competition and timezone.now() > competition.start_date:
            portfolio = in_competition

            positions = CompetitionPosition.objects.filter(
                portfolio=portfolio
            ).order_by("-updated")
            balance = portfolio.balance

            if positions:

                def get_position(position):

                    pl, value, price = position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl / position.amount_invested * 100, 2)
                    else:
                        percent_change = None

                    if position.status == "open":
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "shares": position.quantity,
                        "avg_cost": position.open_price,
                        "close_price": position.close_price,
                        "ltp": price,
                        "open_time": position.created.isoformat(),
                        "close_time": (
                            position.updated.isoformat()
                            if position.updated != position.created
                            else "-"
                        ),
                        "change": pl,
                        "percent_change": percent_change,
                        "cur_val": value,
                        "avg_volume": "3300",
                        "volume": "66000",
                        "status": position.status,
                        "invested": position.amount_invested,
                        "profit_loss": profit_loss,
                        "side": position.action,
                        "order": position.order_type,
                        "order_id": position.order_id,
                    }
                    return data

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                # wallet_balance = portfolio.balance
                # open_balance = open_trade_sum
                positions_open = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                open_balance = sum(
                    [position.amount_invested for position in positions_open]
                )

                hold_data = {
                    "balance": balance + open_balance,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": balance + floating_pl + open_balance,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "balance": 0,
                    "floating_pl": 0,
                    "closed_pl": 0,
                    "equity": 0,
                    "holdings": [],
                }

                return Response(hold_data)
        else:
            portfolio = DemoPortfolio.objects.filter(user=request.user).first()
            positions = DemoPosition.objects.filter(portfolio=portfolio).order_by(
                "-updated"
            )
            balance = portfolio.balance

            if positions:

                def get_position(position):

                    pl, value, price = position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl / position.amount_invested * 100, 2)
                    else:
                        percent_change = None

                    if position.status == "open":
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "shares": position.quantity,
                        "avg_cost": position.open_price,
                        "close_price": position.close_price,
                        "ltp": price,
                        "open_time": position.created.isoformat(),
                        "close_time": (
                            position.updated.isoformat()
                            if position.updated != position.created
                            else "-"
                        ),
                        "change": pl,
                        "percent_change": percent_change,
                        "cur_val": value,
                        "avg_volume": "3300",
                        "volume": "66000",
                        "status": position.status,
                        "invested": position.amount_invested,
                        "profit_loss": profit_loss,
                        "side": position.action,
                        "order": position.order_type,
                        "order_id": position.order_id,
                    }
                    return data

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                # wallet_balance = portfolio.balance
                open_balance = open_trade_sum

                hold_data = {
                    "balance": balance + open_balance,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": balance + floating_pl + open_balance,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "balance": 0,
                    "floating_pl": 0,
                    "closed_pl": 0,
                    "equity": 0,
                    "holdings": [],
                }

                return Response(hold_data)


from accounts.models import CustomUser


class SupportDemoHolding(APIView):
    def get(self, request, *args, **kwargs):
        email = kwargs.get("email")
        print(email)
        user = CustomUser.objects.get(email=email)

        competition = Competition.objects.filter(status="current").first()

        in_competition = CompetitionPortfolio.objects.filter(
            user=user, competition=competition, active=True
        ).first()
        if in_competition and timezone.now() > competition.start_date:
            portfolio = in_competition

            positions = CompetitionPosition.objects.filter(
                portfolio=portfolio
            ).order_by("-updated")
            balance = portfolio.balance

            if positions:

                def get_position(position):

                    pl, value, price = position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl / position.amount_invested * 100, 2)
                    else:
                        percent_change = None

                    if position.status == "open":
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "shares": position.quantity,
                        "avg_cost": position.open_price,
                        "close_price": position.close_price,
                        "ltp": price,
                        "open_time": position.created.isoformat(),
                        "close_time": (
                            position.updated.isoformat()
                            if position.updated != position.created
                            else "-"
                        ),
                        "change": pl,
                        "percent_change": percent_change,
                        "cur_val": value,
                        "avg_volume": "3300",
                        "volume": "66000",
                        "status": position.status,
                        "invested": position.amount_invested,
                        "profit_loss": profit_loss,
                        "side": position.action,
                        "order": position.order_type,
                        "order_id": position.order_id,
                    }
                    return data

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                # wallet_balance = portfolio.balance
                positions_open = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                open_balance = sum(
                    [position.amount_invested for position in positions_open]
                )

                hold_data = {
                    "balance": balance + open_balance,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": balance + floating_pl + open_balance,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "balance": 0,
                    "floating_pl": 0,
                    "closed_pl": 0,
                    "equity": 0,
                    "holdings": [],
                }

                return Response(hold_data)
        else:
            portfolio = DemoPortfolio.objects.filter(user=user).first()
            positions = DemoPosition.objects.filter(portfolio=portfolio).order_by(
                "-updated"
            )
            balance = portfolio.balance

            if positions:

                def get_position(position):

                    pl, value, price = position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl / position.amount_invested * 100, 2)
                    else:
                        percent_change = None

                    if position.status == "open":
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "shares": position.quantity,
                        "avg_cost": position.open_price,
                        "close_price": position.close_price,
                        "ltp": price,
                        "open_time": position.created.isoformat(),
                        "close_time": (
                            position.updated.isoformat()
                            if position.updated != position.created
                            else "-"
                        ),
                        "change": pl,
                        "percent_change": percent_change,
                        "cur_val": value,
                        "avg_volume": "3300",
                        "volume": "66000",
                        "status": position.status,
                        "invested": position.amount_invested,
                        "profit_loss": profit_loss,
                        "side": position.action,
                        "order": position.order_type,
                        "order_id": position.order_id,
                    }
                    return data

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                # wallet_balance = portfolio.balance
                balance = open_trade_sum + closed_trade_sum + closed_pl

                positions_open = DemoPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                open_balance = sum(
                    [position.amount_invested for position in positions_open]
                )

                hold_data = {
                    "balance": balance + open_balance,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": balance + floating_pl + open_balance,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "balance": 0,
                    "floating_pl": 0,
                    "closed_pl": 0,
                    "equity": 0,
                    "holdings": [],
                }

                return Response(hold_data)


class DemoHolding2(APIView):
    def get(self, request):
        def get_price():
            from portfolio.utils import connect_to_mongodb

            db = connect_to_mongodb("stock_prices")
            collection = db["price_combined"]
            last_item = collection.find_one(sort=[("_id", -1)])
            # print(symbol)
            return last_item

        all_prices = get_price()

        in_competition = CompetitionPortfolio.objects.filter(
            user=request.user, competition__status="current", active=True
        ).first()
        if in_competition:
            portfolio = in_competition

            positions = CompetitionPosition.objects.filter(
                portfolio=portfolio
            ).order_by("-updated")
            balance = portfolio.balance

            if positions:

                def get_position(position):
                    if position.status == "close":
                        # pl, value, price= position.calculate_profit_loss()
                        # print("plv",pl, value, price)
                        pl = position.profit_loss

                        if position.amount_invested != 0:
                            percent_change = round(
                                pl / position.amount_invested * 100, 2
                            )
                        else:
                            percent_change = None
                        price = all_prices[position.stock.symbol]["current_price"]
                        value = round(position.quantity * price, 2)

                        data = {
                            "id": position.id,
                            "stock": position.stock.symbol,
                            "shares": position.quantity,
                            "avg_cost": position.open_price,
                            "close_price": position.close_price,
                            "ltp": price,
                            "open_time": position.created.isoformat(),
                            "close_time": (
                                position.updated.isoformat()
                                if position.updated != position.created
                                else "-"
                            ),
                            "change": pl,
                            "percent_change": percent_change,
                            "cur_val": value,
                            "avg_volume": "3300",
                            "volume": "66000",
                            "status": position.status,
                            "invested": position.amount_invested,
                            "profit_loss": position.profit_loss,
                            "side": position.action,
                            "order": position.order_type,
                            "order_id": position.order_id,
                        }
                    return data

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                # closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance

                hold_data = {
                    "balance": open_trade_sum,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": open_trade_sum + floating_pl,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "portfolio_value": 0,
                    "profit_loss": 0,
                    "total_invested": 0,
                    "holdings": [],
                }

                return Response(hold_data)
        else:
            portfolio = DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions = DemoPosition.objects.filter(portfolio=portfolio).order_by(
                "-updated"
            )
            balance = portfolio.balance

            if positions:

                def get_position(position):

                    pl, value, price = position.calculate_profit_loss()
                    # print("plv",pl, value, price)
                    if position.amount_invested != 0:
                        percent_change = round(pl / position.amount_invested * 100, 2)
                    else:
                        percent_change = None

                    if position.status == "open":
                        profit_loss = pl
                    else:
                        profit_loss = position.profit_loss
                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "shares": position.quantity,
                        "avg_cost": position.open_price,
                        "close_price": position.close_price,
                        "ltp": price,
                        "open_time": position.created.isoformat(),
                        "close_time": (
                            position.updated.isoformat()
                            if position.updated != position.created
                            else "-"
                        ),
                        "change": pl,
                        "percent_change": percent_change,
                        "cur_val": value,
                        "avg_volume": "3300",
                        "volume": "66000",
                        "status": position.status,
                        "invested": position.amount_invested,
                        "profit_loss": profit_loss,
                        "side": position.action,
                        "order": position.order_type,
                        "order_id": position.order_id,
                    }
                    return data

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(get_position, positions)
                    positions_data = [result for result in futures if result]

                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                # closed_trade_sum = sum([data['invested'] for data in positions_data if data['status']=='close'])
                # wallet_balance = portfolio.balance

                hold_data = {
                    "balance": open_trade_sum,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": open_trade_sum + floating_pl,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "portfolio_value": 0,
                    "profit_loss": 0,
                    "total_invested": 0,
                    "holdings": [],
                }

                return Response(hold_data)


class CreatCompetitionAccount(APIView):
    serializer_class = (
        competition_serializer_module.CompetitionPortfolioCreateSerializers
    )

    def post(self, request):
        # get the correct competition
        try:
            competition = competion_models.Competition.objects.get(status="current")
        except Competition.DoesNotExist:
            return Response(
                {"detail": "There is no ongoing competition"},
                status=status.HTTP_404_NOT_FOUND,
            )

        clan_query = competion_models.Clan.objects.filter(clan_admin=request.user)
        clan_query2 = competion_models.Clan.objects.filter(member=request.user)
        if not (clan_query2.exists() or clan_query.exists()):

            # save_and_send_notification(request.user.id, "You need to be in a clan to join competition. Create or join one clan.")
            return Response(
                {
                    "detail": "You need to be in a clan to join competition. Create or join one clan."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if competition.end_date - timezone.now() < timedelta(weeks=2):
            return Response(
                {
                    "detail": "You can only join the competition up to 2 weeks before the end"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        portfolio = CompetitionPortfolio.objects.filter(
            competition=competition, user=request.user
        ).first()
        if portfolio:
            if portfolio.active:
                return Response(
                    {"detail": "You already  have account in this competition."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                return Response(
                    {
                        "detail": "You have already exited this competition. You cannot create account in this competition again."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            portfolio = serializer.save(
                user=request.user, competition=competition, balance=1000000
            )
            competition_task.create_returns.delay(portfolio.id)
            save_and_send_notification(
                portfolio.user.id, "You have joined the ongoing competition. Goodluck!"
            )
            return Response(
                {
                    "detail": "You have successfully joined this competition",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


class LeaveCompetion(APIView):

    def post(self, request):
        # get the correct competition
        try:
            competition = competion_models.Competition.objects.get(status="current")
        except Competition.DoesNotExist:
            return Response(
                {"detail": "There is no ongoing competition"},
                status=status.HTTP_404_NOT_FOUND,
            )

        portfolio = CompetitionPortfolio.objects.filter(
            competition=competition, user=request.user
        ).first()

        if not portfolio:
            return Response(
                {"detail": "You are not in this competition"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if portfolio.active:
            portfolio.active = False
            portfolio.save()
            return Response(
                {"detail": "You have successfully left this competition"},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"detail": "You have  already exited this competition"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RetrieveSIngleCompetitonAccount(APIView):
    serializer_class = (
        competition_serializer_module.CompetitionPortfolioCreateSerializers
    )

    def get_competition_account(self, id):
        portfolio = CompetitionPortfolio.objects.filter(id=id).first()
        return portfolio if portfolio else None

    def get(self, request, *args, **kwargs):
        id = kwargs.get("id")
        account = self.get_competition_account(id)
        if account is None:
            return Response(
                {"detail": "Competition account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if account.user != request.user:
            return Response(
                {"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        positions = CompetitionPosition.objects.filter(portfolio=account, status="open")

        open_balance = sum([position.amount_invested for position in positions])
        data = {
            "id": account.id,
            "account_name": account.account_name,
            "account_type": account.account_type,
            "balance": account.balance + open_balance,
            "user": account.user.id,
        }
        return Response(data)

    def put(self, request, *args, **kwargs):
        id = kwargs.get("id")
        account = self.get_competition_account(id)
        if account is None:
            return Response(
                {"detail": "Competition account not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if account.user != request.user:
            return Response(
                {"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.serializer_class(account, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


class DemoPorfoliosAccounts(APIView):
    serializer_class = exec_serializer.DemoPortfolioSerializer
    account_create_serializer = exec_serializer.DemoPortfolioCreateSerializer
    competition_serializer = (
        competition_serializer_module.CompetitionPortfolioCreateSerializers
    )

    def get(self, request):
        """_summary_

        Get competition account for the current competition. if no competiton return empty
        """

        competition_account = CompetitionPortfolio.objects.filter(
            user=request.user
        ).order_by("id")
        if competition_account.exists():
            competition_account = competition_account.last()

            compositions = CompetitionPosition.objects.filter(
                portfolio=competition_account, status="open"
            )
            com_open_balance = sum(
                [position.amount_invested for position in compositions]
            )
            comdata = {
                "id": competition_account.id,
                "account_name": competition_account.account_name,
                "account_type": competition_account.account_type,
                "balance": competition_account.balance + com_open_balance,
                "user": competition_account.user.id,
                "account_id": competition_account.account_id,
                "active": competition_account.active,
            }
        else:
            comdata = []

        demo_accounts = DemoPortfolio.objects.filter(user=request.user, is_prop=False)

        demo_data = []
        for accounts in demo_accounts:
            positions = DemoPosition.objects.filter(portfolio=accounts, status="open")
            # print(accounts.user)
            # print(positions)
            open_balance = sum([position.amount_invested for position in positions])
            data = {
                "id": accounts.id,
                "account_name": accounts.account_name,
                "account_type": accounts.account_type,
                "balance": accounts.balance + open_balance,
                "user": accounts.user.id,
                "account_id": accounts.account_id,
            }
            demo_data.append(data)

        prop_accounts = DemoPortfolio.objects.filter(
            user=request.user, is_prop=True, activated=True
        )
        prop_data = []
        for accounts in prop_accounts:
            positions = DemoPosition.objects.filter(portfolio=accounts, status="open")
            # print(accounts.user)
            # print(positions)
            open_balance = sum([position.amount_invested for position in positions])
            data = {
                "id": accounts.id,
                "account_name": accounts.account_name,
                "account_type": accounts.account_type,
                "balance": accounts.balance + open_balance,
                "user": accounts.user.id,
                "account_id": accounts.account_id,
                "activated": accounts.activated,
            }
            prop_data.append(data)

        # serializer = self.serializer_class(demo_accounts, many=True)
        return Response(
            {
                "demo_accounts": demo_data,
                "competition_account": comdata,
                "prop_accounts": prop_data,
            }
        )

    def post(self, request):

        demo_accounts = DemoPortfolio.objects.filter(
            user=request.user, is_prop=False
        ).count()
        if demo_accounts >= 10:
            return Response(
                "You can only have 10 demo acccounts", status.HTTP_400_BAD_REQUEST
            )
        serializer = self.account_create_serializer(data=request.data)
        account_exist = DemoPortfolio.objects.filter(
            account_name=request.data.get("account_name"), user=request.user
        ).exists()
        if account_exist:
            return Response("Duplicate name not allowed.", status.HTTP_400_BAD_REQUEST)
        if serializer.is_valid():
            serializer.save(user=request.user)

            portfolio = serializer.instance
            DemoDailyReturns2.objects.create(
                portfolio=portfolio, user=request.user, created=timezone.now()
            )
            DemoCumulativeReturns.objects.create(
                portfolio=portfolio, user=request.user, created=timezone.now()
            )
            # NewMarketReturns .objects.create(portfolio=portfolio,created=timezone.now())
            # NewCumulativeMarketReturns .objects.create(portfolio=portfolio, created=timezone.now())

            return Response(serializer.data)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


class SupportDemoPorfoliosAccounts(APIView):
    serializer_class = exec_serializer.DemoPortfolioSerializer
    account_create_serializer = exec_serializer.DemoPortfolioCreateSerializer
    competition_serializer = (
        competition_serializer_module.CompetitionPortfolioCreateSerializers
    )

    def get(self, request, *args, **kwargs):
        """_summary_

        Get competition account for the current competition. if no competiton return empty
        """
        email = kwargs.get("email")

        # competition = competion_models.Competition.objects.filter(status='current').first()
        # if competition:
        #     competition_account = CompetitionPortfolio.objects.filter(user__email=email,competition=competition)
        #     if competition_account.exists():
        #         competition_account = competition_account.first()

        #         compositions = CompetitionPosition.objects.filter(portfolio=competition_account, status='open')
        #         com_open_balance = sum([position.amount_invested for position in compositions])
        #         comdata = {
        #             "id": competition_account.id,
        #             'account_name':competition_account.account_name,
        #             "account_type":competition_account.account_type,
        #             "balance":competition_account.balance + com_open_balance,
        #             "user":competition_account.user.id,
        #             "account_id": competition_account.account_id,
        #             'active':competition_account.active
        #         }
        #     else:
        #         comdata = []
        # else:
        #     comdata = []

        competition_account = CompetitionPortfolio.objects.filter(
            user__email=email
        ).order_by("id")
        if competition_account.exists():
            competition_account = competition_account.last()

            compositions = CompetitionPosition.objects.filter(
                portfolio=competition_account, status="open"
            )
            com_open_balance = sum(
                [position.amount_invested for position in compositions]
            )
            comdata = {
                "id": competition_account.id,
                "account_name": competition_account.account_name,
                "account_type": competition_account.account_type,
                "balance": competition_account.balance + com_open_balance,
                "user": competition_account.user.id,
                "account_id": competition_account.account_id,
                "active": competition_account.active,
            }
        else:
            comdata = []

        demo_accounts = DemoPortfolio.objects.filter(user__email=email)
        demo_data = []
        for accounts in demo_accounts:
            positions = DemoPosition.objects.filter(portfolio=accounts, status="open")
            # print(accounts.user)
            # print(positions)
            open_balance = sum([position.amount_invested for position in positions])
            data = {
                "id": accounts.id,
                "account_name": accounts.account_name,
                "account_type": accounts.account_type,
                "balance": accounts.balance + open_balance,
                "user": accounts.user.id,
                "account_id": accounts.account_id,
            }
            demo_data.append(data)

        # serializer = self.serializer_class(demo_accounts, many=True)
        return Response({"demo_accounts": demo_data, "competition_account": comdata})


class PorfoliosAccounts(APIView):
    serializer_class = exec_serializer.PortfolioSerializer
    account_create_serializer = exec_serializer.PortfolioCreateSerializer

    def get(self, request):

        accounts = Portfolio.objects.filter(user=request.user)
        live_data = []
        for account in accounts:
            positions = Position.objects.filter(portfolio=account, status="open")
            # print(accounts.user)
            # print(positions)
            open_balance = sum([position.amount_invested for position in positions])
            data = {
                "id": account.id,
                "account_name": account.account_name,
                "account_type": account.account_type,
                "balance": account.balance + open_balance,
                "user": account.user.id,
                "account_id": account.account_id,
            }
            live_data.append(data)

        # serializer = self.serializer_class(demo_accounts, many=True)
        return Response({"accounts": live_data})

    def post(self, request):
        accounts = Portfolio.objects.filter(user=request.user).count()
        if accounts >= 10:
            return Response(
                "You can only have 10 live acccounts", status.HTTP_400_BAD_REQUEST
            )
        serializer = self.account_create_serializer(data=request.data)
        account_exist = Portfolio.objects.filter(
            account_name=request.data.get("account_name"), user=request.user
        ).exists()
        if account_exist:
            return Response("Duplicate name not allowed.", status.HTTP_400_BAD_REQUEST)
        if serializer.is_valid():
            serializer.save(user=request.user)

            portfolio = serializer.instance
            DailyReturns2.objects.create(
                portfolio=portfolio, user=request.user, created=timezone.now()
            )
            CumulativeReturns.objects.create(
                portfolio=portfolio, user=request.user, created=timezone.now()
            )

            return Response(serializer.data)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


class RetrieveSingleDemoPorfoliosAccounts(APIView):
    serializer_class = exec_serializer.DemoPortfolioSerializer
    account_create_serializer = exec_serializer.DemoPortfolioCreateSerializer

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get(self, request, *args, **kwargs):
        id = kwargs.get("id")
        demo_account = self.get_account(id)
        if demo_account is None:
            return Response("Account not found", status.HTTP_404_NOT_FOUND)
        if demo_account.user != request.user:
            return Response("Permission denied", status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(demo_account, many=False)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        id = kwargs.get("id")
        demo_account = self.get_account(id)
        if demo_account is None:
            return Response("Account not found", status.HTTP_404_NOT_FOUND)
        if demo_account.user != request.user:
            return Response("Permission denied", status.HTTP_403_FORBIDDEN)

        serializer = self.account_create_serializer(
            demo_account, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        id = kwargs.get("id")
        demo_account = self.get_account(id)
        if demo_account is None:
            return Response("Account not found", status.HTTP_404_NOT_FOUND)
        if demo_account.user != request.user:
            return Response("Permission denied", status.HTTP_403_FORBIDDEN)
        demo_account.delete()
        return Response(None, status.HTTP_204_NO_CONTENT)


class RetrieveSinglePorfoliosAccounts(APIView):
    serializer_class = exec_serializer.PortfolioSerializer
    account_create_serializer = exec_serializer.PortfolioCreateSerializer

    def get_account(self, id):
        account = Portfolio.objects.filter(id=id).first()
        return account if account else None

    def get(self, request, *args, **kwargs):
        id = kwargs.get("id")
        account = self.get_account(id)
        if account is None:
            return Response("Account not found", status.HTTP_404_NOT_FOUND)
        if account.user != request.user:
            return Response("Permission denied", status.HTTP_403_FORBIDDEN)

        serializer = self.serializer_class(account, many=False)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        id = kwargs.get("id")
        account = self.get_account(id)
        if account is None:
            return Response("Account not found", status.HTTP_404_NOT_FOUND)
        if account.user != request.user:
            return Response("Permission denied", status.HTTP_403_FORBIDDEN)

        serializer = self.account_create_serializer(
            account, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        id = kwargs.get("id")
        account = self.get_account(id)
        if account is None:
            return Response("Account not found", status.HTTP_404_NOT_FOUND)
        if account.user != request.user:
            return Response("Permission denied", status.HTTP_403_FORBIDDEN)

        wallet = Wallet.objects.get(user=request.user)
        wallet.balance += account.balance
        wallet.save()

        account.delete()
        return Response(None, status.HTTP_204_NO_CONTENT)


def get_position(all_prices, queryset):

    all_positions = []
    for position in queryset:
        symbol = position.stock.symbol
        price = all_prices[symbol]["current_price"]
        current_value = round(position.quantity * price, 2)

        if position.status == "open":
            if position.action == "buy":
                profit_loss = Decimal(current_value) - position.amount_invested
            elif position.action == "sell":
                profit_loss = position.amount_invested - Decimal(current_value)
        elif position.status == "close":
            profit_loss = position.profit_loss
            current_value = position.quantity * position.close_price
        else:
            current_value = 0
            profit_loss = 0

        if position.amount_invested != 0:
            percent = round((profit_loss / position.amount_invested) * 100, 2)
            data1 = {
                "id": position.id,
                "symbol": symbol,
                "open_pl": round(profit_loss, 2),
                "pl_percent": percent,
                "created": position.created,
                "status": position.status,
                "open_price": position.open_price,
                "order_id": position.order_id,
            }

        else:
            data1 = {
                "id": position.id,
                "symbol": symbol,
                "open_pl": 0,
                "pl_percent": 0,
                "created": position.created,
                "status": position.status,
                "open_price": position.open_price,
                "order_id": position.order_id,
            }
        all_positions.append(data1)
    return all_positions


class SingleDemoTradeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "demo_portfolio":
            # GET THE PARTICULAR PORTFOLIO
            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            positions = DemoPosition.objects.filter(
                portfolio=demo_account, status="open"
            )
            all_prices = get_stockdata2()

            position_data_list = [get_position(all_prices, positions)]

            return Response(position_data_list)

        else:

            # get competition portfoilo by id
            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            demo_account = CompetitionPortfolio.objects.filter(
                competition__status="current", active=True, id=id
            )

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # competition = Competition.objects.filter(status='current').first()
            # portfolio = None

            if competition:
                portfolio = in_competition

            if portfolio and timezone.now() > competition.start_date:
                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )

            all_prices = get_stockdata2()

            position_data_list = [get_position(all_prices, positions)]

            return Response(position_data_list)

    def post(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = [
            "demo_portfolio",
            "competition_account",
        ]
        id = kwargs.get("id")

        if not account_type in valid_account_types:
            return Response(
                {"error": f"Account type should be {valid_account_types}."},
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "demo_portfolio":
            demo_account = self.get_account(id)
            if demo_account.is_prop:
                if not demo_account.is_active or demo_account.blown:
                    return Response(
                        "You can no longer trade on this account.",
                        status.HTTP_400_BAD_REQUEST,
                    )

        symbol = request.data.get("symbol")
        order_id = request.data.get("order_id")
        quantity = int(request.data.get("quantity"))
        if quantity is None or quantity <= 0:
            return Response(
                {"error": "Quantity must be provided."},
                status.HTTP_400_BAD_REQUEST,
            )
        device_type = request.data.get("device_type", None)
        if request.data.get("price"):
            price = float(request.data.get("price"))
        action = request.data.get("action")
        time_in_force = request.data.get(
            "time_in_force", "day"
        )  # Default to Good 'Til Canceled
        is_buy = action == "buy"
        order_type = request.data.get("order_type")
        take_profit = request.data.get("take_profit", None)
        stop_loss = request.data.get("stop_loss", None)

        if take_profit:
            take_profit = float(take_profit)

        if stop_loss:
            stop_loss = float(stop_loss)

        current_price = round(Decimal(get_price(symbol)["current_price"]), 2)

        if order_type == "market":
            if take_profit:
                if action == "buy":
                    if current_price >= take_profit:
                        return Response(
                            {"error": "Take profit cannot be less than current price"},
                            status.HTTP_400_BAD_REQUEST,
                        )
                elif action == "sell":
                    if current_price <= take_profit:
                        return Response(
                            {
                                "error": "Take profit cannot be greater than current price"
                            },
                            status.HTTP_400_BAD_REQUEST,
                        )

            if stop_loss:
                if action == "buy":
                    if current_price <= stop_loss:
                        return Response(
                            {"error": "Stop loss cannot be greater than current price"},
                            status.HTTP_400_BAD_REQUEST,
                        )
                elif action == "sell":
                    if current_price >= stop_loss:
                        return Response(
                            {"error": "Stop loss cannot be less than current price"},
                            status.HTTP_400_BAD_REQUEST,
                        )

        elif order_type == "limit":
            if take_profit:
                if action == "buy":
                    if price >= take_profit:
                        return Response(
                            {"error": "Take profit cannot be less than current price"},
                            status.HTTP_400_BAD_REQUEST,
                        )
                elif action == "sell":
                    if price <= take_profit:
                        return Response(
                            {
                                "error": "Take profit cannot be greater than current price"
                            },
                            status.HTTP_400_BAD_REQUEST,
                        )

            if stop_loss:
                if action == "buy":
                    if price <= stop_loss:
                        return Response(
                            {"error": "Stop loss cannot be greater than current price"},
                            status.HTTP_400_BAD_REQUEST,
                        )
                elif action == "sell":
                    if price >= stop_loss:
                        return Response(
                            {"error": "Stop loss cannot be less than current price"},
                            status.HTTP_400_BAD_REQUEST,
                        )

        # print(order_type)

        stock = get_object_or_404(Stock, symbol=symbol)

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            demo_account = CompetitionPortfolio.objects.filter(
                competition__status="current", active=True, id=id
            )

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition and timezone.now() > competition.start_date:
                portfolio = in_competition
                if order_type == "market":
                    market_price = current_price
                    amount = quantity * market_price

                    balance = portfolio.balance
                    # trade_commission = round(Decimal(0.00435) * amount, 2) + 200

                    total = amount  # + trade_commission
                    if balance >= total:
                        position = CompetitionPosition.objects.create(
                            portfolio=portfolio,
                            stock=stock,
                            status=CompetitionPosition.OPEN,
                            open_price=market_price,
                            quantity=quantity,
                            amount_invested=amount,
                            order_id=order_id,
                            take_profit=take_profit,
                            stop_loss=stop_loss,
                        )

                        if not is_buy:
                            position.action = "sell"
                            position.save()

                        CompetitionTransaction.objects.create(
                            user=request.user,
                            transaction_type="open trade",
                            amount=amount,
                            status="completed",
                        )
                        # CompetitionTransaction.objects.create(
                        #     user=request.user,
                        #     transaction_type="trade commission",
                        #     amount=trade_commission,
                        #     status="completed",
                        # )

                        portfolio.balance -= total
                        portfolio.save()

                        UserActivityLog.objects.create(
                            user=request.user,
                            action_type="competition_open_trade",
                            description=f"User opened competition trade with amount {amount} on symbol {symbol}.",
                            device_type=device_type,
                        )

                        competition_task.first_daily_trade.delay(portfolio.id)

                        save_and_send_notification(
                            request.user.id,
                            f" COMPETITION: You opened position {quantity} units of {stock.symbol} at {position.open_price} per unit. Total value:{quantity * position.open_price}naira ",
                        )

                        return Response(
                            {"message": f"{action.title()} order placed successfully."},
                            status=status.HTTP_201_CREATED,
                        )
                    else:
                        return Response(
                            {"error": "Insufficient funds to trade."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                elif order_type == "limit":

                    position = CompetitionPosition.objects.create(
                        portfolio=portfolio,
                        stock=stock,
                        status=CompetitionPosition.PENDING,
                        limit_price=price,
                        quantity=quantity,
                        alert_name="pending_trade_" + shortuuid.uuid(),
                        time_in_force=time_in_force,
                        order_id=order_id,
                        order_type=order_type,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                        action=action,
                    )

                    # schedule, created = IntervalSchedule.objects.get_or_create(
                    #     every=3,
                    #     period=IntervalSchedule.MINUTES,
                    # )

                    # if not is_buy:
                    #     position.action = "sell"
                    #     position.save()

                    # task = PeriodicTask.objects.create(
                    #     interval=schedule,
                    #     name=position.alert_name,
                    #     task="execution.tasks.process_limit_order",
                    #     args=json.dumps([position.id, True]),
                    # )

                    # positions = CompetitionPosition.objects.filter(portfolio=portfolio,status='open',active=True)

                    save_and_send_notification(
                        request.user.id,
                        f" COMPETITION: Your limit order will be opened when the condition you set is met.",
                    )

                    return Response(
                        {"message": f"{action.title()} order scheduled successfully."},
                        status=status.HTTP_201_CREATED,
                    )

        # the acccount type is a demo portfolio
        else:

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account

            if order_type == "market":
                market_price = round(Decimal(get_price(symbol)["current_price"]), 2)
                amount = quantity * market_price

                balance = portfolio.balance
                # trade_commission = round(Decimal(0.00435) * amount, 2) + 200

                total = amount  # + trade_commission
                if balance >= total:
                    position = DemoPosition.objects.create(
                        portfolio=portfolio,
                        stock=stock,
                        status=CompetitionPosition.OPEN,
                        open_price=market_price,
                        quantity=quantity,
                        amount_invested=amount,
                        order_id=order_id,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )

                    if not is_buy:
                        position.action = "sell"
                        position.save()

                    DemoTransaction.objects.create(
                        user=request.user,
                        transaction_type="open trade",
                        amount=amount,
                        status="completed",
                    )
                    # DemoTransaction.objects.create(
                    #     user=request.user,
                    #     transaction_type="trade commission",
                    #     amount=trade_commission,
                    #     status="completed",
                    # )

                    portfolio.balance -= total
                    portfolio.save()

                    UserActivityLog.objects.create(
                        user=request.user,
                        action_type="demo_open_trade",
                        description=f"User opened demo trade with amount {amount} on symbol {symbol}.",
                        device_type=device_type,
                    )

                    save_and_send_notification(
                        request.user.id,
                        f" DEMO: You opened position {quantity} units of {stock.symbol} at {position.open_price} per unit. Total value:{quantity * position.open_price}naira ",
                    )

                    return Response(
                        {"message": f"{action.title()} order placed successfully."},
                        status=status.HTTP_201_CREATED,
                    )
                else:
                    return Response(
                        {"error": "Insufficient funds to trade."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            elif order_type == "limit":

                position = DemoPosition.objects.create(
                    portfolio=portfolio,
                    stock=stock,
                    status=DemoPosition.PENDING,
                    limit_price=price,
                    quantity=quantity,
                    alert_name=shortuuid.uuid(),
                    time_in_force=time_in_force,
                    order_id=order_id,
                    order_type=order_type,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    action=action,
                )

                # schedule, created = IntervalSchedule.objects.get_or_create(
                #     every=3,
                #     period=IntervalSchedule.MINUTES,
                # )

                # if not is_buy:
                #     position.action = "sell"
                #     position.save()

                # task = PeriodicTask.objects.create(
                #     interval=schedule,
                #     name=position.alert_name,
                #     task="execution.tasks.process_limit_order",
                #     args=json.dumps([position.id]),
                # )

                # positions = DemoPosition.objects.filter(
                #     portfolio=portfolio, status="open"
                # )

                save_and_send_notification(
                    request.user.id,
                    f" DEMO: Your limit order will be opened when the condition you set is met.",
                )

                return Response(
                    {"message": f"{action.title()} order scheduled successfully."},
                    status=status.HTTP_201_CREATED,
                )


class SupportSingleDemoTradeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "demo_portfolio":
            # GET THE PARTICULAR PORTFOLIO
            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if not request.user.is_staff:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            positions = DemoPosition.objects.filter(
                portfolio=demo_account, status="open"
            )

        else:

            # get competition portfoilo by id
            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            demo_account = CompetitionPortfolio.objects.filter(
                competition__status="current", active=True, id=id
            )

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if not request.user.is_staff:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # competition = Competition.objects.filter(status='current').first()
            # portfolio = None

            if competition:
                portfolio = in_competition

            if portfolio and timezone.now() > competition.start_date:
                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )

        all_prices = get_stockdata2()

        position_data_list = [get_position(all_prices, positions)]

        return Response(position_data_list)


####################### New home view ###############################################


class NewHome(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            # demo_account = self.get_competion_account(id, competition)

            demo_account = CompetitionPortfolio.objects.filter(active=True, id=id)

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition:
                portfolio = in_competition
                compositions = CompetitionPosition.objects.filter(
                    portfolio=portfolio,)
                positions = compositions.filter(
                    status="open"
                )
                positions2 = compositions.filter(
                    status="close"
                )

                today = timezone.now()
                position_data_dict = {}

                for daily in positions2:
                    if daily.updated.month == today.month:
                        date_key = daily.updated.date()
                        if date_key in position_data_dict:
                            position_data_dict[date_key] += daily.profit_loss - daily.commission
                        else:
                            position_data_dict[date_key] = daily.profit_loss - daily.commission

                position_data_list2 = [
                    {"profit_loss": profit_loss, "date": date}
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item["date"] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {
                        "profit_loss": position_data_dict.get(date, 0),
                        "date": date.strftime("%Y-%m-%d"),
                    }
                    for date in (
                        start_date + timedelta(n)
                        for n in range((today.date() - start_date).days + 1)
                        if (start_date + timedelta(n)).weekday() < 5
                    )
                ]
                profit_loss2 = sum([pos.profit_loss - pos.commission for pos in positions2])

                balance = portfolio.balance

                def pl_cv(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    print(pl)
                    data2 = {
                        "stock": symbol,
                        "current_value": round(cur_val, 2),
                        "pl": pl,
                        "open_date": position.created,
                    }

                    return pl, data2

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]

                close_positions_new = [
                    {
                        "stock": position.stock.symbol,
                        "profit_loss": position.profit_loss,
                        "close_date": position.updated,
                    }
                    for position in positions2
                ]

                open_positionsmap = [x[1] for x in pl_cv_list]
                open_positions_new = [
                    {"symbol": x["stock"], "profit_loss": x["pl"]}
                    for x in open_positionsmap
                ]

                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]

                profit_loss = sum(profit_loss_list) if profit_loss_list else 0

                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss = CompetitionDailyReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")
                cumulative_profitloss = CompetitionCumulativeReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for returns in daily_profitloss:
                        overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    for returns in cumulative_profitloss:
                        cumulative_overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                equity1 = round(balance + profit_loss, 2)
                equity = equity1 if equity1 >= 0 else 0

                calendar = [
                    {
                        "date": daily.created.date(),
                        "return": daily.portfolio_returns,
                    }
                    for daily in daily_profitloss[1:]
                    if daily_profitloss.count() > 1
                ]
                open_balance = sum([position.amount_invested for position in positions])

                data = {
                    "balance": round(balance + open_balance, 2),
                    "starting_balance": 1000000,
                    "equity": equity + open_balance,
                    "floating_pl": profit_loss,
                    "closed_pl": profit_loss2,
                    # 'positions': position_data_list2,
                    "positions": final_list,
                    # 'open_positions': position_data_list,
                    "current_value": current_value_list,
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                    "calendar": calendar,
                    "remaining_balance": balance,
                    "close_positions": close_positions_new,
                    "open_positions": open_positions_new,
                }

                return Response(data)
        else:

            # handle specific portfolio

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account
            demo_positions_q =  DemoPosition.objects.filter(portfolio=portfolio)
            # portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions = demo_positions_q.filter(status="open")
            positions2 = demo_positions_q.filter(status="close")

            today = timezone.now()
            position_data_dict = {}

            for daily in positions2:
                if daily.updated.month == today.month:
                    date_key = daily.updated.date()
                    if date_key in position_data_dict:
                        position_data_dict[date_key] += daily.profit_loss - daily.commission
                    else:
                        position_data_dict[date_key] = daily.profit_loss - daily.commission

            position_data_list2 = [
                {"profit_loss": profit_loss, "date": date}
                for date, profit_loss in position_data_dict.items()
            ]
            if position_data_list2:
                start_date = min(item["date"] for item in position_data_list2)
            else:
                start_date = today.date()

            # Create a new list with dates from start_date until today
            final_list = [
                {
                    "profit_loss": position_data_dict.get(date, 0),
                    "date": date.strftime("%Y-%m-%d"),
                }
                for date in (
                    start_date + timedelta(n)
                    for n in range((today.date() - start_date).days + 1)
                    if (start_date + timedelta(n)).weekday() < 5
                )
            ]
            profit_loss2 = sum([pos.profit_loss - pos.commission for pos in positions2])

            balance = portfolio.balance

            def pl_cv(position):
                pl, cur_val, price = position.calculate_profit_loss()
                symbol = position.stock.symbol
                print(pl)
                data2 = {
                    "stock": symbol,
                    "current_value": round(cur_val, 2),
                    "pl": pl,
                    "open_date": position.created,
                }

                return pl, data2

            with ThreadPoolExecutor() as executor:
                futures = executor.map(pl_cv, positions)
                pl_cv_list = [result for result in futures if result]

            close_positions_new = [
                {
                    "stock": position.stock.symbol,
                    "profit_loss": position.profit_loss,
                    "close_date": position.updated,
                }
                for position in positions2
            ]

            open_positionsmap = [x[1] for x in pl_cv_list]
            open_positions_new = [
                {"symbol": x["stock"], "profit_loss": x["pl"]}
                for x in open_positionsmap
            ]

            profit_loss_list = [x[0] for x in pl_cv_list]
            current_value_list = [x[1] for x in pl_cv_list]

            profit_loss = sum(profit_loss_list) if profit_loss_list else 0

            # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
            daily_profitloss = DemoDailyReturns2.objects.filter(
                portfolio=portfolio
            ).order_by("created")
            cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                portfolio=portfolio
            ).order_by("created")
            # print(daily_profitloss)
            # print(cumulative_profitloss)

            # market= NewMarketReturns.objects.filter(portfolio=portfolio)
            # cumulative_market = NewCumulativeMarketReturns.objects.filter(portfolio=portfolio)

            overview = []
            cumulative_overview = []

            if daily_profitloss and daily_profitloss.count() > 1:
                for returns in daily_profitloss:
                    overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            if cumulative_profitloss and cumulative_profitloss.count() > 1:
                for returns in cumulative_profitloss:
                    cumulative_overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            equity1 = round(balance + profit_loss, 2)
            equity = equity1 if equity1 >= 0 else 0

            calendar = [
                {
                    "date": daily.created.date(),
                    "return": daily.portfolio_returns,
                }
                for daily in daily_profitloss[1:]
                if daily_profitloss.count() > 1
            ]
            open_balance = sum([position.amount_invested for position in positions])
            data = {
                "balance": round(balance + open_balance, 2),
                "starting_balance": float(portfolio.initial_balance),
                "equity": equity + open_balance,
                "floating_pl": profit_loss,
                "closed_pl": profit_loss2,
                # 'positions': position_data_list2,
                "positions": final_list,
                # 'open_positions': position_data_list,
                "current_value": current_value_list,
                "overview": overview,
                "cumulative_overview": cumulative_overview,
                "calendar": calendar,
                "remaining_balance": balance,
                "close_positions": close_positions_new,
                "open_positions": open_positions_new,
            }

            return Response(data)


class NewSupportHome(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            competition__status="current", active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            # demo_account = self.get_competion_account(id, competition)

            demo_account = CompetitionPortfolio.objects.filter(active=True, id=id)

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition:
                portfolio = in_competition

                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="open"
                )
                positions2 = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    {"profit_loss": profit_loss, "date": date}
                    for date, profit_loss in position_data_dict.items()
                ]
                if position_data_list2:
                    start_date = min(item["date"] for item in position_data_list2)
                else:
                    start_date = today.date()

                # Create a new list with dates from start_date until today
                final_list = [
                    {
                        "profit_loss": position_data_dict.get(date, 0),
                        "date": date.strftime("%Y-%m-%d"),
                    }
                    for date in (
                        start_date + timedelta(n)
                        for n in range((today.date() - start_date).days + 1)
                        if (start_date + timedelta(n)).weekday() < 5
                    )
                ]
                profit_loss2 = sum([pos.profit_loss for pos in positions2])

                balance = portfolio.balance

                def pl_cv(position):
                    pl, cur_val, price = position.calculate_profit_loss()
                    symbol = position.stock.symbol
                    print(pl)
                    data2 = {
                        "stock": symbol,
                        "current_value": round(cur_val, 2),
                        "pl": pl,
                        "open_date": position.created,
                    }

                    return pl, data2

                with ThreadPoolExecutor() as executor:
                    futures = executor.map(pl_cv, positions)
                    pl_cv_list = [result for result in futures if result]

                close_positions_new = [
                    {
                        "stock": position.stock.symbol,
                        "profit_loss": position.profit_loss,
                        "close_date": position.updated,
                    }
                    for position in positions2
                ]

                open_positionsmap = [x[1] for x in pl_cv_list]
                open_positions_new = [
                    {"symbol": x["stock"], "profit_loss": x["pl"]}
                    for x in open_positionsmap
                ]
                profit_loss_list = [x[0] for x in pl_cv_list]
                current_value_list = [x[1] for x in pl_cv_list]

                profit_loss = sum(profit_loss_list) if profit_loss_list else 0

                # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
                daily_profitloss = CompetitionDailyReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")
                cumulative_profitloss = CompetitionCumulativeReturns2.objects.filter(
                    portfolio=in_competition
                ).order_by("created")

                # market= CompetitionMarketReturns.objects.all()
                # cumulative_market = CompetitionCumulativeMarketReturns.objects.all()

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for returns in daily_profitloss:
                        overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    for returns in cumulative_profitloss:
                        cumulative_overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                equity1 = round(balance + profit_loss, 2)
                equity = equity1 if equity1 >= 0 else 0

                calendar = [
                    {
                        "date": daily.created.date(),
                        "return": daily.portfolio_returns,
                    }
                    for daily in daily_profitloss[1:]
                    if daily_profitloss.count() > 1
                ]
                open_balance = sum([position.amount_invested for position in positions])
                data = {
                    "balance": round(balance + open_balance, 2),
                    "starting_balance": 1000000,
                    "equity": equity + open_balance,
                    "floating_pl": profit_loss,
                    "closed_pl": profit_loss2,
                    # 'positions': position_data_list2,
                    "positions": final_list,
                    # 'open_positions': position_data_list,
                    "current_value": current_value_list,
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                    "calendar": calendar,
                    "remaining_balance": balance,
                    "close_positions": close_positions_new,
                    "open_positions": open_positions_new,
                }

                return Response(data)
        else:

            # handle specific portfolio

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)

            portfolio = demo_account

            # portfolio= DemoPortfolio.objects.get_or_create(user=request.user)[0]
            positions = DemoPosition.objects.filter(portfolio=portfolio, status="open")
            positions2 = DemoPosition.objects.filter(
                portfolio=portfolio, status="close"
            )

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
                {"profit_loss": profit_loss, "date": date}
                for date, profit_loss in position_data_dict.items()
            ]
            if position_data_list2:
                start_date = min(item["date"] for item in position_data_list2)
            else:
                start_date = today.date()

            # Create a new list with dates from start_date until today
            final_list = [
                {
                    "profit_loss": position_data_dict.get(date, 0),
                    "date": date.strftime("%Y-%m-%d"),
                }
                for date in (
                    start_date + timedelta(n)
                    for n in range((today.date() - start_date).days + 1)
                    if (start_date + timedelta(n)).weekday() < 5
                )
            ]
            profit_loss2 = sum([pos.profit_loss for pos in positions2])

            balance = portfolio.balance

            def pl_cv(position):
                pl, cur_val, price = position.calculate_profit_loss()
                symbol = position.stock.symbol
                print(pl)
                data2 = {
                    "stock": symbol,
                    "current_value": round(cur_val, 2),
                    "pl": pl,
                    "open_date": position.created,
                }

                return pl, data2

            with ThreadPoolExecutor() as executor:
                futures = executor.map(pl_cv, positions)
                pl_cv_list = [result for result in futures if result]

            close_positions_new = [
                {
                    "stock": position.stock.symbol,
                    "profit_loss": position.profit_loss,
                    "close_date": position.updated,
                }
                for position in positions2
            ]

            open_positionsmap = [x[1] for x in pl_cv_list]
            open_positions_new = [
                {"symbol": x["stock"], "profit_loss": x["pl"]}
                for x in open_positionsmap
            ]

            profit_loss_list = [x[0] for x in pl_cv_list]
            current_value_list = [x[1] for x in pl_cv_list]

            profit_loss = sum(profit_loss_list) if profit_loss_list else 0

            # daily_profitloss= DemoDailyReturns.objects.filter(user=request.user)
            daily_profitloss = DemoDailyReturns2.objects.filter(
                portfolio=portfolio
            ).order_by("created")
            cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                portfolio=portfolio
            ).order_by("created")
            # print(daily_profitloss)
            # print(cumulative_profitloss)

            # market= NewMarketReturns.objects.filter(portfolio=portfolio)
            # cumulative_market = NewCumulativeMarketReturns.objects.filter(portfolio=portfolio)

            overview = []
            cumulative_overview = []

            if daily_profitloss and daily_profitloss.count() > 1:
                for returns in daily_profitloss:
                    overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            if cumulative_profitloss and cumulative_profitloss.count() > 1:
                for returns in cumulative_profitloss:
                    cumulative_overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            equity1 = round(balance + profit_loss, 2)
            equity = equity1 if equity1 >= 0 else 0

            calendar = [
                {
                    "date": daily.created.date(),
                    "return": daily.portfolio_returns,
                }
                for daily in daily_profitloss[1:]
                if daily_profitloss.count() > 1
            ]
            open_balance = sum([position.amount_invested for position in positions])
            data = {
                "balance": round(balance + open_balance, 2),
                "starting_balance": 1000000,
                "equity": equity + open_balance,
                "floating_pl": profit_loss,
                "closed_pl": profit_loss2,
                # 'positions': position_data_list2,
                "positions": final_list,
                # 'open_positions': position_data_list,
                "current_value": current_value_list,
                "overview": overview,
                "cumulative_overview": cumulative_overview,
                "calendar": calendar,
                "remaining_balance": balance,
                "close_positions": close_positions_new,
                "open_positions": open_positions_new,
            }

            return Response(data)


class NewOverView(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        from_date = kwargs.get("from_date", None)
        to_date = kwargs.get("to_date", None)

        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )
        two_weeks_ago = datetime.now().date() - timedelta(weeks=2)

        if account_type == "competition_account":

            id = kwargs.get("id")

            demo_account = CompetitionPortfolio.objects.filter(active=True, id=id)

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            if in_competition:
                portfolio = in_competition

                if from_date != "all" and to_date != "all":

                    daily_profitloss = CompetitionDailyReturns2.objects.filter(
                        portfolio=portfolio, created__range=(from_date, to_date)
                    ).order_by("created")
                    cumulative_profitloss = (
                        CompetitionCumulativeReturns2.objects.filter(
                            portfolio=portfolio, created__range=(from_date, to_date)
                        ).order_by("created")
                    )
                else:

                    daily_profitloss = CompetitionDailyReturns2.objects.filter(
                        portfolio=in_competition
                    ).order_by("created")
                    cumulative_profitloss = (
                        CompetitionCumulativeReturns2.objects.filter(
                            portfolio=in_competition
                        ).order_by("created")
                    )

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for returns in daily_profitloss:
                        overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    for returns in cumulative_profitloss:
                        cumulative_overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                data = {
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                }

                return Response(data)
        else:

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account
            if from_date != "all" and to_date != "all":
                daily_profitloss = DemoDailyReturns2.objects.filter(
                    portfolio=portfolio, created__range=(from_date, to_date)
                ).order_by("created")
                cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                    portfolio=portfolio, created__range=(from_date, to_date)
                ).order_by("created")
            else:

                daily_profitloss = DemoDailyReturns2.objects.filter(
                    portfolio=portfolio
                ).order_by("created")
                cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                    portfolio=portfolio
                ).order_by("created")

            overview = []
            cumulative_overview = []

            if daily_profitloss:
                for returns in daily_profitloss:
                    overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            if cumulative_profitloss:
                for returns in cumulative_profitloss:
                    cumulative_overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            data = {
                "overview": overview[-20:],
                "cumulative_overview": cumulative_overview[-20:],
            }

            return Response(data)


class SupportNewOverView(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        from_date = kwargs.get("from_date", None)
        to_date = kwargs.get("to_date", None)

        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )
        two_weeks_ago = datetime.now().date() - timedelta(weeks=2)

        if account_type == "competition_account":

            id = kwargs.get("id")

            demo_account = CompetitionPortfolio.objects.filter(active=True, id=id)

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)

            in_competition = demo_account

            if in_competition:
                portfolio = in_competition

                if from_date != "all" and to_date != "all":

                    daily_profitloss = CompetitionDailyReturns2.objects.filter(
                        portfolio=portfolio, created__range=(from_date, to_date)
                    ).order_by("created")
                    cumulative_profitloss = (
                        CompetitionCumulativeReturns2.objects.filter(
                            portfolio=portfolio, created__range=(from_date, to_date)
                        ).order_by("created")
                    )
                else:

                    daily_profitloss = CompetitionDailyReturns2.objects.filter(
                        portfolio=in_competition
                    ).order_by("created")
                    cumulative_profitloss = (
                        CompetitionCumulativeReturns2.objects.filter(
                            portfolio=in_competition
                        ).order_by("created")
                    )

                overview = []
                cumulative_overview = []

                if daily_profitloss and daily_profitloss.count() > 1:
                    for returns in daily_profitloss:
                        overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                if cumulative_profitloss and cumulative_profitloss.count() > 1:
                    for returns in cumulative_profitloss:
                        cumulative_overview.append(
                            {
                                "portfolio_returns": returns.portfolio_returns,
                                "market_returns": returns.market_returns,
                                "date": returns.created.date(),
                            }
                        )

                data = {
                    "overview": overview,
                    "cumulative_overview": cumulative_overview,
                }

                return Response(data)
        else:

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)

            portfolio = demo_account
            if from_date != "all" and to_date != "all":
                daily_profitloss = DemoDailyReturns2.objects.filter(
                    portfolio=portfolio, created__range=(from_date, to_date)
                ).order_by("created")
                cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                    portfolio=portfolio, created__range=(from_date, to_date)
                ).order_by("created")
            else:

                daily_profitloss = DemoDailyReturns2.objects.filter(
                    portfolio=portfolio
                ).order_by("created")
                cumulative_profitloss = DemoCumulativeReturns.objects.filter(
                    portfolio=portfolio
                ).order_by("created")

            overview = []
            cumulative_overview = []

            if daily_profitloss:
                for returns in daily_profitloss:
                    overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            if cumulative_profitloss:
                for returns in cumulative_profitloss:
                    cumulative_overview.append(
                        {
                            "portfolio_returns": returns.portfolio_returns,
                            "market_returns": returns.market_returns,
                            "date": returns.created.date(),
                        }
                    )

            data = {
                "overview": overview[-20:],
                "cumulative_overview": cumulative_overview[-20:],
            }

            return Response(data)


class NewDemoCloseTrade(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def post(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        device_type = request.data.get("device_type", None)
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")
            position_id = kwargs.get("position_id")

            demo_account = CompetitionPortfolio.objects.filter(
                competition__status="current", active=True, id=id
            )

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition and timezone.now() > competition.start_date:
                position = CompetitionPosition.objects.filter(
                    portfolio=in_competition, id=position_id
                ).first()

                if position.status == "open":
                    pl, cur_val, price = position.calculate_profit_loss()

                    trade_commission = (
                        round(Decimal(0.00435) * position.amount_invested, 2) + 200
                    )

                    position.status = "close"
                    position.close_price = Decimal(price)
                    position.profit_loss = pl
                    position.comment = "closed by trader"
                    position.save()

                    CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type="close trade",
                        amount=cur_val,
                        status="completed",
                    )

                    CompetitionTransaction.objects.create(
                        user=request.user,
                        transaction_type="trade commission",
                        amount=trade_commission,
                        status="completed",
                    )

                    UserActivityLog.objects.create(
                        user=request.user,
                        action_type="competition_closed_trade",
                        description=f"User closed competition trade with symbol {position.stock.symbol}.",
                        device_type=device_type,
                    )
                    position.portfolio.balance += (
                        position.amount_invested
                        + position.profit_loss
                        - trade_commission
                    )
                    position.portfolio.save()

                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "quantity": position.quantity,
                        "open_price": position.open_price,
                        "close_price": position.close_price,
                        "open_time": position.created.isoformat(),
                        "close_time": position.updated.isoformat(),
                        "profit_loss": position.profit_loss,
                        "order_id": position.order_id,
                    }
                    return Response(data)
                else:
                    return Response("Position is already closed")
        else:

            id = kwargs.get("id")
            position_id = kwargs.get("position_id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account
            position = DemoPosition.objects.filter(
                portfolio=portfolio, id=position_id
            ).first()

            if not position:
                return Response("Position not found", status.HTTP_404_NOT_FOUND)

            # position =  get_object_or_404(DemoPosition, id=id)
            if position.status == "open":
                pl, cur_val, price = position.calculate_profit_loss()

                trade_commission = (
                    round(Decimal(0.00435) * position.amount_invested, 2) + 200
                )

                position.status = "close"
                position.close_price = Decimal(price)
                position.comment = "closed by trader"
                position.profit_loss = pl

                position.save()

                DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type="close trade",
                    amount=cur_val,
                    status="completed",
                )

                DemoTransaction.objects.create(
                    user=request.user,
                    transaction_type="trade commission",
                    amount=trade_commission,
                    status="completed",
                )

                UserActivityLog.objects.create(
                    user=request.user,
                    action_type="demo_closed_trade",
                    description=f"User closed demo trade with symbol {position.stock.symbol}.",
                    device_type=device_type,
                )
                position.portfolio.balance += (
                    position.amount_invested + position.profit_loss - trade_commission
                )
                position.portfolio.save()

                data = {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": position.close_price,
                    "open_time": position.created.isoformat(),
                    "close_time": position.updated.isoformat(),
                    "profit_loss": position.profit_loss,
                    "order_id": position.order_id,
                }
                return Response(data)
            else:
                return Response("Position is not open")


class NewDemoClosePendingTrade(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def post(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]
        device_type = request.data.get("device_type", None)

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")
            position_id = kwargs.get("position_id")

            demo_account = CompetitionPortfolio.objects.filter(
                competition__status="current", active=True, id=id
            )

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition and timezone.now() > competition.start_date:
                position = CompetitionPosition.objects.filter(
                    portfolio=in_competition, id=position_id
                ).first()
                if position.status == "pending":

                    position.status = "cancelled"
                    position.save()

                    task = PeriodicTask.objects.get(name=position.alert_name)
                    task.enabled = False
                    task.save()

                    activity = UserActivityLog.objects.create(
                        user=request.user,
                        action_type="competition_cancel_trade",
                        description=f"User cancelled competition pending trade with symbol {position.stock.symbol}.",
                        device_type=device_type,
                    )

                    data = {
                        "id": position.id,
                        "stock": position.stock.symbol,
                        "quantity": position.quantity,
                        "open_price": position.open_price,
                        "close_price": position.close_price,
                        "open_time": position.created.isoformat(),
                        "close_time": position.updated.isoformat(),
                        "profit_loss": position.profit_loss,
                        "order_id": position.order_id,
                    }
                    return Response(data)
                else:
                    return Response("Position is already cancelled")
        else:

            id = kwargs.get("id")
            position_id = kwargs.get("position_id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account
            position = DemoPosition.objects.filter(
                portfolio=portfolio, id=position_id
            ).first()

            if not position:
                return Response("Position not found", status.HTTP_404_NOT_FOUND)

            # position =  get_object_or_404(DemoPosition, id=id)
            if position.status == "pending":

                position.status = "cancelled"

                position.save()

                task = PeriodicTask.objects.get(name=position.alert_name)
                task.enabled = False
                task.save()

                UserActivityLog.objects.create(
                    user=request.user,
                    action_type="demo_closed_pending_trade",
                    description=f"User cancelled  demo pending trade with symbol {position.stock.symbol}.",
                    device_type=device_type,
                )

                data = {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": position.close_price,
                    "open_time": position.created.isoformat(),
                    "close_time": position.updated.isoformat(),
                    "profit_loss": position.profit_loss,
                    "order_id": position.order_id,
                }
                return Response(data)
            else:
                return Response("Position is not open")


def get_holdings_positions(queryset):
    all_prices = get_stockdata2()
    all_holdings = []
    for position in queryset:
        symbol = position.stock.symbol
        price = all_prices[symbol]["current_price"]
        current_value = round(position.quantity * price, 2)

        if position.status == "open":
            if position.action == "buy":
                profit_loss = Decimal(current_value) - position.amount_invested
            elif position.action == "sell":
                profit_loss = position.amount_invested - Decimal(current_value) 
        elif position.status == "close":
            profit_loss = position.profit_loss - position.commission
            current_value = position.quantity * position.close_price
        else:
            current_value = 0
            profit_loss = 0
        # print(type(profit_loss))
        if position.amount_invested != 0:
            percent_change = round(float(profit_loss) / float(position.amount_invested) * 100, 2)
        else:
            percent_change = None

        data = {
            "id": position.id,
            "stock": position.stock.symbol,
            "logo_url": position.stock.logo_url,
            "shares": position.quantity,
            "avg_cost": position.open_price,
            "close_price": position.close_price,
            "ltp": price,
            "open_time": position.created.isoformat(),
            "close_time": (
                position.updated.isoformat()
                if position.updated != position.created
                else "-"
            ),
            "change": round(profit_loss, 2),
            "percent_change": percent_change,
            "cur_val": current_value,
            "avg_volume": "3300",
            "volume": "66000",
            "status": position.status,
            "invested": position.amount_invested,
            "profit_loss": round(profit_loss, 2),
            "side": position.action,
            "order": position.order_type,
            "order_id": position.order_id,
            "take_profit": position.take_profit,
            "stop_loss": position.stop_loss,
            "trailing_sl": position.trailing_stop_loss,
            "comment": position.comment,
        }
        all_holdings.append(data)
    return all_holdings


class NewDemoHolding(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            demo_account = CompetitionPortfolio.objects.filter(active=True, id=id)

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition:
                portfolio = in_competition

                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio
                ).order_by("-updated")
                balance = portfolio.balance

                if positions:

                    positions_data = get_holdings_positions(positions)
                    floating_pl = sum(
                        [
                            data["change"]
                            for data in positions_data
                            if data["status"] == "open"
                        ]
                    )
                    closed_pl = sum(
                        [
                            data["profit_loss"]
                            for data in positions_data
                            if data["status"] == "close"
                        ]
                    )
                    open_trade_sum = sum(
                        [
                            data["invested"]
                            for data in positions_data
                            if data["status"] == "open"
                        ]
                    )
                    closed_trade_sum = sum(
                        [
                            data["invested"]
                            for data in positions_data
                            if data["status"] == "close"
                        ]
                    )
                    # wallet_balance = portfolio.balance
                    # open_balance = open_trade_sum
                    positions_close = CompetitionPosition.objects.filter(
                        portfolio=portfolio, status="open"
                    )
                    open_balance = sum(
                        [position.amount_invested for position in positions_close]
                    )

                    hold_data = {
                        "balance": balance + open_balance,
                        "floating_pl": floating_pl,
                        "closed_pl": closed_pl,
                        "equity": balance + floating_pl + open_balance,
                        "holdings": positions_data,
                    }

                    return Response(hold_data)
                else:
                    hold_data = {
                        "balance": balance,
                        "floating_pl": 0,
                        "closed_pl": 0,
                        "equity": balance,
                        "holdings": [],
                    }

                    return Response(hold_data)
        else:

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account

            positions = DemoPosition.objects.filter(portfolio=portfolio).order_by(
                "-updated"
            )
            balance = portfolio.balance

            if positions:

                positions_data = get_holdings_positions(positions)
                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                # wallet_balance = portfolio.balance
                open_balance = open_trade_sum

                hold_data = {
                    "balance": balance + open_balance,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": balance + floating_pl + open_balance,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "balance": balance,
                    "floating_pl": 0,
                    "closed_pl": 0,
                    "equity": balance,
                    "holdings": [],
                }

                return Response(hold_data)


class NewSupportDemoHolding(APIView):

    def get_account(self, id):
        demo_account = DemoPortfolio.objects.filter(id=id).first()
        return demo_account if demo_account else None

    def get_competion_account(self, id, competion):
        competition_demo_account = CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()
        return competition_demo_account if competition_demo_account else None

    def get(self, request, *args, **kwargs):

        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if not account_type in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":

            competition = Competition.objects.filter(status="current").first()

            # get the competion account
            id = kwargs.get("id")

            demo_account = demo_account = CompetitionPortfolio.objects.filter(
                active=True, id=id
            )

            if demo_account.exists:
                demo_account = demo_account.first()
            else:
                demo_account = None

            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)

            if not request.user.is_staff:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            in_competition = demo_account

            # in_competition =  CompetitionPortfolio.objects.filter(user=request.user, competition=competition,active=True).first()
            if in_competition:
                portfolio = in_competition

                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio
                ).order_by("-updated")
                balance = portfolio.balance

                if positions:

                    positions_data = get_holdings_positions(positions)
                    floating_pl = sum(
                        [
                            data["change"]
                            for data in positions_data
                            if data["status"] == "open"
                        ]
                    )
                    closed_pl = sum(
                        [
                            data["profit_loss"]
                            for data in positions_data
                            if data["status"] == "close"
                        ]
                    )
                    open_trade_sum = sum(
                        [
                            data["invested"]
                            for data in positions_data
                            if data["status"] == "open"
                        ]
                    )
                    closed_trade_sum = sum(
                        [
                            data["invested"]
                            for data in positions_data
                            if data["status"] == "close"
                        ]
                    )
                    # wallet_balance = portfolio.balance
                    # open_balance = open_trade_sum
                    positions_close = CompetitionPosition.objects.filter(
                        portfolio=portfolio, status="open"
                    )
                    open_balance = sum(
                        [position.amount_invested for position in positions_close]
                    )

                    hold_data = {
                        "balance": balance + open_balance,
                        "floating_pl": floating_pl,
                        "closed_pl": closed_pl,
                        "equity": balance + floating_pl + open_balance,
                        "holdings": positions_data,
                    }

                    return Response(hold_data)
                else:
                    hold_data = {
                        "balance": balance,
                        "floating_pl": 0,
                        "closed_pl": 0,
                        "equity": balance,
                        "holdings": [],
                    }

                    return Response(hold_data)
        else:

            id = kwargs.get("id")

            demo_account = self.get_account(id)
            if demo_account is None:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if not request.user.is_staff:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            portfolio = demo_account

            positions = DemoPosition.objects.filter(portfolio=portfolio).order_by(
                "-updated"
            )
            balance = portfolio.balance

            if positions:

                positions_data = get_holdings_positions(positions)
                floating_pl = sum(
                    [
                        data["change"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_pl = sum(
                    [
                        data["profit_loss"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                open_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "open"
                    ]
                )
                closed_trade_sum = sum(
                    [
                        data["invested"]
                        for data in positions_data
                        if data["status"] == "close"
                    ]
                )
                # wallet_balance = portfolio.balance
                open_balance = open_trade_sum

                hold_data = {
                    "balance": balance + open_balance,
                    "floating_pl": floating_pl,
                    "closed_pl": closed_pl,
                    "equity": balance + floating_pl + open_balance,
                    "holdings": positions_data,
                }

                return Response(hold_data)
            else:
                hold_data = {
                    "balance": balance,
                    "floating_pl": 0,
                    "closed_pl": 0,
                    "equity": balance,
                    "holdings": [],
                }

                return Response(hold_data)


class AddTrailingStopLoss(APIView):
    def get_demo_position(self, id):
        position = DemoPosition.objects.filter(id=id).first()
        return position if position else None

    def get_competion_account(self, id):
        position = CompetitionPosition.objects.filter(id=id).first()
        return position if position else None

    def post(self, request, *args, **kwargs):

        id = kwargs.get("id")
        account_type = request.data.get("account_type")

        if account_type == "competition_account":
            account = self.get_competion_account(id)
        else:
            account = self.get_demo_position(id)

        if not account:
            return Response("Position not found", status.HTTP_404_NOT_FOUND)

        # sl = request.data.get("stop_loss", account.stop_loss)
        # tp = request.data.get("take_profit", account.take_profit)
        # trailing_sl = request.data.get("trailing_sl", account.trailing_stop_loss )

        if account.status != "open":
            return Response("Position is not open", status.HTTP_400_BAD_REQUEST)

        sl = request.data.get("stop_loss")
        if sl:
            account.stop_loss = sl
        tp = request.data.get("take_profit")
        if tp:
            account.take_profit = tp
        trailing_sl = request.data.get("trailing_sl")
        if trailing_sl:
            account.trailing_stop_loss = Decimal(trailing_sl)

        # if not trailing_sl:
        #     return Response("Trailing stop loss is required", status.HTTP_400_BAD_REQUEST)

        # today = timezone.now()
        # if account.updated.date()== today.date() and account.trailing_stop_loss:
        #     return Response("Trailing stop loss can be added once a day.", status.HTTP_400_BAD_REQUEST)

        account.last_price = 0
        account.save()

        return Response("Trailing stop loss added successfully", status.HTTP_200_OK)


class ActivatePropAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code")

        # Verify code existence and ownership
        try:
            prop_account = DemoPortfolio.objects.get(
                code=code, user=request.user, is_prop=True
            )
        except DemoPortfolio.DoesNotExist:
            return Response(
                {"error": "Invalid or unauthorized code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Activate the account
        if prop_account.is_active:
            return Response(
                {"error": "Account is already active"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prop_account.is_active = True
        prop_account.activated = True
        prop_account.receipt_aproved = True
        prop_account.save()

        return Response(
            {"status": "Prop trading account activated successfully"},
            status=status.HTTP_200_OK,
        )

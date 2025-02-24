import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import shortuuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import competition
from accounts.models import UserActivityLog
from accounts.utils import User, get_referrer
from affilate.models import BrokageCommission, ReferralWallet, RewardActivities
from competition import models as competion_models
from competition import serializers as competition_serializer_module
from competition import tasks as competition_task
from competition.models import (
    Competition,
    CompetitionCumulativeReturns,
    CompetitionCumulativeReturns2,
    CompetitionDailyReturns,
    CompetitionDailyReturns2,
    CompetitionPortfolio,
    CompetitionPosition,
    CompetitionTransaction,
)
from notifications.utils import save_and_send_notification
from portfolio.models import DemoTransaction, Stock, Wallet
from portfolio.utils import get_price, get_stockdata2

from . import serializers as exec_serializer
from .models import (
    CompetitionCumulativeMarketReturns,
    CompetitionMarketReturns,
    CumulativeMarketReturns,
    CumulativeReturns,
    DailyReturns2,
    DemoCumulativeReturns,
    DemoDailyReturns2,
    DemoPortfolio,
    DemoPosition,
    MarketReturns,
    Portfolio,
    Position,
)

from django.db import transaction
from .utils import send_trade_notification

User = get_user_model()


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

    def validate_portfolio(self, portfolio):
        """Validate if portfolio can trade"""
        if not portfolio.can_trade:
            raise ValidationError("This account is not allowed to trade")
        if hasattr(portfolio, "is_prop") and portfolio.is_prop:
            if not portfolio.is_active or portfolio.blown:
                raise ValidationError("You can no longer trade on this account")
        return True

    def get_account(self, id):
        return DemoPortfolio.objects.filter(id=id).first()

    def get_competition_account(self, id, competition):
        return CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()

    def get(self, request, *args, **kwargs):
        account_type = kwargs.get("account_type")
        valid_account_types = ["demo_portfolio", "competition_account"]

        if account_type not in valid_account_types:
            return Response(
                f"Account type should be {valid_account_types}.",
                status.HTTP_400_BAD_REQUEST,
            )

        id = kwargs.get("id")

        if account_type == "demo_portfolio":
            demo_account = self.get_account(id)
            if not demo_account:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            positions = DemoPosition.objects.filter(
                portfolio=demo_account, status="open"
            )
        else:
            competition = Competition.objects.filter(status="current").first()
            demo_account = self.get_competition_account(id, competition)

            if not demo_account:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if demo_account.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            if competition and timezone.now() > competition.start_date:
                positions = CompetitionPosition.objects.filter(
                    portfolio=demo_account, status="open"
                )
            else:
                return Response(
                    "Competition hasn't started", status.HTTP_400_BAD_REQUEST
                )

        all_prices = get_stockdata2()
        position_data_list = [get_position(all_prices, positions)]
        return Response(position_data_list)

    @transaction.atomic
    def process_market_order(
        self,
        portfolio,
        stock,
        quantity,
        action,
        current_price,
        order_id,
        take_profit,
        stop_loss,
        device_type,
    ):
        """Process market order with transaction handling"""

        self.validate_portfolio(portfolio)

        amount = quantity * current_price
        trade_commission = round(Decimal(0.00435) * amount, 2) + Decimal("200")
        total = amount

        if portfolio.balance < total:
            raise ValidationError("Insufficient funds to trade")

        # Lock the portfolio row
        portfolio = type(portfolio).objects.select_for_update().get(id=portfolio.id)

        # Deduct balance first
        portfolio.balance -= total
        portfolio.save()

        position_model = (
            DemoPosition
            if isinstance(portfolio, DemoPortfolio)
            else CompetitionPosition
        )

        try:
            position = position_model.objects.create(
                portfolio=portfolio,
                stock=stock,
                status="open",
                open_price=current_price,
                quantity=quantity,
                amount_invested=amount,
                order_id=order_id,
                take_profit=take_profit,
                stop_loss=stop_loss,
                action=action,
            )

            # Send email notification
            trade_data = {
                "user_email": portfolio.user.email,
                "symbol": stock.symbol,
                "quantity": quantity,
                "price": current_price,
                "amount": amount,
                "account_id": portfolio.account_id,
                "order_type": "market",
                "action": action,
            }

            trade_type = (
                "competition" if isinstance(portfolio, CompetitionPortfolio) else "demo"
            )
            send_trade_notification(trade_type, "open", trade_data)

            return position

        except Exception as e:
            # Rollback is automatic in atomic block
            raise ValidationError(f"Failed to create position: {str(e)}")

    @transaction.atomic
    def process_limit_order(
        self,
        portfolio,
        stock,
        quantity,
        price,
        action,
        order_id,
        take_profit,
        stop_loss,
        time_in_force,
        device_type,
    ):
        """Process limit order with transaction handling"""

        self.validate_portfolio(portfolio)
        position_model = (
            DemoPosition
            if isinstance(portfolio, DemoPortfolio)
            else CompetitionPosition
        )

        try:
            position = position_model.objects.create(
                portfolio=portfolio,
                stock=stock,
                status="pending",
                limit_price=price,
                quantity=quantity,
                alert_name=shortuuid.uuid(),
                time_in_force=time_in_force,
                order_id=order_id,
                order_type="limit",
                take_profit=take_profit,
                stop_loss=stop_loss,
                action=action,
            )

            # Send email notification
            trade_data = {
                "user_email": portfolio.user.email,
                "symbol": stock.symbol,
                "quantity": quantity,
                "limit_price": price,
                "account_id": portfolio.account_id,
                "order_type": "limit",
                "action": action,
            }

            trade_type = (
                "competition" if isinstance(portfolio, CompetitionPortfolio) else "demo"
            )
            send_trade_notification(trade_type, "open_limit", trade_data)

            return position

        except Exception as e:
            raise ValidationError(f"Failed to create limit order: {str(e)}")

    def post(self, request, *args, **kwargs):
        try:
            account_type = kwargs.get("account_type")
            valid_account_types = ["demo_portfolio", "competition_account"]
            id = kwargs.get("id")

            if account_type not in valid_account_types:
                return Response(
                    {"error": f"Account type should be {valid_account_types}."},
                    status.HTTP_400_BAD_REQUEST,
                )

            # Get appropriate portfolio
            if account_type == "competition_account":
                competition = Competition.objects.filter(status="current").first()
                portfolio = self.get_competition_account(id, competition)
            else:
                portfolio = self.get_account(id)

            if not portfolio:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if portfolio.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            if not portfolio.can_trade:
                return Response(
                    {"error": "This account is not allowed to trade"},
                    status.HTTP_400_BAD_REQUEST,
                )

            # Validate input parameters
            symbol = request.data.get("symbol")
            order_id = request.data.get("order_id")
            quantity = int(request.data.get("quantity", 0))
            device_type = request.data.get("device_type")
            action = request.data.get("action")
            time_in_force = request.data.get("time_in_force", "day")
            order_type = request.data.get("order_type")
            take_profit = request.data.get("take_profit")
            stop_loss = request.data.get("stop_loss")

            if quantity <= 0:
                return Response(
                    {"error": "Invalid quantity."},
                    status.HTTP_400_BAD_REQUEST,
                )

            if take_profit:
                take_profit = float(take_profit)
            if stop_loss:
                stop_loss = float(stop_loss)

            stock = get_object_or_404(Stock, symbol=symbol)
            current_price = round(Decimal(get_price(symbol)["current_price"]), 2)

            # Validate take profit and stop loss
            if order_type == "market":
                self.validate_tp_sl_market(
                    action, current_price, take_profit, stop_loss
                )
                position = self.process_market_order(
                    portfolio,
                    stock,
                    quantity,
                    action,
                    current_price,
                    order_id,
                    take_profit,
                    stop_loss,
                    device_type,
                )
            elif order_type == "limit":
                price = float(request.data.get("price"))
                self.validate_tp_sl_limit(action, price, take_profit, stop_loss)
                position = self.process_limit_order(
                    portfolio,
                    stock,
                    quantity,
                    price,
                    action,
                    order_id,
                    take_profit,
                    stop_loss,
                    time_in_force,
                    device_type,
                )
            else:
                return Response(
                    {"error": "Invalid order type."},
                    status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"message": f"{action.title()} order placed successfully."},
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return Response({"error": str(e)}, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred."},
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def validate_tp_sl_market(self, action, current_price, take_profit, stop_loss):
        if take_profit:
            if action == "buy" and current_price >= take_profit:
                raise ValidationError("Take profit cannot be less than current price")
            elif action == "sell" and current_price <= take_profit:
                raise ValidationError(
                    "Take profit cannot be greater than current price"
                )

        if stop_loss:
            if action == "buy" and current_price <= stop_loss:
                raise ValidationError("Stop loss cannot be greater than current price")
            elif action == "sell" and current_price >= stop_loss:
                raise ValidationError("Stop loss cannot be less than current price")

    def validate_tp_sl_limit(self, action, price, take_profit, stop_loss):
        if take_profit:
            if action == "buy" and price >= take_profit:
                raise ValidationError("Take profit cannot be less than limit price")
            elif action == "sell" and price <= take_profit:
                raise ValidationError("Take profit cannot be greater than limit price")

        if stop_loss:
            if action == "buy" and price <= stop_loss:
                raise ValidationError("Stop loss cannot be greater than limit price")
            elif action == "sell" and price >= stop_loss:
                raise ValidationError("Stop loss cannot be less than limit price")


class NewDemoCloseTrade(APIView):
    permission_classes = [IsAuthenticated]

    def get_account(self, id):
        return DemoPortfolio.objects.filter(id=id).first()

    def get_competition_account(self, id, competition):
        return CompetitionPortfolio.objects.filter(
            competition=competition, active=True, id=id
        ).first()

    @transaction.atomic
    def _process_close_trade(self, position, user, device_type, transaction_model):
        """Process trade closure with improved transaction handling"""

        # Lock the portfolio
        portfolio = (
            type(position.portfolio)
            .objects.select_for_update()
            .get(id=position.portfolio.id)
        )

        pl, cur_val, price = position.calculate_profit_loss()
        trade_commission = round(
            Decimal(0.00435) * position.amount_invested, 2
        ) + Decimal("200")

        try:
            position.status = "close"
            position.close_price = Decimal(price)
            position.profit_loss = pl
            position.comment = "closed by trader"
            position.closed_at = timezone.now()
            position.save()

            # Update portfolio balance
            final_amount = position.amount_invested + pl - trade_commission
            portfolio.balance += final_amount
            portfolio.save()

            # Create transaction records
            transaction_model.objects.create(
                user=user,
                transaction_type="close trade",
                amount=cur_val,
                status="completed",
            )

            transaction_model.objects.create(
                user=user,
                transaction_type="trade commission",
                amount=trade_commission,
                status="completed",
            )

            # Send email notification
            trade_data = {
                "user_email": user.email,
                "symbol": position.stock.symbol,
                "quantity": position.quantity,
                "open_price": position.open_price,
                "close_price": price,
                "profit_loss": pl,
                "account_id": portfolio.account_id,
            }

            trade_type = (
                "competition" if isinstance(portfolio, CompetitionPortfolio) else "demo"
            )
            send_trade_notification(trade_type, "close", trade_data)

            return {
                "id": position.id,
                "stock": position.stock.symbol,
                "quantity": position.quantity,
                "open_price": position.open_price,
                "close_price": position.close_price,
                "open_time": position.created.isoformat(),
                "close_time": position.closed_at.isoformat(),
                "profit_loss": position.profit_loss,
                "order_id": position.order_id,
            }

        except Exception as e:
            # Rollback is automatic in atomic block
            raise ValidationError(f"Failed to close position: {str(e)}")

    def post(self, request, *args, **kwargs):
        try:
            account_type = kwargs.get("account_type")
            device_type = request.data.get("device_type")
            valid_account_types = ["demo_portfolio", "competition_account"]

            if account_type not in valid_account_types:
                return Response(
                    f"Account type should be {valid_account_types}.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            id = kwargs.get("id")
            position_id = kwargs.get("position_id")

            if account_type == "competition_account":
                competition = Competition.objects.filter(status="current").first()
                portfolio = self.get_competition_account(id, competition)
                position_model = CompetitionPosition
                transaction_model = CompetitionTransaction
            else:
                portfolio = self.get_account(id)
                position_model = DemoPosition
                transaction_model = DemoTransaction

            if not portfolio:
                return Response("Account not found", status.HTTP_404_NOT_FOUND)
            if portfolio.user != request.user:
                return Response("Permission denied", status.HTTP_403_FORBIDDEN)

            position = (
                position_model.objects.filter(portfolio=portfolio, id=position_id)
                .select_for_update()
                .first()
            )

            if not position:
                return Response("Position not found", status.HTTP_404_NOT_FOUND)

            if not position.stock.active:
                return Response("Stock is not active", status.HTTP_400_BAD_REQUEST)

            if position.status != "open":
                return Response("Position is not open", status.HTTP_400_BAD_REQUEST)

            result = self._process_close_trade(
                position=position,
                user=request.user,
                device_type=device_type,
                transaction_model=transaction_model,
            )

            return Response(result)

        except ValidationError as e:
            return Response({"error": str(e)}, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# def calculate_cumulative_returns(data: Union[QuerySet, List[Dict]]) -> List[Dict]:
#     """
#     Calculate cumulative returns as the SUM of daily returns (non-standard).
#     Handles both QuerySet and List[Dict] inputs.

#     Args:
#         data: Either a QuerySet of DailyReturns or a list of dictionaries containing returns data

#     Returns:
#         List[Dict]: List of dictionaries containing cumulative returns data
#     """
#     if not data:
#         return []

#     # Convert QuerySet to list of dictionaries if needed
#     if isinstance(data, QuerySet):
#         overview_data = [
#             {
#                 "portfolio_returns": item.portfolio_returns,
#                 "market_returns": item.market_returns,
#                 "date": item.created.date(),
#             }
#             for item in data
#         ]
#     else:
#         overview_data = data

#     # Convert to DataFrame
#     df = pd.DataFrame(overview_data)
#     if df.empty:
#         return []

#     # Calculate cumulative SUM of returns
#     df["portfolio_returns"] = df["portfolio_returns"].cumsum()
#     df["market_returns"] = df["market_returns"].cumsum()

#     # Round to 2 decimal places
#     df["portfolio_returns"] = df["portfolio_returns"].round(2)
#     df["market_returns"] = df["market_returns"].round(2)

#     # Ensure date is preserved in the output
#     return [
#         {
#             "portfolio_returns": row["portfolio_returns"],
#             "market_returns": row["market_returns"],
#             "date": row["date"],
#         }
#         for _, row in df.iterrows()
#     ]


# def calculate_cumulative_returns(
#     daily_returns_data: QuerySet,
#     portfolio: Union["DemoPortfolio", "CompetitionPortfolio"],
# ) -> List[Dict]:
#     """
#     Calculate cumulative returns with:
#     - Portfolio returns: calculated from daily total net P/L
#     - Market returns: cumulative sum of daily market returns

#     Args:
#         daily_returns_data: QuerySet of daily returns
#         portfolio: Portfolio object (Demo or Competition)

#     Returns:
#         List[Dict]: List containing dates and cumulative returns
#     """
#     if not daily_returns_data:
#         return []

#     # Get position model based on portfolio type
#     PositionModel = (
#         DemoPosition if isinstance(portfolio, DemoPortfolio) else CompetitionPosition
#     )

#     # Get all closed positions
#     positions = PositionModel.objects.filter(
#         portfolio=portfolio, status="close"
#     ).order_by("closed_at")

#     # Create DataFrame for positions with daily total P/L
#     positions_data = []
#     for position in positions:
#         net_pl = (
#             float(position.profit_loss - position.commission - position.swap_fee)
#             if isinstance(position, DemoPosition)
#             else float(position.profit_loss - position.commission)
#         )
#         date = position.closed_at.date()

#         # Add or update daily total
#         found = False
#         for entry in positions_data:
#             if entry["date"] == date:
#                 entry["pl"] += net_pl
#                 found = True
#                 break

#         if not found:
#             positions_data.append(
#                 {
#                     "date": date,
#                     "pl": net_pl,
#                     "balance": float(portfolio.initial_balance),
#                 }
#             )

#     if not positions_data:
#         return []

#     # Convert to DataFrame and sort by date
#     pos_df = pd.DataFrame(positions_data)
#     pos_df = pos_df.sort_values("date")

#     # Calculate cumulative P/L and returns
#     pos_df["cumulative_pl"] = pos_df["pl"].cumsum()
#     pos_df["portfolio_returns"] = (pos_df["cumulative_pl"] / pos_df["balance"]) * 100

#     # Create market returns DataFrame
#     market_data = [
#         {
#             "date": item.created.date(),
#             "market_returns": (
#                 item.market_returns if item.market_returns is not None else 0
#             ),
#         }
#         for item in daily_returns_data
#     ]
#     market_df = pd.DataFrame(market_data)

#     if not market_df.empty:
#         market_df["market_returns"] = market_df["market_returns"].fillna(0).cumsum()

#     # Merge portfolio and market returns on date
#     result_df = pos_df.merge(market_df, on="date", how="outer").sort_values("date")

#     # Forward fill missing values and replace NaN with 0
#     result_df["portfolio_returns"] = result_df["portfolio_returns"].ffill().fillna(0)
#     result_df["market_returns"] = result_df["market_returns"].ffill().fillna(0)

#     # Round results
#     result_df["portfolio_returns"] = result_df["portfolio_returns"].round(2)
#     result_df["market_returns"] = result_df["market_returns"].round(2)

#     # For debugging
#     print("Daily P/L and Returns:")
#     print(
#         result_df[
#             ["date", "pl", "cumulative_pl", "portfolio_returns", "market_returns"]
#         ]
#     )

#     # Convert to list of dictionaries, ensuring no NaN values
#     result = []
#     for _, row in result_df.iterrows():
#         entry = {
#             "date": row["date"],
#             "portfolio_returns": (
#                 float(row["portfolio_returns"])
#                 if pd.notnull(row["portfolio_returns"])
#                 else 0
#             ),
#             "market_returns": (
#                 float(row["market_returns"]) if pd.notnull(row["market_returns"]) else 0
#             ),
#         }
#         result.append(entry)

#     return result


# def calculate_cumulative_returns(
#     daily_returns_data: QuerySet,
#     portfolio: Union["DemoPortfolio", "CompetitionPortfolio"],
# ) -> List[Dict]:
#     """
#     Calculate cumulative returns with:
#     - Portfolio returns: calculated from daily total net P/L, starting from zero
#     - Market returns: cumulative sum of daily market returns

#     Args:
#         daily_returns_data: QuerySet of daily returns
#         portfolio: Portfolio object (Demo or Competition)

#     Returns:
#         List[Dict]: List containing dates and cumulative returns
#     """
#     if not daily_returns_data:
#         return []

#     # Get the first date from daily returns
#     first_daily_return = daily_returns_data.order_by("created").first()
#     if not first_daily_return:
#         return []

#     start_date = first_daily_return.created.date()

#     # Get position model based on portfolio type
#     PositionModel = (
#         DemoPosition if isinstance(portfolio, DemoPortfolio) else CompetitionPosition
#     )

#     # Initialize result with starting point
#     result = [{"date": start_date, "portfolio_returns": 0, "market_returns": 0}]

#     # Get all closed positions after start date
#     positions = PositionModel.objects.filter(
#         portfolio=portfolio, status="close", closed_at__date__gte=start_date
#     ).order_by("closed_at")

#     # Create DataFrame for positions with daily total P/L
#     positions_data = []
#     for position in positions:
#         net_pl = (
#             float(position.profit_loss - position.commission - position.swap_fee)
#             if isinstance(position, DemoPosition)
#             else float(position.profit_loss - position.commission)
#         )
#         date = position.closed_at.date()

#         # Add or update daily total
#         found = False
#         for entry in positions_data:
#             if entry["date"] == date:
#                 entry["pl"] += net_pl
#                 found = True
#                 break

#         if not found:
#             positions_data.append(
#                 {
#                     "date": date,
#                     "pl": net_pl,
#                     "balance": float(portfolio.initial_balance),
#                 }
#             )

#     if positions_data:
#         # Convert to DataFrame and sort by date
#         pos_df = pd.DataFrame(positions_data)
#         pos_df = pos_df.sort_values("date")

#         # Calculate cumulative P/L and returns
#         pos_df["cumulative_pl"] = pos_df["pl"].cumsum()
#         pos_df["portfolio_returns"] = (
#             pos_df["cumulative_pl"] / pos_df["balance"]
#         ) * 100

#         # Create market returns DataFrame
#         market_data = [
#             {
#                 "date": item.created.date(),
#                 "market_returns": (
#                     item.market_returns if item.market_returns is not None else 0
#                 ),
#             }
#             for item in daily_returns_data
#         ]
#         market_df = pd.DataFrame(market_data)

#         if not market_df.empty:
#             market_df["market_returns"] = market_df["market_returns"].fillna(0).cumsum()

#         # Merge portfolio and market returns on date
#         result_df = pos_df.merge(market_df, on="date", how="outer").sort_values("date")

#         # Forward fill missing values and replace NaN with 0
#         result_df["portfolio_returns"] = (
#             result_df["portfolio_returns"].ffill().fillna(0)
#         )
#         result_df["market_returns"] = result_df["market_returns"].ffill().fillna(0)

#         # Round results
#         result_df["portfolio_returns"] = result_df["portfolio_returns"].round(2)
#         result_df["market_returns"] = result_df["market_returns"].round(2)

#         # Convert to list of dictionaries, ensuring no NaN values
#         result.extend(
#             [
#                 {
#                     "date": row["date"],
#                     "portfolio_returns": (
#                         float(row["portfolio_returns"])
#                         if pd.notnull(row["portfolio_returns"])
#                         else 0
#                     ),
#                     "market_returns": (
#                         float(row["market_returns"])
#                         if pd.notnull(row["market_returns"])
#                         else 0
#                     ),
#                 }
#                 for _, row in result_df.iterrows()
#                 if row["date"]
#                 > start_date  # Skip the start date as we already added it
#             ]
#         )

#     return result


def calculate_cumulative_returns(
    daily_returns_data: QuerySet,
    portfolio: Union["DemoPortfolio", "CompetitionPortfolio"],
) -> List[Dict]:
    """
    Calculate cumulative returns with:
    - Portfolio returns: starting from 0, followed by actual returns
    - Market returns: cumulative sum of daily market returns
    """
    if not daily_returns_data:
        return []

    # Get the first date from daily returns
    first_daily_return = daily_returns_data.order_by("created").first()
    if not first_daily_return:
        return []

    start_date = first_daily_return.created.date()

    # Get position model based on portfolio type
    PositionModel = (
        DemoPosition if isinstance(portfolio, DemoPortfolio) else CompetitionPosition
    )

    # Get all closed positions including start date
    positions = PositionModel.objects.filter(
        portfolio=portfolio, status="close", closed_at__date__gte=start_date
    ).order_by("closed_at")

    # Create DataFrame for positions with daily total P/L
    positions_data = []
    for position in positions:
        net_pl = (
            float(position.profit_loss - position.commission - position.swap_fee)
            if isinstance(position, DemoPosition)
            else float(position.profit_loss - position.commission)
        )
        date = position.closed_at.date()

        # Add or update daily total
        found = False
        for entry in positions_data:
            if entry["date"] == date:
                entry["pl"] += net_pl
                found = True
                break

        if not found:
            positions_data.append(
                {
                    "date": date,
                    "pl": net_pl,
                    "balance": float(portfolio.initial_balance),
                }
            )

    # Create market returns DataFrame
    market_data = [
        {
            "date": item.created.date(),
            "market_returns": (
                item.market_returns if item.market_returns is not None else 0
            ),
        }
        for item in daily_returns_data
    ]
    market_df = pd.DataFrame(market_data)

    if not market_df.empty:
        market_df["market_returns"] = market_df["market_returns"].fillna(0).cumsum()

    # Initialize result with starting point
    result = [{"date": start_date, "portfolio_returns": 0, "market_returns": 0}]

    if positions_data:
        # Convert to DataFrame and sort by date
        pos_df = pd.DataFrame(positions_data)
        pos_df = pos_df.sort_values("date")

        # Calculate cumulative P/L and returns
        pos_df["cumulative_pl"] = pos_df["pl"].cumsum()
        pos_df["portfolio_returns"] = (
            pos_df["cumulative_pl"] / pos_df["balance"]
        ) * 100

        # Merge portfolio and market returns on date
        result_df = pos_df.merge(market_df, on="date", how="outer").sort_values("date")

        # Forward fill missing values and replace NaN with 0
        result_df["portfolio_returns"] = (
            result_df["portfolio_returns"].ffill().fillna(0)
        )
        result_df["market_returns"] = result_df["market_returns"].ffill().fillna(0)

        # Round results
        result_df["portfolio_returns"] = result_df["portfolio_returns"].round(2)
        result_df["market_returns"] = result_df["market_returns"].round(2)

        # Handle start date - only add second entry if there was actual P/L
        start_date_data = result_df[result_df["date"] == start_date]
        if (
            not start_date_data.empty
            and abs(start_date_data.iloc[-1]["portfolio_returns"]) > 0
        ):
            result.append(
                {
                    "date": start_date,
                    "portfolio_returns": float(
                        start_date_data.iloc[-1]["portfolio_returns"]
                    ),
                    "market_returns": float(start_date_data.iloc[-1]["market_returns"]),
                }
            )

        # Add all other dates
        for _, row in result_df[result_df["date"] > start_date].iterrows():
            result.append(
                {
                    "date": row["date"],
                    "portfolio_returns": float(row["portfolio_returns"]),
                    "market_returns": float(row["market_returns"]),
                }
            )

    # For debugging
    print("Cumulative Returns Data:")
    for r in result:
        print(
            f"Date: {r['date']}, Portfolio: {r['portfolio_returns']}, Market: {r['market_returns']}"
        )

    return result


@dataclass
class AccountMetrics:
    balance: Decimal
    equity: Decimal
    floating_pl: Decimal
    closed_pl: Decimal
    remaining_balance: Decimal
    open_balance: Decimal


class PortfolioCalculator:
    """Handles calculations for portfolio metrics"""

    @staticmethod
    def calculate_open_positions(
        positions: List[Any],
    ) -> Tuple[Decimal, List[Dict], List[Dict]]:
        """Calculate metrics for open positions and return formatted position data"""

        def process_position(position):
            pl, cur_val, _ = position.calculate_profit_loss()
            position_detail = {
                "stock": position.stock.symbol,
                "current_value": round(cur_val, 2),
                "pl": pl,
                "open_date": position.created,
            }

            position_summary = {"symbol": position.stock.symbol, "profit_loss": pl}

            return pl, position_detail, position_summary

        with ThreadPoolExecutor() as executor:
            results = list(executor.map(process_position, positions))

        total_pl = sum(r[0] for r in results)
        position_details = [r[1] for r in results]
        position_summaries = [r[2] for r in results]

        return total_pl, position_details, position_summaries

    @staticmethod
    def calculate_closed_positions(positions: List[Any]) -> Tuple[Decimal, List[Dict]]:
        """Calculate metrics for closed positions"""
        closed_positions = [
            {
                "stock": pos.stock.symbol,
                "profit_loss": pos.profit_loss - pos.commission,
                "close_date": pos.closed_at,
            }
            for pos in positions
        ]

        total_pl = sum(pos.profit_loss - pos.commission for pos in positions)
        return total_pl, closed_positions


@dataclass
class PositionMetrics:
    profit_loss: Decimal
    current_value: Decimal
    commission: Decimal
    swap_fee: Decimal = Decimal(0)
    percent_change: float = 0.0


class EnhancedPortfolioCalculator(PortfolioCalculator):
    """Enhanced calculator for portfolio metrics including detailed position analysis"""

    @staticmethod
    def calculate_position_metrics(
        position: Union[DemoPosition, CompetitionPosition]
    ) -> PositionMetrics:
        """Calculate core metrics for a single position"""

        if position.status == "open":
            price = position.current_price
            current_value = Decimal(str(round(position.quantity * price, 2)))

            if position.action == "buy":
                profit_loss = current_value - position.amount_invested
            else:  # sell
                profit_loss = position.amount_invested - current_value

            commission = Decimal("0")
            swap_fee = Decimal("0")

        elif position.status == "close":
            current_value = Decimal(str(position.quantity * position.close_price))
            profit_loss = Decimal(str(position.profit_loss))
            commission = Decimal(str(position.commission))
            swap_fee = (
                Decimal(str(position.swap_fee))
                if hasattr(position, "swap_fee")
                else Decimal("0")
            )
        else:
            return PositionMetrics(
                profit_loss=Decimal("0"),
                current_value=Decimal("0"),
                commission=Decimal("0"),
            )

        # Calculate percent change
        percent_change = (
            round(float(profit_loss) / float(position.amount_invested) * 100, 2)
            if position.amount_invested != 0
            else 0.0
        )

        return PositionMetrics(
            profit_loss=profit_loss,
            current_value=current_value,
            commission=commission,
            swap_fee=swap_fee,
            percent_change=percent_change,
        )

    @staticmethod
    def format_position_data(
        position: Union[DemoPosition, CompetitionPosition],
        metrics: PositionMetrics,
        price: Decimal,
    ) -> Dict:
        """Format position data into standardized dictionary"""

        base_data = {
            "id": position.id,
            "stock": position.stock.symbol,
            "logo_url": position.stock.logo_url,
            "shares": position.quantity,
            "avg_cost": position.open_price,
            "close_price": position.close_price,
            "ltp": price,
            "open_time": position.created.isoformat(),
            "close_time": position.closed_at.isoformat() if position.closed_at else "-",
            "change": round(metrics.profit_loss, 2),
            "percent_change": metrics.percent_change,
            "cur_val": metrics.current_value,
            "avg_volume": "3300",
            "volume": "66000",
            "status": position.status,
            "invested": position.amount_invested,
            "profit_loss": round(metrics.profit_loss, 2),
            "side": position.action,
            "order": position.order_type,
            "order_id": position.order_id,
            "take_profit": position.take_profit,
            "stop_loss": position.stop_loss,
            "trailing_sl": position.trailing_stop_loss,
            "comment": position.comment,
            "commission": metrics.commission,
            "net_profit_loss": round(
                float(metrics.profit_loss)
                - float(metrics.commission)
                - float(metrics.swap_fee),
                2,
            ),
        }

        if isinstance(position, DemoPosition):
            base_data["swap_fee"] = [metrics.swap_fee]

        return base_data

    def calculate_portfolio_metrics(
        self,
        portfolio: Union[DemoPortfolio, CompetitionPortfolio],
        positions: List[Union[DemoPosition, CompetitionPosition]],
    ) -> Dict:
        """Calculate complete portfolio metrics"""

        all_positions_data = []
        total_floating_pl = Decimal("0")
        total_closed_pl = Decimal("0")
        open_balance = Decimal("0")

        for position in positions:
            metrics = self.calculate_position_metrics(position)
            position_data = self.format_position_data(
                position,
                metrics,
                (
                    position.current_price
                    if position.status == "open"
                    else position.close_price
                ),
            )

            all_positions_data.append(position_data)

            if position.status == "open":
                total_floating_pl += metrics.profit_loss
                open_balance += position.amount_invested
            else:
                total_closed_pl += Decimal(str(position_data["net_profit_loss"]))

        # Calculate final balance and equity
        initial_balance = portfolio.initial_balance
        current_balance = initial_balance + total_closed_pl
        equity = current_balance + total_floating_pl

        return {
            "balance": current_balance,
            "floating_pl": float(total_floating_pl),
            "closed_pl": float(total_closed_pl),
            "equity": float(equity),
            "holdings": all_positions_data,
        }


class NewDemoHolding(APIView):
    calculator = EnhancedPortfolioCalculator()

    def get(self, request, *args, **kwargs):
        account_type = kwargs.get("account_type")
        account_id = kwargs.get("id")

        if account_type not in ["demo_portfolio", "competition_account"]:
            return Response("Invalid account type", status=status.HTTP_400_BAD_REQUEST)

        # Get appropriate portfolio
        if account_type == "demo_portfolio":
            portfolio = DemoPortfolio.objects.filter(id=account_id).first()
            position_model = DemoPosition
        else:
            portfolio = CompetitionPortfolio.objects.filter(
                id=account_id, active=True
            ).first()
            position_model = CompetitionPosition

        if not portfolio:
            return Response("Account not found", status=status.HTTP_404_NOT_FOUND)

        # if portfolio.user != request.user:
        #     return Response("Permission denied", status=status.HTTP_403_FORBIDDEN)

        # Get positions
        positions = position_model.objects.filter(portfolio=portfolio).order_by(
            "-closed_at"
        )

        # Calculate metrics
        portfolio_data = self.calculator.calculate_portfolio_metrics(
            portfolio, positions
        )

        return Response(portfolio_data)


class NewHome(APIView):
    """API view for handling portfolio data"""

    VALID_ACCOUNT_TYPES = {
        "demo_portfolio": (DemoPortfolio, DemoPosition, DemoDailyReturns2),
        "competition_account": (
            CompetitionPortfolio,
            CompetitionPosition,
            CompetitionDailyReturns2,
        ),
    }

    def get_account(self, account_type: str, account_id: int, user) -> Optional[Any]:
        """Get account based on type and ID"""
        AccountModel = self.VALID_ACCOUNT_TYPES[account_type][0]

        account = AccountModel.objects.filter(id=account_id).first()

        if not account:
            return None
        # if account.user != user:
        #     return None

        return account

    def calculate_account_metrics(
        self, portfolio, positions, positions_closed
    ) -> Tuple[AccountMetrics, Dict]:
        """Calculate main account metrics and position data"""

        # Calculate metrics for open positions
        floating_pl, position_details, open_positions = (
            PortfolioCalculator.calculate_open_positions(positions)
        )

        # Calculate metrics for closed positions
        closed_pl, closed_positions = PortfolioCalculator.calculate_closed_positions(
            positions_closed
        )

        # Adjust closed PL for swap fees if applicable
        if hasattr(portfolio, "get_swap_fees"):
            closed_pl -= portfolio.get_swap_fees()

        open_balance = sum(position.amount_invested for position in positions)
        initial_balance = Decimal(portfolio.initial_balance)

        # Calculate final metrics
        balance = round(float(initial_balance) + closed_pl, 2)
        equity = balance + float(floating_pl)

        metrics = AccountMetrics(
            balance=balance,
            equity=equity,
            floating_pl=floating_pl,
            closed_pl=closed_pl,
            remaining_balance=portfolio.balance,
            open_balance=open_balance,
        )

        position_data = {
            "open_positions": open_positions,
            "close_positions": closed_positions,
            "current_value": position_details,
        }

        return metrics, position_data

    def get(self, request, *args, **kwargs):
        account_type = kwargs.get("account_type")
        account_id = kwargs.get("id")

        if account_type not in self.VALID_ACCOUNT_TYPES:
            return Response(
                f"Account type should be one of {list(self.VALID_ACCOUNT_TYPES.keys())}.",
                status.HTTP_400_BAD_REQUEST,
            )

        # Get account and verify access
        account = self.get_account(account_type, account_id, request.user)
        if not account:
            return Response(
                "Account not found or access denied", status.HTTP_404_NOT_FOUND
            )

        # Get position model based on account type
        PositionModel = self.VALID_ACCOUNT_TYPES[account_type][1]

        # Get positions
        positions = PositionModel.objects.filter(portfolio=account, status="open")
        positions_closed = PositionModel.objects.filter(
            portfolio=account, status="close"
        )

        # Calculate metrics and position data
        metrics, position_data = self.calculate_account_metrics(
            account, positions, positions_closed
        )

        # Calculate historical data and returns
        daily_returns = (
            self.VALID_ACCOUNT_TYPES[account_type][2]
            .objects.filter(portfolio=account)
            .order_by("created")
        )

        # Calculate positions history
        # positions_history = self.calculate_positions_history(positions_closed)

        data = {
            "balance": round(metrics.balance, 2),
            "starting_balance": float(account.initial_balance),
            "equity": metrics.equity,
            "floating_pl": metrics.floating_pl,
            "closed_pl": metrics.closed_pl,
            "remaining_balance": metrics.remaining_balance,
            "overview": self.get_returns_overview(daily_returns),
            # "cumulative_overview": calculate_cumulative_returns(daily_returns),
            "cumulative_overview": calculate_cumulative_returns(daily_returns, account),
            "calendar": self.get_calendar_data(daily_returns),
            # "positions": positions_history,
            # "current_value": position_data["current_value"],
            "close_positions": position_data["close_positions"],
            "open_positions": position_data["open_positions"],
        }

        return Response(data, status=status.HTTP_200_OK)

    def calculate_positions_history(self, closed_positions) -> List[Dict]:
        """Calculate historical position data by date"""
        today = timezone.now()
        position_data_dict = {}

        # Group closed positions by date
        for position in closed_positions:
            if position.closed_at.month == today.month:
                date_key = position.closed_at.date()
                daily_pl = position.profit_loss - position.commission
                position_data_dict[date_key] = (
                    position_data_dict.get(date_key, 0) + daily_pl
                )

        # If no positions exist, use today as start date
        if position_data_dict:
            start_date = min(position_data_dict.keys())
        else:
            start_date = today.date()

        # Create final list with all weekdays
        final_list = [
            {
                "profit_loss": position_data_dict.get(date, 0),
                "date": date.strftime("%Y-%m-%d"),
            }
            for date in (
                start_date + timedelta(n)
                for n in range((today.date() - start_date).days + 1)
                if (start_date + timedelta(n)).weekday() < 5  # Exclude weekends
            )
        ]

        return final_list

    @staticmethod
    def get_returns_overview(daily_returns) -> List[Dict]:
        """Generate returns overview from daily returns data"""
        if len(daily_returns) <= 1:
            return []

        return [
            {
                "portfolio_returns": returns.portfolio_returns,
                "market_returns": returns.market_returns,
                "date": returns.created.date(),
            }
            for returns in daily_returns
        ]

    @staticmethod
    def get_calendar_data(daily_returns) -> List[Dict]:
        """Generate calendar data from daily returns"""
        if len(daily_returns) <= 1:
            return []

        return [
            {
                "date": daily.created.date(),
                "return": daily.portfolio_returns,
            }
            for daily in daily_returns[1:]
        ]

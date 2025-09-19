# external_trading/services/trading_service.py
from decimal import Decimal

import shortuuid
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from execution.models import CompetitionPortfolio, DemoPortfolio, DemoPosition, Stock
from execution.utils import send_trade_notification
from execution.views2 import get_position
from portfolio.models import DemoTransaction
from portfolio.utils import get_price, get_stockdata2


class TradingService:
    """Service class for handling trading operations"""

    @staticmethod
    def validate_portfolio(portfolio):
        """Validate if portfolio can trade"""
        if getattr(portfolio, "is_prop", False):
            if not portfolio.is_active:
                raise ValidationError("Account is inactive")
            if portfolio.blown:
                raise ValidationError("Account is blown")
            if portfolio.inactive_by_inactivity:
                raise ValidationError("Account is inactive")

        if not portfolio.can_trade:
            raise ValidationError("Account is inactive")

        return True

    @staticmethod
    def get_account(account_type, account_id, user):
        """Get portfolio account based on type and id"""
        if account_type == "demo_portfolio":
            portfolio = DemoPortfolio.objects.filter(account_id=account_id).first()
            if not portfolio or portfolio.user != user:
                raise ValidationError("Account not found or access denied")
            return portfolio, DemoPosition
        else:
            raise ValidationError(f"Invalid account type: {account_type}")

    @staticmethod
    def validate_tp_sl_market(action, current_price, take_profit, stop_loss):
        """Validate take profit and stop loss for market orders"""
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

    @staticmethod
    def validate_tp_sl_limit(action, price, take_profit, stop_loss):
        """Validate take profit and stop loss for limit orders"""
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

    @staticmethod
    @transaction.atomic
    def process_market_order(
        portfolio,
        symbol,
        quantity,
        action,
        order_id,
        take_profit,
        stop_loss,
        device_type,
    ):
        """Process market order with transaction handling"""
        # Validate portfolio
        TradingService.validate_portfolio(portfolio)

        # Get stock and current price
        stock = get_object_or_404(Stock, symbol=symbol)
        current_price = round(Decimal(get_price(symbol)["current_price"]), 2)

        # Validate take profit and stop loss
        if take_profit or stop_loss:
            take_profit_value = float(take_profit) if take_profit else None
            stop_loss_value = float(stop_loss) if stop_loss else None
            TradingService.validate_tp_sl_market(
                action, float(current_price), take_profit_value, stop_loss_value
            )

        # Calculate trade details
        amount = quantity * current_price
        trade_commission = round(Decimal(0.00435) * amount, 2) + Decimal("200")
        total = amount

        # Check sufficient funds
        if portfolio.balance < total:
            raise ValidationError("Insufficient funds to trade")

        # Lock the portfolio row
        portfolio = type(portfolio).objects.select_for_update().get(id=portfolio.id)

        # Deduct balance first
        portfolio.balance -= total
        portfolio.save()

        position_model = DemoPosition

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

    @staticmethod
    @transaction.atomic
    def process_limit_order(
        portfolio,
        symbol,
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
        # Validate portfolio
        TradingService.validate_portfolio(portfolio)

        # Get stock
        stock = get_object_or_404(Stock, symbol=symbol)

        # Validate take profit and stop loss
        if take_profit or stop_loss:
            take_profit_value = float(take_profit) if take_profit else None
            stop_loss_value = float(stop_loss) if stop_loss else None
            TradingService.validate_tp_sl_limit(
                action, float(price), take_profit_value, stop_loss_value
            )

        position_model = DemoPosition

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
            # send_trade_notification(trade_type, "open_limit", trade_data)

            return position

        except Exception as e:
            raise ValidationError(f"Failed to create limit order: {str(e)}")

    @staticmethod
    @transaction.atomic
    def close_trade(portfolio, position_id):
        """Close a specific trade"""
        position_model = DemoPosition

        # Get and validate position with lock
        position = (
            position_model.objects.select_for_update()
            .filter(portfolio=portfolio, id=position_id)
            .first()
        )

        if not position:
            raise ValidationError("Position not found")
        if not position.stock.active:
            raise ValidationError("Stock is not active")
        if position.status != "open":
            raise ValidationError("Position is not open")

        # Calculate profit/loss
        pl, cur_val, price = position.calculate_profit_loss()
        trade_commission = round(
            Decimal("0.00435") * position.amount_invested, 2
        ) + Decimal("200")
        final_amount = position.amount_invested + pl - trade_commission

        # Update position
        position.status = "close"
        position.close_price = Decimal(price)
        position.profit_loss = pl
        position.comment = "closed by trader"
        position.closed_at = timezone.now()
        position.save()

        # Update portfolio balance
        portfolio.balance += final_amount
        portfolio.save()

        # Create transaction records
        transaction_model = DemoTransaction

        transaction_model.objects.create(
            user=portfolio.user,
            transaction_type="close trade",
            amount=cur_val,
            status="completed",
        )

        transaction_model.objects.create(
            user=portfolio.user,
            transaction_type="trade commission",
            amount=trade_commission,
            status="completed",
        )

        # Send notification
        trade_notification_data = {
            "user_email": portfolio.user.email,
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
        send_trade_notification(trade_type, "close", trade_notification_data)

        # Return trade details
        return {
            "id": position.id,
            "stock": position.stock.symbol,
            "quantity": position.quantity,
            "open_price": position.open_price,
            "close_price": price,
            "open_time": position.created.isoformat(),
            "close_time": timezone.now().isoformat(),
            "profit_loss": pl,
            "order_id": position.order_id,
            "commission": trade_commission,
            "final_amount": final_amount,
            "current_value": cur_val,
        }

    @staticmethod
    @transaction.atomic
    def close_all_trades(portfolio):
        """Close all open trades in an account"""
        position_model = DemoPosition

        # Get all open positions with lock
        open_positions = position_model.objects.select_for_update().filter(
            portfolio=portfolio, status="open"
        )

        if not open_positions.exists():
            raise ValidationError("No open positions found")

        closed_positions_data = []
        total_final_amount = Decimal("0")

        transaction_model = DemoTransaction

        # Process each position
        for position in open_positions:
            if not position.stock.active:
                # Skip inactive stocks
                continue

            # Calculate profit/loss
            pl, cur_val, price = position.calculate_profit_loss()
            trade_commission = round(
                Decimal("0.00435") * position.amount_invested, 2
            ) + Decimal("200")
            final_amount = position.amount_invested + pl - trade_commission
            total_final_amount += final_amount

            # Update position
            position.status = "close"
            position.close_price = Decimal(price)
            position.profit_loss = pl
            position.comment = "closed by trader (bulk closure)"
            position.closed_at = timezone.now()
            position.save()

            # Create transaction records
            transaction_model.objects.create(
                user=portfolio.user,
                transaction_type="close trade",
                amount=cur_val,
                status="completed",
            )

            transaction_model.objects.create(
                user=portfolio.user,
                transaction_type="trade commission",
                amount=trade_commission,
                status="completed",
            )

            # Send notification
            trade_notification_data = {
                "user_email": portfolio.user.email,
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
            send_trade_notification(trade_type, "close", trade_notification_data)

            closed_positions_data.append(
                {
                    "id": position.id,
                    "stock": position.stock.symbol,
                    "quantity": position.quantity,
                    "open_price": position.open_price,
                    "close_price": price,
                    "open_time": position.created.isoformat(),
                    "close_time": timezone.now().isoformat(),
                    "profit_loss": pl,
                    "order_id": position.order_id,
                    "commission": trade_commission,
                    "final_amount": final_amount,
                    "current_value": cur_val,
                }
            )

        # Update portfolio balance if positions were closed
        if closed_positions_data:
            portfolio.balance += total_final_amount
            portfolio.save()

        return {
            "closed_positions": closed_positions_data,
            "total_positions_closed": len(closed_positions_data),
            "total_final_amount": total_final_amount,
        }

    @staticmethod
    def get_open_positions(portfolio):
        """Get all open positions for a portfolio"""
        position_model = DemoPosition

        positions = position_model.objects.filter(
            portfolio=portfolio, status="open", order_id__startswith="ext"
        )

        all_prices = get_stockdata2()
        position_data = get_position(all_prices, positions)
        print(position_data)

        return position_data

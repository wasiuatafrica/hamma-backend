from datetime import timedelta
from decimal import Decimal

import pytz
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from execution.models import DemoPortfolio, DemoPosition

from .models import Payout
from .pay_service import PayoutService
from .serializers import PayoutDetailSerializer
from .utils import get_account_data, get_equity_balance


class PayoutListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get list of payouts"""
        if request.user.is_staff:
            payouts = Payout.objects.all()
        else:
            payouts = Payout.objects.filter(portfolio__user=request.user)

        serializer = PayoutDetailSerializer(payouts, many=True)
        return Response(serializer.data)


class PayoutDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            payout = Payout.objects.get(pk=pk)
            if (
                not self.request.user.is_staff
                and payout.portfolio.user != self.request.user
            ):
                raise Payout.DoesNotExist
            return payout
        except Payout.DoesNotExist:
            return None

    def get(self, request, pk):
        """Get payout detail"""
        payout = self.get_object(pk)
        if not payout:
            return Response(
                {"error": "Payout not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = PayoutDetailSerializer(payout)
        return Response(serializer.data)


class RequestPayoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Request a new payout"""
        portfolio_id = request.data.get("portfolio_id")
        if not portfolio_id:
            return Response(
                {"error": "Portfolio ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            portfolio = DemoPortfolio.objects.get(
                account_id=portfolio_id, user=request.user
            )

            payout_service = PayoutService(portfolio)
            is_eligible, conditions = payout_service.check_payout_eligibility()

            # Prepare detailed error messages for failed conditions
            error_messages = {
                "minimum_trading_days": "Minimum trading days requirement not met (2 days per week required)",
                "profit_target_met": "No profit available for payout",
                "drawdown_limits": "Account has exceeded drawdown limits",
                "minimum_trades": "Minimum trades requirement not met",
                "active_account": "Account is not active or has been blown",
                "payout_timing": "Payout request can only be made on Fridays",
                "no_open_trades": "Cannot request payout while having open trades",
            }

            if not is_eligible:
                failed_conditions = []
                for condition, passed in conditions.items():
                    if not passed:
                        failed_conditions.append(
                            {
                                "condition": condition,
                                "message": error_messages.get(
                                    condition, "Condition not met"
                                ),
                            }
                        )

                return Response(
                    {
                        "error": "Payout conditions not met",
                        "failed_conditions": failed_conditions,
                        "details": {
                            "open_trades_count": DemoPosition.objects.filter(
                                portfolio=portfolio, status="open"
                            ).count(),
                            "trading_days_this_week": DemoPosition.objects.filter(
                                portfolio=portfolio,
                                created__gte=timezone.now() - timedelta(days=7),
                                status="close",
                            )
                            .dates("created", "day")
                            .count(),
                            "current_profit": float(
                                get_equity_balance(portfolio)["equity"]
                                - portfolio.initial_balance
                            ),
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check specifically for open trades and provide detailed information
            open_positions = DemoPosition.objects.filter(
                portfolio=portfolio, status="open"
            )
            if open_positions.exists():
                open_trades_info = [
                    {
                        "symbol": pos.stock.symbol,
                        "quantity": pos.quantity,
                        "open_price": float(pos.open_price),
                        "action": pos.action,
                        "opened_at": pos.created.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for pos in open_positions
                ]

                return Response(
                    {
                        "error": "Cannot request payout while having open trades",
                        "open_trades": open_trades_info,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            payout = payout_service.process_payout_request()
            serializer = PayoutDetailSerializer(payout)

            return Response(
                {
                    "message": "Payout request submitted successfully",
                    "data": serializer.data,
                    "details": {
                        "payout_amount": float(payout.amount),
                        "profit_percentage": float(payout.profit_percentage),
                        "week_number": payout.week_number,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except DemoPortfolio.DoesNotExist:
            return Response(
                {"error": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProcessPayoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Payout.objects.get(pk=pk)
        except Payout.DoesNotExist:
            return None

    def post(self, request, pk):
        """Process (approve/reject) a payout request"""
        if not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        payout = self.get_object(pk)
        if not payout:
            return Response(
                {"error": "Payout not found"}, status=status.HTTP_404_NOT_FOUND
            )

        action = request.data.get("action")

        if action not in ["approve", "reject"]:
            return Response(
                {"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if action == "approve":
                payout.status = "approved"
                payout.process_date = timezone.now()
                payout.processed_by = request.user
            else:
                reason = request.data.get("reason")
                if not reason:
                    return Response(
                        {"error": "Reason is required for rejection"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                payout.status = "rejected"
                payout.rejected_reason = reason

            payout.admin_notes = request.data.get("notes")
            payout.save()

            return Response(PayoutDetailSerializer(payout).data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PortfolioMetrics(APIView):

    def get(self, request, portfolio_id):
        # try:
        portfolio = DemoPortfolio.objects.get(account_id=portfolio_id)

        # Get timezone
        wat = pytz.timezone("Africa/Lagos")
        current_time = timezone.now().astimezone(wat)

        # Get historical data for the last 14 days
        historical_data = get_account_data(portfolio_id)

        # Get current balance, equity and positions data
        current_data = get_equity_balance(portfolio)
        current_balance = Decimal(str(current_data["balance"]))
        current_equity = Decimal(str(current_data["equity"]))

        # Calculate profit/loss
        initial_balance = portfolio.initial_balance
        profit_loss = current_equity - initial_balance

        # Get positions for the last 14 days
        two_weeks_ago = current_time - timedelta(days=14)
        positions = DemoPosition.objects.filter(
            portfolio=portfolio, created__gte=two_weeks_ago
        )

        # Calculate trades count and win rate
        closed_positions = positions.filter(status="close")
        total_trades = closed_positions.count()
        winning_trades = closed_positions.filter(profit_loss__gt=0).count()
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Calculate drawdown
        if historical_data:
            peak_equity = max([data["equity"] for data in historical_data])
            current_drawdown = peak_equity - float(current_equity)
        else:
            current_drawdown = 0 if profit_loss > 0 else abs(profit_loss)

        # Get trading days (count unique days with trades)
        trading_days = len(
            set(
                position.created.astimezone(wat).date()
                for position in positions
                if position.created >= two_weeks_ago
            )
        )

        # Get daily drawdown limit
        daily_dd_limit = portfolio.account_drawdown_limit or Decimal("120000")

        response_data = {
            "metrics": {
                "balance": f"{current_balance:.2f}",
                "equity": f"{current_equity:.2f}",
                "profit_loss": f"{profit_loss:.2f}",
                "drawdown": f"{current_drawdown:.2f}",
                "trading_days": trading_days,
                "trades": total_trades,
                "win_rate": f"{win_rate:.2f}%",
            },
            "trading_objectives": {
                "daily_drawdown": {
                    "max_dd_limit": f"{daily_dd_limit:.2f}",
                    "today_dd_limit": f"{daily_dd_limit:.2f}",
                },
                "trading_days": {
                    "minimum": 5,
                    "current": trading_days,
                    "status": "Passed" if trading_days >= 5 else "Not Passed",
                },
                "profit_target": {
                    "minimum": "750000.00",
                    "current": f"{profit_loss:.2f}",
                    "status": "Passed" if profit_loss >= 750000 else "Not Passed",
                },
            },
            "last_updated": current_time.strftime("%Y-%m-%d %H:%M"),
        }

        # Calculate open positions P/L
        open_positions = positions.filter(status="open")
        open_positions_data = []
        total_open_pl = Decimal("0")

        for position in open_positions:
            pl, current_value, price = position.calculate_profit_loss()
            total_open_pl += pl
            position_data = {
                "symbol": position.stock.symbol,
                "quantity": position.quantity,
                "entry_price": float(position.open_price),
                "current_price": price,
                "profit_loss": float(pl),
                "action": position.action,
            }
            open_positions_data.append(position_data)

        response_data["open_positions"] = {
            "positions": open_positions_data,
            "total_pl": float(total_open_pl),
        }

        return Response(response_data)


class AccountDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, account_id):
        try:
            account_data = get_account_data(account_id)
            return Response(account_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

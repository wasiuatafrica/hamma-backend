import logging
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import AdminUserActivityLog, Referral
from affilate.models import ReferralWallet, ReferralWithdrawalRequest, RewardActivities
from affilate.serializers import (
    ReferralRewardPayoutSerializer,
    ReferralWalletSerializer,
    ReferralWithdrawalRequestSerializer,
    RewardActivitiesSerializer,
)
from anyon.serializers import AdminReceiptsViewSerializer
from execution.models import DemoPortfolio, DemoPosition, PropReceipt
from notifications.utils import save_and_send_notification
from portfolio.models import PayStackReceipts, Receipts

from .models import Payout
from .pay_service import PayoutService
from .serializers import AccountlistSerializer, PayoutDetailSerializer
from .utils import get_account_data, get_equity_balance

logger = logging.getLogger(__name__)


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
            portfolio = DemoPortfolio.objects.get(id=portfolio_id, user=request.user)

            payout_service = PayoutService(portfolio)
            is_eligible, conditions = payout_service.check_payout_eligibility()

            # Prepare detailed error messages for failed conditions
            error_messages = {
                "minimum_trading_days": "Minimum trading days requirement not met (2 days per week required)",
                "profit_target_met": "No profit available for payout",
                "drawdown_limits": "Account has exceeded drawdown limits",
                "minimum_trades": "Minimum trades requirement not met",
                "active_account": "Account is not active or has been blown",
                "payout_timing": "Payout request can only be made between Wednesdays and 12pm on Fridays",
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
                        "opened_at": pos.created.strftime("%Y-%m-%d %H:%M"),
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
        profit_loss = current_balance - initial_balance

        # Get positions for the last 14 days
        two_weeks_ago = current_time - timedelta(days=14)
        positions = DemoPosition.objects.filter(
            portfolio=portfolio  # , created__gte=two_weeks_ago
        )

        # Calculate trades count and win rate
        closed_positions = positions.filter(status="close")
        total_trades = closed_positions.count()
        winning_trades = closed_positions.filter(profit_loss__gt=0).count()
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Calculate drawdown
        if historical_data:
            least_equity = min([data["equity"] for data in historical_data])
            least_balance = min([data["balance"] for data in historical_data])

            current_drawdown = float(initial_balance) - min(least_equity, least_balance)
        else:
            current_drawdown = 0

        # Get trading days (count unique days with trades)
        trading_days = len(
            set(
                position.created.astimezone(wat).date()
                for position in positions
                # if position.created >= two_weeks_ago
            )
        )

        # Get daily drawdown limit
        daily_dd_limit = portfolio.account_drawdown_limit or Decimal("120000")

        response_data = {
            "metrics": {
                "balance": f"{current_balance:.2f}",
                "equity": f"{current_equity:.2f}",
                "floating_profit_loss": f"{profit_loss:.2f}",
                "drawdown": f"{current_drawdown:.2f}",
                "trading_days": trading_days,
                "closed_trades": total_trades,
                "win_rate": f"{win_rate:.2f}%",
            },
            "trading_objectives": {
                "daily_drawdown": {
                    "max_dd_limit": f"{daily_dd_limit:.2f}",
                    "today_dd_limit": f"{daily_dd_limit:.2f}",
                },
                "trading_days": {
                    "minimum": 6,
                    "current": trading_days,
                    "status": "Passed" if trading_days >= 5 else "Not Passed",
                },
                "profit_target": {
                    "minimum": portfolio.profit_target,
                    "current": f"{profit_loss:.2f}",
                    "status": (
                        "Passed"
                        if profit_loss >= portfolio.profit_target
                        else "Not Passed"
                    ),
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
            "total_open_pl": float(total_open_pl),
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


class AdminReceiptsView(APIView):
    serializer_class = AdminReceiptsViewSerializer

    def get(self, request):
        email = request.GET.get("email")
        filter = request.GET.get("filter")
        receipts_data = []

        # Get all receipts IDs from PropReceipt to filter against
        prop_receipt_ids = PropReceipt.objects.values_list("receipt_id", flat=True)

        if filter == "bank_transfer":
            # Only include receipts in PropReceipt
            for receipt in Receipts.objects.filter(
                user__email=email, id__in=prop_receipt_ids
            ).order_by("-created"):
                receipt_dict = {
                    "id": receipt.id,
                    "amount": receipt.amount,
                    "created": receipt.created,
                    "receipt_status": receipt.receipt_status,
                    "payment_method": receipt.payment_method,
                    "fullname": receipt.user.fullname,
                    "comment": receipt.comment,
                    "approved_date": receipt.approved_date,
                    "image_url": receipt.image.url,
                    "user": receipt.user.id,
                    "flag": receipt.flag,
                    "timestamp": receipt.created.timestamp(),
                }
                receipts_data.append(receipt_dict)
        elif filter == "paystack":
            # Only include PayStack receipts in PropReceipt
            # paystack_receipt_ids = PropReceipt.objects.filter(
            #     receipt__in=PayStackReceipts.objects.all()
            # ).values_list("receipt_id", flat=True)
            paystack_receipt_ids = []

            for paystack_receipt in PayStackReceipts.objects.filter(
                user__email=email, id__in=paystack_receipt_ids
            ).order_by("-date"):
                paystack_receipt_dict = {
                    "id": paystack_receipt.id,
                    "amount": paystack_receipt.amount,
                    "created": paystack_receipt.date,
                    "receipt_status": paystack_receipt.receipt_status,
                    "payment_method": "paystack",
                    "user": paystack_receipt.user.id,
                    "image_url": "",
                    "approved_date": "",
                    "comment": paystack_receipt.comment,
                    "fullname": paystack_receipt.user.fullname,
                    "flag": paystack_receipt.flag,
                    "timestamp": paystack_receipt.date.timestamp(),
                }
                receipts_data.append(paystack_receipt_dict)
        else:
            # For no specific filter, include both Receipts and PayStackReceipts in PropReceipt
            for receipt in Receipts.objects.filter(id__in=prop_receipt_ids).order_by(
                "-created"
            ):
                receipt_dict = {
                    "id": receipt.id,
                    "amount": receipt.amount,
                    "created": receipt.created,
                    "receipt_status": receipt.receipt_status,
                    "payment_method": receipt.payment_method,
                    "fullname": receipt.user.fullname,
                    "comment": receipt.comment,
                    "approved_date": receipt.approved_date,
                    "image_url": receipt.image.url,
                    "user": receipt.user.id,
                    "flag": receipt.flag,
                    "timestamp": receipt.created.timestamp(),
                }
                receipts_data.append(receipt_dict)

            # for paystack_receipt in PayStackReceipts.objects.filter(
            #     id__in=paystack_receipt_ids
            # ).order_by("-date"):
            #     paystack_receipt_dict = {
            #         "id": paystack_receipt.id,
            #         "amount": paystack_receipt.amount,
            #         "created": paystack_receipt.date,
            #         "receipt_status": paystack_receipt.receipt_status,
            #         "payment_method": "paystack",
            #         "user": paystack_receipt.user.id,
            #         "image_url": "",
            #         "approved_date": "",
            #         "comment": paystack_receipt.comment,
            #         "fullname": paystack_receipt.user.fullname,
            #         "flag": paystack_receipt.flag,
            #         "timestamp": paystack_receipt.date.timestamp(),
            #     }
            #     receipts_data.append(paystack_receipt_dict)

        receipts_data2 = sorted(
            receipts_data, key=lambda x: x["timestamp"], reverse=True
        )
        return Response(receipts_data2)

    def post(self, request):

        statuses = ["approved", "rejected"]

        id = request.data["id"]
        amount = request.data["amount"]
        receipt_status = request.data["receipt_status"]
        comment = request.data["comment"]

        if receipt_status not in statuses:
            return Response("receipt_status must either be approved or rejected ")

        receipt = Receipts.objects.get(id=id)
        receipt.receipt_status = receipt_status
        receipt.save()

        if receipt_status == "approved":

            receipt.amount = amount
            receipt.save()
            AdminUserActivityLog.objects.create(
                admin=request.user,
                user=receipt.user,
                action_type="approved_reciept",
                description=f"Admin user approved reciept.",
            )
            prop_receipt = PropReceipt.objects.filter(receipt=receipt).first()

            prop_account = prop_receipt.account
            prop_account.receipt_approved = True
            prop_account.save()

            try:
                # Check if this user was referred by someone
                referral = Referral.objects.get(person_referred=receipt.user)

                # Check if rewards have already been given for this user
                existing_reward = RewardActivities.objects.filter(
                    trader=receipt.user, reward_type="prop_referral"
                ).exists()

                if not existing_reward:
                    # Credit referrer
                    referrer_wallet, _ = ReferralWallet.objects.get_or_create(
                        user=referral.user
                    )
                    referrer_wallet.balance += Decimal("18000")
                    referrer_wallet.save()

                    # Create reward activity for referrer
                    RewardActivities.objects.create(
                        user=referral.user,
                        trader=receipt.user,
                        reward_type="prop_referral",
                        amount=18000,
                        status="processed",
                        comment="Referral reward for prop account purchase",
                    )

                    # Credit referee (the user who was referred)
                    referee_wallet, _ = ReferralWallet.objects.get_or_create(
                        user=receipt.user
                    )
                    referee_wallet.balance += Decimal("18000")
                    referee_wallet.save()

                    # Create reward activity for referee
                    RewardActivities.objects.create(
                        user=receipt.user,
                        trader=receipt.user,
                        reward_type="referral_reward",
                        amount=18000,
                        status="processed",
                        comment="Referral reward for prop account purchase",
                    )

                    # Update referral status
                    # referral.converted = True
                    # referral.save()

            except Referral.DoesNotExist:
                # No referral relationship exists
                pass

            receipt_data = {
                "id": receipt.id,
                "user": receipt.user.id,
                "fullname": receipt.user.fullname,
                "amount": receipt.amount,
                "payment_method": receipt.payment_method,
                "receipt_status": receipt.receipt_status,
                "comment": receipt.comment,
                "created": receipt.created,
                "approved_date": receipt.approved_date,
                "image_url": receipt.image.url if receipt.image else None,
            }
            return Response(receipt_data)

        elif receipt_status == "rejected":
            receipt.comment = comment
            receipt.save()

            AdminUserActivityLog.objects.create(
                admin=request.user,
                user=receipt.user,
                action_type="rejected_reciept",
                description=f"Admin user rejected reciept.",
            )
            receipt_data = {
                "id": receipt.id,
                "user": receipt.user.id,
                "fullname": receipt.user.fullname,
                "amount": receipt.amount,
                "payment_method": receipt.payment_method,
                "receipt_status": receipt.receipt_status,
                "comment": receipt.comment,
                "created": receipt.created,
                "approved_date": receipt.approved_date,
                "image_url": receipt.image.url if receipt.image else None,
            }
            save_and_send_notification(
                receipt.user.id,
                f"Your payment receipt has been rejected. Reason: {receipt.comment}.",
            )

            return Response(receipt_data)


class AdminAccountsList(APIView):

    def get(self, request):
        accounts = DemoPortfolio.objects.filter(is_prop=True)
        serializer = AccountlistSerializer(accounts, many=True)
        return Response(serializer.data)


class UserAccounctsList(APIView):

    def get(self, request):
        accounts = DemoPortfolio.objects.filter(
            user=request.user, is_prop=True, receipt_approved=True
        )
        serializer = AccountlistSerializer(accounts, many=True)
        return Response(serializer.data)


# class PortfolioDailyProfitLossView(APIView):
#     def get(self, request, portfolio_id):
#         try:
#             # Get the number of days from query params, default to 7
#             days = int(request.query_params.get("days", 7))

#             # Calculate the start date
#             end_date = timezone.now()
#             start_date = end_date - timedelta(days=days)

#             # Get the portfolio
#             portfolio = DemoPortfolio.objects.get(id=portfolio_id)

#             # Query closed positions and group them by date
#             daily_data = (
#                 DemoPosition.objects.filter(
#                     portfolio=portfolio,
#                     status="close",
#                     updated__gte=start_date,
#                     updated__lte=end_date,
#                 )
#                 .annotate(date=TruncDate("updated"))
#                 .values("date")
#                 .annotate(
#                     profit_sum=Sum("profit_loss", filter=Q(profit_loss__gt=0)),
#                     loss_sum=Sum("profit_loss", filter=Q(profit_loss__lt=0)),
#                 )
#                 .order_by("date")
#             )

#             # Calculate total profit and loss
#             total_profit = sum(d["profit_sum"] or 0 for d in daily_data)
#             total_loss = sum(d["loss_sum"] or 0 for d in daily_data)

#             # Format the response
#             daily_results = [
#                 {
#                     "date": entry["date"].strftime("%Y-%m-%d"),
#                     "profit": float(entry["profit_sum"] or 0),
#                     "loss": float(entry["loss_sum"] or 0),
#                 }
#                 for entry in daily_data
#             ]

#             response_data = {
#                 "summary": {
#                     "total_profit": float(total_profit),
#                     "total_loss": float(total_loss),
#                     "net_profit": float(total_profit + total_loss),
#                     "percentage_change": calculate_percentage_change(
#                         total_profit, total_loss
#                     ),
#                 },
#                 "daily_data": daily_results,
#                 "last_updated": timezone.now().strftime("%Y-%m-%d %H:%M"),
#             }

#             return Response(response_data)

#         except DemoPortfolio.DoesNotExist:
#             return Response({"error": "Portfolio not found"}, status=404)
#         except Exception as e:
#             return Response({"error": str(e)}, status=400)


class PortfolioDailyProfitLossView(APIView):
    def get(self, request, portfolio_id):
        try:
            days = int(request.query_params.get("days", 7))
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            portfolio = DemoPortfolio.objects.get(id=portfolio_id)

            # Get all closed positions for the period
            positions = DemoPosition.objects.filter(
                portfolio=portfolio,
                status="close",
                updated__gte=start_date,
                updated__lte=end_date,
            ).annotate(
                date=TruncDate("updated"),
                commission=ExpressionWrapper(
                    (F("amount_invested") * Decimal("0.00435")) + Decimal("200"),
                    output_field=DecimalField(),
                ),
            )

            # Group by date and calculate daily totals including commission
            daily_data = (
                positions.values("date")
                .annotate(
                    profit_sum=Sum(
                        Case(
                            When(
                                profit_loss__gt=0,
                                then=F("profit_loss") - F("commission"),
                            ),
                            default=Value(0),
                            output_field=DecimalField(),
                        )
                    ),
                    loss_sum=Sum(
                        Case(
                            When(
                                profit_loss__lt=0,
                                then=F("profit_loss") - F("commission"),
                            ),
                            default=Value(0),
                            output_field=DecimalField(),
                        )
                    ),
                    total_commission=Sum("commission"),
                )
                .order_by("date")
            )

            # Calculate totals
            total_profit = Decimal("0")
            total_loss = Decimal("0")
            total_commission = Decimal("0")

            daily_results = []
            for entry in daily_data:
                profit = Decimal(str(entry["profit_sum"] or 0))
                loss = Decimal(str(entry["loss_sum"] or 0))
                commission = Decimal(str(entry["total_commission"] or 0))

                total_profit += profit
                total_loss += loss
                total_commission += commission

                daily_results.append(
                    {
                        "date": entry["date"].strftime("%Y-%m-%d"),
                        "profit": float(profit),
                        "loss": float(loss),
                        "commission": float(commission),
                        "net": float(profit + loss),  # Net profit/loss after commission
                    }
                )

            net_profit = total_profit + total_loss
            wat = pytz.timezone("Africa/Lagos")
            response_data = {
                "summary": {
                    "total_profit": float(total_profit),
                    "total_loss": float(total_loss),
                    "total_commission": float(total_commission),
                    "net_profit": float(net_profit),
                    "percentage_change": self.calculate_percentage_change(
                        portfolio, start_date, end_date
                    ),
                },
                "daily_data": daily_results,
                "last_updated": timezone.now()
                .astimezone(wat)
                .strftime("%Y-%m-%d %H:%M"),
            }

            return Response(response_data)

        except DemoPortfolio.DoesNotExist:
            return Response({"error": "Portfolio not found"}, status=404)
        except Exception as e:
            logger.error(f"Error in PortfolioDailyProfitLossView: {str(e)}")
            return Response({"error": str(e)}, status=400)

    def calculate_percentage_change(self, portfolio, start_date, end_date):
        """
        Calculate percentage change over the period
        Returns positive percentage for profit and negative for loss
        """
        try:
            # Get positions at the start and end of the period
            start_positions = DemoPosition.objects.filter(
                portfolio=portfolio, updated__lt=start_date, status="close"
            ).aggregate(
                total_profit_loss=Sum("profit_loss"),
                total_commission=Sum(
                    ExpressionWrapper(
                        (F("amount_invested") * Decimal("0.00435")) + Decimal("200"),
                        output_field=DecimalField(),
                    )
                ),
            )

            end_positions = DemoPosition.objects.filter(
                portfolio=portfolio, updated__lte=end_date, status="close"
            ).aggregate(
                total_profit_loss=Sum("profit_loss"),
                total_commission=Sum(
                    ExpressionWrapper(
                        (F("amount_invested") * Decimal("0.00435")) + Decimal("200"),
                        output_field=DecimalField(),
                    )
                ),
            )

            # Calculate net values including commission
            start_net = Decimal(
                str(start_positions["total_profit_loss"] or 0)
            ) - Decimal(str(start_positions["total_commission"] or 0))

            end_net = Decimal(str(end_positions["total_profit_loss"] or 0)) - Decimal(
                str(end_positions["total_commission"] or 0)
            )

            # Calculate the difference in profit/loss
            profit_difference = end_net - start_net

            # Get the reference value (initial balance or start period balance)
            reference_balance = portfolio.initial_balance + start_net

            if reference_balance == 0:
                return 0

            # Calculate percentage change
            percentage_change = (profit_difference / reference_balance) * 100
            return round(float(percentage_change), 2)

        except Exception as e:
            logger.error(f"Error calculating percentage change: {e}")
            return 0


def calculate_percentage_change(profit, loss):
    total = profit + abs(loss) if loss else profit
    if total == 0:
        return 0
    return round((profit / total) * 100 if total > 0 else 0, 2)


class MyReferralWalletManagement(viewsets.ModelViewSet):
    serializer_class = ReferralWalletSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def wallet_balance(self, request, *args, **kwargs):
        """
        Get the user's referral wallet balance.
        """
        user = request.user
        wallet, _ = ReferralWallet.objects.get_or_create(user=request.user)
        serializer = self.serializer_class(wallet, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def reward_activities(self, request, *args, **kwargs):
        """
        Get the referral activities for the user.
        """
        user = request.user
        activities = RewardActivities.objects.filter(
            user=user, reward_type="prop_referral"
        ).order_by("-created")
        serializer = RewardActivitiesSerializer(activities, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def request_referral_reward_payout(self, request, *args, **kwargs):
        """
        Request a referral reward payout.
        """

        wallet, _ = ReferralWallet.objects.get_or_create(user=request.user)
        serializer = ReferralRewardPayoutSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data.get("amount")
            if amount > wallet.balance:
                return Response(
                    {"error": "Insufficient balance in referral wallet"}, status=400
                )
            ReferralWithdrawalRequest.objects.create(wallet=wallet, amount=amount)
            save_and_send_notification(
                request.user.id,
                "Your referral commission withdrawal has been submitted.",
            )
            wallet.balance -= amount
            wallet.save()

            return Response({"message": "Referral reward payout request successful"})
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=["post"])
    def my_referral_payout_request_lists(self, request, *args, **kwargs):
        """
        Get the user's referral payout request lists.
        """
        user = request.user
        requests = ReferralWithdrawalRequest.objects.filter(wallet__user=user).order_by(
            "-created"
        )
        serializer = ReferralWithdrawalRequestSerializer(requests, many=True)
        return Response(serializer.data)


class UserReceiptsView(APIView):
    def get(self, request):
        receipts_data = []

        prop_receipt_ids = PropReceipt.objects.values_list("receipt_id", flat=True)

        for receipt in Receipts.objects.filter(
            user=request.user, id__in=prop_receipt_ids
        ).order_by("-created"):
            receipt_dict = {
                "amount": receipt.amount,
                "upload_date": receipt.created,
                "receipt_status": receipt.receipt_status,
                "payment_method": receipt.payment_method,
                "comment": receipt.comment,
                "approved_date": receipt.approved_date,
                "image_url": receipt.image.url,
            }

            receipts_data.append(receipt_dict)
        return Response(receipts_data)


class PayoutsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, portfolio_id):
        user = request.user

        try:
            portfolio = DemoPortfolio.objects.get(id=portfolio_id, user=user)
            payouts = Payout.objects.filter(portfolio=portfolio)

            # Calculate Available Profit
            available_profit = self.calculate_available_profit(portfolio)

            # Calculate Pending Amount
            pending_amount = payouts.filter(status="pending").aggregate(
                total=Sum("amount")
            )["total"] or Decimal("0")

            # Calculate Total Paid
            total_paid = payouts.filter(status="paid").aggregate(total=Sum("amount"))[
                "total"
            ] or Decimal("0")

            response_data = {
                "available_profit": {
                    "amount": float(available_profit),
                    "can_request": available_profit > 0,
                },
                "pending_amount": {
                    "amount": float(pending_amount),
                },
                "total_paid": {
                    "amount": float(total_paid),
                },
                "last_updated": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            return Response(response_data)

        except DemoPortfolio.DoesNotExist:
            return Response(
                {"error": "Portfolio not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def calculate_available_profit(self, portfolio):
        """
        Calculate available profit for withdrawal based on profit since last paid payout
        """
        try:
            # Get current balance from portfolio
            current_balance = Decimal(str(portfolio.balance))

            # Get the last paid payout
            last_payout = (
                Payout.objects.filter(portfolio=portfolio, status="paid")
                .order_by("-process_date")
                .first()
            )

            # Get account data from MongoDB
            account_data = get_account_data(portfolio.account_id)

            if not account_data:
                return Decimal("0")

            if last_payout and last_payout.process_date:
                # Convert process_date to the same format as MongoDB timestamp
                process_date = last_payout.process_date.strftime("%Y-%m-%dT%H:%M")

                # Find the first balance entry after the last payout
                balance_after_payout = None
                for entry in account_data:
                    if entry["timestamp"] > process_date:
                        balance_after_payout = Decimal(str(entry["balance"]))
                        break

                if balance_after_payout is None:
                    logger.warning(
                        f"No balance data found after last payout for portfolio {portfolio.id}"
                    )
                    return Decimal("0")

                # Calculate profit since last payout
                profit = current_balance - balance_after_payout
                logger.info(
                    f"Portfolio {portfolio.id} profit calculation: "
                    f"current_balance({current_balance}) - "
                    f"balance_after_payout({balance_after_payout}) = {profit}"
                )
            else:
                # No previous payout, calculate from initial balance
                initial_balance = Decimal(str(portfolio.initial_balance))
                profit = current_balance - initial_balance
                logger.info(
                    f"Portfolio {portfolio.id} initial profit calculation: "
                    f"current_balance({current_balance}) - "
                    f"initial_balance({initial_balance}) = {profit}"
                )

            if profit > 0:
                # Get pending payouts
                pending_payouts = Payout.objects.filter(
                    portfolio=portfolio, status="pending"
                ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

                # Subtract pending payouts from available profit
                available = profit - pending_payouts
                return max(Decimal("0"), available)

            return Decimal("0")

        except Exception as e:
            logger.error(
                f"Error calculating available profit for portfolio {portfolio.id}: {e}"
            )
            return Decimal("0")

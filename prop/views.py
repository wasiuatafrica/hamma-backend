import logging
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import portfolio
from accounts.models import AdminUserActivityLog, Referral
from accounts.serializers import AdminCustomUserSerializer
from affilate.models import ReferralWallet, ReferralWithdrawalRequest, RewardActivities
from affilate.serializers import (
    ReferralRewardPayoutSerializer,
    ReferralWalletSerializer,
    ReferralWithdrawalRequestSerializer,
    RewardActivitiesSerializer,
)
from anyon.serializers import AdminReceiptsViewSerializer
from execution.models import (
    DemoPortfolio,
    DemoPosition,
    PropReceipt,
    HammaAccountRequest,
)
from notifications.utils import save_and_send_notification
from portfolio.models import PayStackReceipts, Receipts

from .models import Payout
from .pay_service import PayoutService
from .serializers import AccountlistSerializer, PayoutDetailSerializer
from .utils import (
    calculate_trading_days,
    get_account_data,
    get_equity_balance,
    initiate_first_data,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def calculate_daily_drawdown(data, model_type):
    """
    Calculate the maximum drawdown achieved and allowed for today's data.

    Args:
        data (list): A list of dictionaries with keys 'balance', 'equity', 'timestamp', and 'account_id'.
        model_type (str): The model type ('model_1' or other).

    Returns:
        tuple: Maximum drawdown allowed and maximum drawdown achieved.
    """

    # Get today's date in 'YYYY-MM-DD' format
    today = datetime.now().strftime("%Y-%m-%d")

    # Filter the data for today, or use the most recent date in the data
    today_data = [record for record in data if record["timestamp"].startswith(today)]
    if not today_data:
        # Find the most recent date and filter data for that day
        most_recent_date = max(record["timestamp"].split("T")[0] for record in data)
        today_data = [
            record
            for record in data
            if record["timestamp"].startswith(most_recent_date)
        ]

    if not today_data:
        return 0, 0  # No data available

    # Extract the list of balance values for today's data
    balances = [record["balance"] for record in today_data]
    if not balances:
        return 0, 0  # No balance data available

    # Get the initial balance (day starting balance)
    initial_balance = balances[0]

    # Calculate the maximum drawdown achieved
    drawdowns = [
        initial_balance - balance for balance in balances if balance < initial_balance
    ]
    max_drawdown_achieved = max(drawdowns, default=0)

    # Calculate the maximum drawdown allowed based on the model type
    max_drawdown_allowed = (
        0.05 * initial_balance if model_type == "model_1" else 0.03 * initial_balance
    )

    return max_drawdown_allowed, max_drawdown_achieved


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


class AdminPayoutListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get list of payouts"""
        payouts = Payout.objects.all().order_by("-request_date")

        serializer = PayoutDetailSerializer(payouts, many=True)
        return Response(serializer.data)


class PayoutDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            payout = Payout.objects.get(pk=pk)

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
        # if not request.user.is_staff:
        #     return Response(
        #         {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
        #     )

        payout = self.get_object(pk)
        if not payout:
            return Response(
                {"error": "Payout not found"}, status=status.HTTP_404_NOT_FOUND
            )

        action = request.data.get("action")

        if action not in ["declined", "paid"]:
            return Response(
                {"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if action == "paid":
                payout.status = "paid"
                payout.process_date = timezone.now()
                payout.processed_by = request.user

            else:
                reason = request.data.get("reason")
                if not reason:
                    return Response(
                        {"error": "Reason is required for rejection"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                payout.status = "declined"
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
        # two_weeks_ago = current_time - timedelta(days=14)
        positions = DemoPosition.objects.filter(
            portfolio=portfolio  # , created__gte=two_weeks_ago
        )

        # Calculate trades count and win rate
        closed_positions = positions.filter(status="close")
        total_trades = closed_positions.count()
        winning_trades = closed_positions.filter(profit_loss__gt=0).count()
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Calculate drawdown
        if not portfolio.balance_based_drawdown:
            if historical_data:
                # Get the least equity below the threshold, or use a default value if no data is found
                least_equity_candidates = [
                    data["equity"]
                    for data in historical_data
                    if data["equity"] < 10000000
                ]
                least_equity = (
                    min(least_equity_candidates)
                    if least_equity_candidates
                    else float(initial_balance)
                )

                # Get the least balance below the threshold, or use a default value if no data is found
                least_balance_candidates = [
                    data["balance"]
                    for data in historical_data
                    if data["balance"] < 10000000
                ]
                least_balance = (
                    min(least_balance_candidates)
                    if least_balance_candidates
                    else float(initial_balance)
                )

                # Calculate the current drawdown
                current_drawdown = float(initial_balance) - min(
                    least_equity, least_balance
                )
            else:
                # No historical data, set drawdown to 0
                current_drawdown = 0
        elif portfolio.balance_based_drawdown:
            if historical_data:
                # Get the least balance below the threshold, or use a default value if no data is found
                least_balance_candidates = [
                    data["balance"]
                    for data in historical_data
                    if data["balance"] < 10000000
                ]
                least_balance = (
                    min(least_balance_candidates)
                    if least_balance_candidates
                    else float(initial_balance)
                )

                # Calculate the current drawdown
                current_drawdown = float(initial_balance) - least_balance
            else:
                # No historical data, set drawdown to 0
                current_drawdown = 0

        trading_days = calculate_trading_days(historical_data)

        # Get daily drawdown limit
        dd_allowed, dd_achieved = calculate_daily_drawdown(
            historical_data, portfolio.model_type
        )

        response_data = {
            "metrics": {
                "balance": f"{current_balance:.2f}",
                "equity": f"{current_equity:.2f}",
                "floating_profit_loss": f"{profit_loss:.2f}",
                "account_drawdown": 10000000 - portfolio.account_drawdown_limit,
                "current_account_drawdown": f"{current_drawdown:.2f}",
                "trading_days": trading_days,
                "closed_trades": total_trades,
                "win_rate": f"{win_rate:.2f}%",
            },
            "trading_objectives": {
                "daily_drawdown": {
                    "max_dd_limit": f"{dd_allowed:.2f}",
                    "today_dd_limit": f"{dd_achieved:.2f}",
                },
                "trading_days": {
                    "minimum": 6,
                    "current": trading_days,
                    "status": "Passed" if trading_days > 5 else "Not Passed",
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

        response_data["balanced_based"] = portfolio.balance_based_drawdown

        return Response(response_data)


# class AccountDataView(APIView):
#     permission_classes = [AllowAny]

#     def get(self, request, account_id):
#         try:
#             account_data = get_account_data(account_id)
#             return Response(account_data, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response(
#                 {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

from datetime import timedelta

from django.utils import timezone


class AccountDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, account_id):
        try:
            # Define time periods
            time_periods = {
                "7d": 7,  # Last 7 days
                "2w": 14,  # Last 2 weeks
                "1m": 30,  # Last 1 month
                "3m": 90,  # Last 3 months
                "6m": 180,  # Last 6 months
                "1y": 365,  # Last 1 year
            }

            # Get period from query params, default to 7 days
            period = request.query_params.get("period", "7d")

            # Validate period
            days = time_periods.get(period)
            if days is None:
                return Response(
                    {
                        "error": "Invalid period. Valid periods are: 7d, 2w, 1m, 3m, 6m, 1y"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            # Get account data
            account_data = get_account_data(account_id)

            # Filter data based on timestamp
            filtered_data = [
                data
                for data in account_data
                if timezone.datetime.strptime(
                    data["timestamp"], "%Y-%m-%dT%H:%M"
                ).replace(tzinfo=timezone.utc)
                >= start_date
            ]

            return Response(filtered_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class AdminReceiptsView(APIView):
#     serializer_class = AdminReceiptsViewSerializer

#     def get(self, request):
#         email = request.GET.get("email")
#         filter = request.GET.get("filter")
#         receipts_data = []

#         # Get all receipts IDs from PropReceipt to filter against
#         prop_receipt_ids = PropReceipt.objects.values_list("receipt_id", flat=True)

#         if filter == "bank_transfer":
#             # Only include receipts in PropReceipt
#             for receipt in Receipts.objects.filter(
#                 user__email=email, id__in=pr
#             ).order_by("-created"):
#                 receipt_dict = {
#                     "id": receipt.id,
#                     "amount": receipt.amount,
#                     "created": receipt.created,
#                     "receipt_status": receipt.receipt_status,
#                     "payment_method": receipt.payment_method,
#                     "fullname": receipt.user.fullname,
#                     "comment": receipt.comment,
#                     "approved_date": receipt.approved_date,
#                     "image_url": receipt.image.url if receipt.image else "",
#                     "user": receipt.user.id,
#                     "flag": receipt.flag,
#                     "timestamp": receipt.created.timestamp(),
#                     discount_code =
#                 }
#                 receipts_data.append(receipt_dict)
#         elif filter == "paystack":
#             # Only include PayStack receipts in PropReceipt
#             # paystack_receipt_ids = PropReceipt.objects.filter(
#             #     receipt__in=PayStackReceipts.objects.all()
#             # ).values_list("receipt_id", flat=True)
#             paystack_receipt_ids = []

#             for paystack_receipt in PayStackReceipts.objects.filter(
#                 user__email=email, id__in=paystack_receipt_ids
#             ).order_by("-date"):
#                 paystack_receipt_dict = {
#                     "id": paystack_receipt.id,
#                     "amount": paystack_receipt.amount,
#                     "created": paystack_receipt.date,
#                     "receipt_status": paystack_receipt.receipt_status,
#                     "payment_method": "paystack",
#                     "user": paystack_receipt.user.id,
#                     "image_url": "",
#                     "approved_date": "",
#                     "comment": paystack_receipt.comment,
#                     "fullname": paystack_receipt.user.fullname,
#                     "flag": paystack_receipt.flag,
#                     "timestamp": paystack_receipt.date.timestamp(),
#                 }
#                 receipts_data.append(paystack_receipt_dict)
#         else:
#             # For no specific filter, include both Receipts and PayStackReceipts in PropReceipt
#             for receipt in Receipts.objects.filter(id__in=prop_receipt_ids).order_by(
#                 "-created"
#             ):
#                 receipt_dict = {
#                     "id": receipt.id,
#                     "amount": receipt.amount,
#                     "created": receipt.created,
#                     "receipt_status": receipt.receipt_status,
#                     "payment_method": receipt.payment_method,
#                     "fullname": receipt.user.fullname,
#                     "comment": receipt.comment,
#                     "approved_date": receipt.approved_date,
#                     "image_url": receipt.image.url if receipt.image else "",
#                     "user": receipt.user.id,
#                     "flag": receipt.flag,
#                     "timestamp": receipt.created.timestamp(),
#                 }
#                 receipts_data.append(receipt_dict)

#             # for paystack_receipt in PayStackReceipts.objects.filter(
#             #     id__in=paystack_receipt_ids
#             # ).order_by("-date"):
#             #     paystack_receipt_dict = {
#             #         "id": paystack_receipt.id,
#             #         "amount": paystack_receipt.amount,
#             #         "created": paystack_receipt.date,
#             #         "receipt_status": paystack_receipt.receipt_status,
#             #         "payment_method": "paystack",
#             #         "user": paystack_receipt.user.id,
#             #         "image_url": "",
#             #         "approved_date": "",
#             #         "comment": paystack_receipt.comment,
#             #         "fullname": paystack_receipt.user.fullname,
#             #         "flag": paystack_receipt.flag,
#             #         "timestamp": paystack_receipt.date.timestamp(),
#             #     }
#             #     receipts_data.append(paystack_receipt_dict)

#         receipts_data2 = sorted(
#             receipts_data, key=lambda x: x["timestamp"], reverse=True
#         )
#         return Response(receipts_data2)

#     def post(self, request):

#         statuses = ["approved", "rejected"]

#         # id = request.data["id"]
#         # amount = request.data["amount"]
#         receipt_status = request.data["receipt_status"]
#         comment = request.data.get("comment", None)

#         receipt_ids = request.data.get("receipt_ids", [])
#         print("recipt ids", receipt_ids)

#         if receipt_status not in statuses:
#             return Response("receipt_status must either be approved or rejected ")

#         receipt_data = []

#         for id in receipt_ids:

#             receipt = Receipts.objects.get(id=id)
#             receipt.receipt_status = receipt_status
#             receipt.save()

#             if receipt_status == "approved":

#                 receipt.amount = 180000
#                 receipt.save()
#                 AdminUserActivityLog.objects.create(
#                     admin=request.user,
#                     user=receipt.user,
#                     action_type="approved_reciept",
#                     description=f"Admin user approved reciept.",
#                 )
#                 prop_receipt = PropReceipt.objects.filter(receipt=receipt).first()

#                 prop_account = prop_receipt.account
#                 prop_account.receipt_approved = True
#                 # prop_account.activated = True
#                 prop_account.is_active = True
#                 prop_account.save()

#                 account_info = {
#                     "login": prop_account.account_id,
#                     "password": prop_account.code,
#                     "server": "HammaServer",
#                     "acc_size": (
#                         "Model 1" if prop_account.model_type == "model_1" else "Model 2"
#                     ),
#                     "payout": prop_account.payout.title(),
#                     "broker": prop_account.broker.title(),
#                     "first_name": receipt.user.firstname.title(),
#                 }

#                 # send the user the account details
#                 sendMail(
#                     "prop/AccountInfo.html",
#                     "Prop Account Details",
#                     [receipt.user.email],
#                     account_info,
#                 )

#                 try:
#                     # Check if this user was referred by someone
#                     referral = Referral.objects.get(person_referred=receipt.user)

#                     # Check if rewards have already been given for this user
#                     existing_reward = RewardActivities.objects.filter(
#                         trader=receipt.user, reward_type="prop_referral"
#                     ).exists()

#                     if not existing_reward:
#                         # Credit referrer
#                         referrer_wallet, _ = ReferralWallet.objects.get_or_create(
#                             user=referral.user
#                         )
#                         referrer_wallet.balance += Decimal("18000")
#                         referrer_wallet.save()

#                         # Create reward activity for referrer
#                         RewardActivities.objects.create(
#                             user=referral.user,
#                             trader=receipt.user,
#                             reward_type="prop_referral",
#                             amount=18000,
#                             status="processed",
#                             comment="Referral reward for prop account purchase",
#                         )

#                         # Credit referee (the user who was referred)
#                         referee_wallet, _ = ReferralWallet.objects.get_or_create(
#                             user=receipt.user
#                         )
#                         referee_wallet.balance += Decimal("18000")
#                         referee_wallet.save()

#                         # Create reward activity for referee
#                         RewardActivities.objects.create(
#                             user=receipt.user,
#                             trader=receipt.user,
#                             reward_type="referral_reward",
#                             amount=18000,
#                             status="processed",
#                             comment="Referral reward for prop account purchase",
#                         )

#                         # Update referral status
#                         # referral.converted = True
#                         # referral.save()

#                 except Referral.DoesNotExist:
#                     # No referral relationship exists
#                     pass

#                 data = {
#                     "id": receipt.id,
#                     "user": receipt.user.id,
#                     "fullname": receipt.user.fullname,
#                     "amount": receipt.amount,
#                     "payment_method": receipt.payment_method,
#                     "receipt_status": receipt.receipt_status,
#                     "comment": receipt.comment,
#                     "created": receipt.created,
#                     "approved_date": receipt.approved_date,
#                     "image_url": receipt.image.url if receipt.image else None,
#                 }
#                 receipt_data.append(data)

#             elif receipt_status == "rejected":
#                 receipt.comment = comment
#                 receipt.save()

#                 AdminUserActivityLog.objects.create(
#                     admin=request.user,
#                     user=receipt.user,
#                     action_type="rejected_reciept",
#                     description=f"Admin user rejected reciept.",
#                 )
#                 data = {
#                     "id": receipt.id,
#                     "user": receipt.user.id,
#                     "fullname": receipt.user.fullname,
#                     "amount": receipt.amount,
#                     "payment_method": receipt.payment_method,
#                     "receipt_status": receipt.receipt_status,
#                     "comment": receipt.comment,
#                     "created": receipt.created,
#                     "approved_date": receipt.approved_date,
#                     "image_url": receipt.image.url if receipt.image else None,
#                 }
#                 save_and_send_notification(
#                     receipt.user.id,
#                     f"Your payment receipt has been rejected. Reason: {receipt.comment}.",
#                 )
#                 receipt_data.append(data)

#         return Response(receipt_data)


def sendMail(
    template: str,
    subject: str,
    to: list,
    context: object = None,
    sender: str = None,
    **kwargs,
) -> bool:
    """
    A wrapper for send_mail
    Compile a template to html and string and send email

    Arguments:
        template {str} -- The template location
        subject {str} -- Mail Subject
        to {object} -- Mail recipients, can be string or list

    Keyword Arguments:
        context {object} -- The data to pass to the template (default: {None})
        sender {str} -- Opeional Sender (default: {None})

    Returns:
        bool -- send_mail 1 = sent and 0 not sent
    """
    html = render_to_string(template, context)
    try:
        send_mail(
            subject,
            "",
            "Hamma Trade <hello@hamma.trade>",
            to,
            html_message=html,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(str(e))
        return False


class AdminReceiptsView(APIView):
    serializer_class = AdminReceiptsViewSerializer

    def get(self, request):
        email = request.GET.get("email")
        filter = request.GET.get("filter")
        receipts_data = []

        # Fetch all PropReceipts with their related data once
        prop_receipts = PropReceipt.objects.select_related(
            "receipt", "receipt__user", "discount_code"
        ).all()

        # Create a dictionary for quick lookup
        prop_receipt_map = {pr.receipt_id: pr for pr in prop_receipts if pr.receipt_id}

        if filter == "bank_transfer":
            # Only include receipts in PropReceipt
            for receipt in (
                Receipts.objects.select_related("user")
                .filter(user__email=email, id__in=prop_receipt_map.keys())
                .order_by("-created")
            ):
                prop_receipt = prop_receipt_map.get(receipt.id)
                receipt_dict = {
                    "id": receipt.id,
                    "amount": receipt.amount,
                    "created": receipt.created,
                    "receipt_status": receipt.receipt_status,
                    "payment_method": receipt.payment_method,
                    "fullname": receipt.user.fullname,
                    "comment": receipt.comment,
                    "approved_date": receipt.approved_date,
                    "image_url": receipt.image.url if receipt.image else "",
                    "user": receipt.user.id,
                    "flag": receipt.flag,
                    "timestamp": receipt.created.timestamp(),
                    "discount_code": (
                        {
                            "code": (
                                prop_receipt.discount_code.code
                                if prop_receipt and prop_receipt.discount_code
                                else None
                            ),
                            "discount_percentage": (
                                prop_receipt.discount_code.discount_percentage
                                if prop_receipt and prop_receipt.discount_code
                                else None
                            ),
                        }
                        if prop_receipt and prop_receipt.discount_code
                        else None
                    ),
                }
                receipts_data.append(receipt_dict)

        elif filter == "paystack":
            # Only include PayStack receipts in PropReceipt
            paystack_receipt_ids = []

            for paystack_receipt in (
                PayStackReceipts.objects.select_related("user")
                .filter(user__email=email, id__in=paystack_receipt_ids)
                .order_by("-date")
            ):
                prop_receipt = prop_receipt_map.get(paystack_receipt.id)
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
                    "discount_code": (
                        {
                            "code": (
                                prop_receipt.discount_code.code
                                if prop_receipt and prop_receipt.discount_code
                                else None
                            ),
                            "discount_percentage": (
                                prop_receipt.discount_code.discount_percentage
                                if prop_receipt and prop_receipt.discount_code
                                else None
                            ),
                        }
                        if prop_receipt and prop_receipt.discount_code
                        else None
                    ),
                }
                receipts_data.append(paystack_receipt_dict)

        else:
            # For no specific filter, include both Receipts and PayStackReceipts in PropReceipt
            for receipt in (
                Receipts.objects.select_related("user")
                .filter(id__in=prop_receipt_map.keys())
                .order_by("-created")
            ):
                prop_receipt = prop_receipt_map.get(receipt.id)
                receipt_dict = {
                    "id": receipt.id,
                    "amount": receipt.amount,
                    "created": receipt.created,
                    "receipt_status": receipt.receipt_status,
                    "payment_method": receipt.payment_method,
                    "fullname": receipt.user.fullname,
                    "comment": receipt.comment,
                    "approved_date": receipt.approved_date,
                    "image_url": receipt.image.url if receipt.image else "",
                    "user": receipt.user.id,
                    "flag": receipt.flag,
                    "timestamp": receipt.created.timestamp(),
                    "discount_code": (
                        {
                            "code": (
                                prop_receipt.discount_code.code
                                if prop_receipt and prop_receipt.discount_code
                                else None
                            ),
                            "discount_percentage": (
                                prop_receipt.discount_code.discount_percentage
                                if prop_receipt and prop_receipt.discount_code
                                else None
                            ),
                        }
                        if prop_receipt and prop_receipt.discount_code
                        else None
                    ),
                }
                receipts_data.append(receipt_dict)

        receipts_data2 = sorted(
            receipts_data, key=lambda x: x["timestamp"], reverse=True
        )
        return Response(receipts_data2)

    def post(self, request):

        statuses = ["approved", "rejected"]

        # id = request.data["id"]
        # amount = request.data["amount"]
        receipt_status = request.data["receipt_status"]
        comment = request.data.get("comment", None)

        receipt_ids = request.data.get("receipt_ids", [])
        print("recipt ids", receipt_ids)

        if receipt_status not in statuses:
            return Response("receipt_status must either be approved or rejected ")

        receipt_data = []

        for id in receipt_ids:

            receipt = Receipts.objects.get(id=id)
            receipt.receipt_status = receipt_status
            receipt.save()

            if receipt_status == "approved":

                receipt.amount = 180000
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
                # prop_account.activated = True
                prop_account.is_active = True
                prop_account.save()

                account_info = {
                    "login": prop_account.account_id,
                    "password": prop_account.code,
                    "server": "HammaServer",
                    "acc_size": (
                        "Model 1" if prop_account.model_type == "model_1" else "Model 2"
                    ),
                    "payout": prop_account.payout.title(),
                    "broker": prop_account.broker.title(),
                    "first_name": receipt.user.firstname.title(),
                }

                # send the user the account details
                sendMail(
                    "prop/AccountInfo.html",
                    "Prop Account Details",
                    [receipt.user.email],
                    account_info,
                )

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

                data = {
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
                receipt_data.append(data)

            elif receipt_status == "rejected":
                receipt.comment = comment
                receipt.save()

                AdminUserActivityLog.objects.create(
                    admin=request.user,
                    user=receipt.user,
                    action_type="rejected_reciept",
                    description=f"Admin user rejected reciept.",
                )
                data = {
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
                receipt_data.append(data)

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
            period = request.query_params.get("period", "7d")  # Default to 7 days
            end_date = timezone.now()

            # Define time periods
            time_periods = {
                "7d": 7,  # Last 7 days
                "2w": 14,  # Last 2 weeks
                "1m": 30,  # Last 1 month
                "3m": 90,  # Last 3 months
                "6m": 180,  # Last 6 months
                "1y": 365,  # Last 1 year
            }

            # Get number of days based on period
            days = time_periods.get(period)
            if days is None:
                return Response(
                    {
                        "error": "Invalid period. Valid periods are: 7d, 2w, 1m, 3m, 6m, 1y"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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

    # class PortfolioDailyProfitLossView(APIView):
    #     def get(self, request, portfolio_id):
    #         try:
    #             # Get date range from query parameters
    #             start_date_str = request.query_params.get("start_date")
    #             end_date_str = request.query_params.get("end_date")
    #             print(start_date_str, end_date_str)

    #             # If no dates provided, default to last 7 days
    #             if not start_date_str or not end_date_str:
    #                 end_date = timezone.now()
    #                 start_date = end_date - timedelta(days=7)
    #             else:
    #                 try:
    #                     start_date = timezone.datetime.strptime(start_date_str, "%Y-%m-%d")
    #                     end_date = timezone.datetime.strptime(end_date_str, "%Y-%m-%d")
    #                     # Set end_date to end of day
    #                     end_date = end_date.replace(hour=23, minute=59, second=59)
    #                 except ValueError:
    #                     return Response(
    #                         {"error": "Invalid date format. Use YYYY-MM-DD"}, status=400
    #                     )

    #             portfolio = DemoPortfolio.objects.get(id=portfolio_id)

    #             # Get all closed positions for the period
    #             positions = DemoPosition.objects.filter(
    #                 portfolio=portfolio,
    #                 status="close",
    #                 updated__gte=start_date,
    #                 updated__lte=end_date,
    #             ).annotate(
    #                 date=TruncDate("updated"),
    #                 commission=ExpressionWrapper(
    #                     (F("amount_invested") * Decimal("0.00435")) + Decimal("200"),
    #                     output_field=DecimalField(),
    #                 ),
    #             )

    #             # Rest of the code remains the same...
    #             # Group by date and calculate daily totals including commission
    #             daily_data = (
    #                 positions.values("date")
    #                 .annotate(
    #                     profit_sum=Sum(
    #                         Case(
    #                             When(
    #                                 profit_loss__gt=0,
    #                                 then=F("profit_loss") - F("commission"),
    #                             ),
    #                             default=Value(0),
    #                             output_field=DecimalField(),
    #                         )
    #                     ),
    #                     loss_sum=Sum(
    #                         Case(
    #                             When(
    #                                 profit_loss__lt=0,
    #                                 then=F("profit_loss") - F("commission"),
    #                             ),
    #                             default=Value(0),
    #                             output_field=DecimalField(),
    #                         )
    #                     ),
    #                     total_commission=Sum("commission"),
    #                 )
    #                 .order_by("date")
    #             )

    #             # Calculate totals
    #             total_profit = Decimal("0")
    #             total_loss = Decimal("0")
    #             total_commission = Decimal("0")

    #             daily_results = []
    #             for entry in daily_data:
    #                 profit = Decimal(str(entry["profit_sum"] or 0))
    #                 loss = Decimal(str(entry["loss_sum"] or 0))
    #                 commission = Decimal(str(entry["total_commission"] or 0))

    #                 total_profit += profit
    #                 total_loss += loss
    #                 total_commission += commission

    #                 daily_results.append(
    #                     {
    #                         "date": entry["date"].strftime("%Y-%m-%d"),
    #                         "profit": float(profit),
    #                         "loss": float(loss),
    #                         "commission": float(commission),
    #                         "net": float(profit + loss),
    #                     }
    #                 )

    #             net_profit = total_profit + total_loss
    #             wat = pytz.timezone("Africa/Lagos")
    #             response_data = {
    #                 "summary": {
    #                     "total_profit": float(total_profit),
    #                     "total_loss": float(total_loss),
    #                     "total_commission": float(total_commission),
    #                     "net_profit": float(net_profit),
    #                     "percentage_change": self.calculate_percentage_change(
    #                         portfolio, start_date, end_date
    #                     ),
    #                 },
    #                 "daily_data": daily_results,
    #                 "last_updated": timezone.now()
    #                 .astimezone(wat)
    #                 .strftime("%Y-%m-%d %H:%M"),
    #                 "period": {
    #                     "start_date": start_date.strftime("%Y-%m-%d"),
    #                     "end_date": end_date.strftime("%Y-%m-%d"),
    #                 },
    #             }

    #             return Response(response_data)

    #         except DemoPortfolio.DoesNotExist:
    #             return Response({"error": "Portfolio not found"}, status=404)
    #         except Exception as e:
    #             logger.error(f"Error in PortfolioDailyProfitLossView: {str(e)}")
    #             return Response({"error": str(e)}, status=400)

    # calculate_percentage_change method remains the same
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

            if portfolio.account_level_type == "challenge":
                response_data = {
                    "available_profit": {"amount": 0, "can_request": False},
                    "pending_amount": {
                        "amount": 0,
                    },
                    "total_paid": {
                        "amount": 0,
                    },
                    "last_updated": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                return Response(response_data)

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
                    "can_request": pending_amount == 0,
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


class ActivateProp(APIView):
    def post(self, request):
        user = request.user
        account_id = request.data.get("account_id")
        account_name = request.data.get("account_name")
        try:
            prop = DemoPortfolio.objects.get(account_id=account_id, user=user)
            if prop.activated:
                return Response(
                    {"error": "Account already created"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:

                prop.activated = True
            prop.account_name = account_name
            prop.save()
            initiate_first_data(prop.account_id)
            return Response({"message": "Prop activated successfully"})
        except DemoPortfolio.DoesNotExist:
            return Response(
                {"error": "Account account cannot be created."},
                status=status.HTTP_404_NOT_FOUND,
            )


class ToggleDrawdownMethodView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, portfolio_id):
        try:
            portfolio = DemoPortfolio.objects.get(id=portfolio_id, user=request.user)

            # Check if portfolio is already using balance-based drawdown
            if portfolio.balance_based_drawdown:
                return Response(
                    {
                        "success": False,
                        "error": "Portfolio is already using balance-based drawdown.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if portfolio has any open positions
            # has_open_positions = portfolio.demopositions2.filter(status="open").exists()
            # if has_open_positions:
            #     return Response(
            #         {
            #             "success": False,
            #             "error": "Cannot switch drawdown method while there are open positions",
            #         },
            #         status=status.HTTP_400_BAD_REQUEST,
            #     )

            # Switch to balance-based drawdown
            portfolio.balance_based_drawdown = True
            portfolio.save()

            return Response(
                {
                    "success": True,
                    "message": "Successfully switched to balance-only drawdown calculation. Overnight swap fees of 500 naira per position will apply.",
                },
                status=status.HTTP_200_OK,
            )

        except DemoPortfolio.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Account not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"success": False, "error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserPendingReceipts(APIView):
    def get(self, request):
        prop_receipts = PropReceipt.objects.filter(
            receipt__user=request.user, receipt__status="pending"
        )
        if prop_receipts:
            pending = True
        else:
            pending = False
        return Response(pending)


class AdminUserList(APIView):
    serializer_class = AdminCustomUserSerializer

    def get_object(self, user_id):
        # Get a single user by ID
        return get_object_or_404(User, id=user_id)

    def get(self, request, user_id=None):

        # filter user by email
        email = request.GET.get("email")
        if email:
            users = User.objects.filter(
                email=email, demoportfolio2__is_prop=True
            ).distinct()
            serialized_data = self.serializer_class(users, many=True).data
            return Response(serialized_data)

        if user_id is not None:
            # Return details of a specific user
            user = self.get_object(user_id)
            serialized_data = self.serializer_class(user).data
            return Response(serialized_data)
        else:
            # Return a list of all users
            users = (
                User.objects.filter(demoportfolio2__is_prop=True)
                .annotate(latest_created=Max("demoportfolio2__created"))
                .order_by("-latest_created")
                .distinct()
            )

            serialized_data = self.serializer_class(users, many=True).data
            return Response(serialized_data)


class HammaAccountRequestView(APIView):
    def get(self, request, account_id):
        # try:
        account = DemoPortfolio.objects.get(
            account_id=account_id, account_type_level="challenge", user=request.user
        )
        target_met = account.target_met
        has_hamma = account.has_hamma
        pending_request = HammaAccountRequest.objects.filter(
            user=request.user, account=account, status="Unprocessed"
        ).exists()

        if target_met and has_hamma:
            return Response(
                {"can_request": False, "reason": "Account already has Hamma"}
            )
        if not target_met:
            return Response(
                {"can_request": False, "reason": "Account has not met target"}
            )
        if pending_request:
            return Response({"can_request": False, "reason": "Request already sent"})

        if target_met and not has_hamma and not pending_request:
            return Response(
                {"can_request": True, "reason": "Account can request Hamma"}
            )

    # except Exception as e:
    #     return Response(
    #         {"error": "Account not found"}, status=status.HTTP_400_BAD_REQUEST
    #     )

    def post(self, request, account_id):
        HammaAccountRequest.objects.create(user=request.user, account=account_id)
        return Response({"message": "Request sent successfully"})

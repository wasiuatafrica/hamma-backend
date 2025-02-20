from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import serialize

from accounts.models import AdminUserActivityLog, Referral
from affilate.models import (
    ReferralWallet,
    ReferralWalletTransaction,
    ReferralWithdrawalRequest,
    RewardActivities,
)
from affilate.serializers import (
    ReferralRewardPayoutSerializer,
    ReferralWalletSerializer,
    ReferralWithdrawalRequestSerializer,
    RewardActivitiesSerializer,
)
from competition.managers.utils import sendMail
from execution.models import DemoPortfolio, HammaAccountRequest
from notifications.utils import save_and_send_notification

from .pagination import CustomPageNumberPagination


class ReferralPayoutManagement(viewsets.ModelViewSet):
    serializer_class = ReferralWalletSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    @action(detail=False, methods=["post"])
    def referral_payout_request_lists(self, request, *args, **kwargs):
        """
        Get the authenticated user's referral payout request list with custom pagination.
        """
        requests = ReferralWithdrawalRequest.objects.all().order_by("-created")

        # Use the custom paginator
        paginator = CustomPageNumberPagination()
        paginated_requests = paginator.paginate_queryset(requests, request)

        # Serialize the paginated data
        serializer = ReferralWithdrawalRequestSerializer(paginated_requests, many=True)

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["put"])
    def update_request_status(self, request, pk=None):
        """
        Update the status of a specific withdrawal request.
        """
        try:
            payout_request = ReferralWithdrawalRequest.objects.get(pk=pk)
        except ReferralWithdrawalRequest.DoesNotExist:
            return Response(
                {"error": "Withdrawal request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ReferralWithdrawalRequestSerializer(
            payout_request, data=request.data, partial=True
        )

        if serializer.is_valid():
            status_value = serializer.validated_data.get("status")
            payout_request = serializer.save()
            user = payout_request.wallet.user

            if status_value == "approved":
                AdminUserActivityLog.objects.create(
                    admin=request.user,
                    user=user,
                    action_type="approved_withrawal",
                    description="Admin user approved prop referral withrawal.",
                )
                # send mail to the user
                sendMail(
                    "general/withdrawlRequestApproved.html",
                    "Payout sent",
                    [user.email],
                    {"first_name": user.firstname},
                )
                message = "Your referral withdrawal request has been approved."
                save_and_send_notification(user.id, message)
                # create the transaction
                ReferralWalletTransaction.objects.create(
                    user=user,
                    transaction_type="prop referral withdrawal",
                    amount=Decimal(payout_request.amount),
                    status="completed",
                )
            elif status_value == "rejected":
                reasons = request.data.get("reasons")
                if not reasons:
                    return Response(
                        {"error": "Please provide reasons for the rejection."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                AdminUserActivityLog.objects.create(
                    admin=request.user,
                    user=user,
                    action_type="rejected_withrawal",
                    description="Admin user rejected prop referral withrawal.",
                )
                # send mail to the user
                sendMail(
                    "general/WithdrawalRequestRejected.html",
                    "Payout declined",
                    [user.email],
                    {"first_name": user.firstname, "reasons": reasons},
                )
                message = "Your referral withdrawal request has been rejected."
                save_and_send_notification(user.id, message)

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HammaRequestAdminView(APIView):
    def get(self, request):
        """
        Fetch all Hamma requests. Allow search by account or user email.
        """
        account = request.GET.get("account", None)
        email = request.GET.get("email", None)
        requests = HammaAccountRequest.objects.all().order_by("-created")

        if account:
            requests = requests.filter(account__icontains=account)
        if email:
            requests = requests.filter(user__email__icontains=email)

        data = [
            {
                "id": req.id,
                "user": req.user.email,
                "account": req.account,
                "status": req.status,
                "created": req.created,
                "comment": req.comment,
                "updated": req.updated,
            }
            for req in requests
        ]
        return Response({"requests": data})

    def post(self, request):
        """
        Approve or decline a list of Hamma requests by IDs.
        If approved, duplicate the portfolio as a new Hamma portfolio.
        """
        request_id = request.data.get("request_id")
        action = request.data.get("action", None)  # 'approve' or 'decline'
        comment = request.data.get("comment", "")

        if action not in ["approve", "decline"]:
            return Response(
                {"error": 'Invalid action. Must be "approve" or "decline".'}, status=400
            )

        try:
            hamma_request = get_object_or_404(HammaAccountRequest, id=request_id)

            hamma_request.status = "Eligible" if action == "approve" else "Ineligible"
            hamma_request.comment = comment
            hamma_request.updated = now()
            hamma_request.save()

            if action == "approve":
                demo_portfolio = get_object_or_404(
                    DemoPortfolio, account_id=hamma_request.account
                )

                if demo_portfolio.has_hamma:
                    return Response(
                        {"error": "This account already has a Hamma account."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Create a new portfolio with updated attributes
                with transaction.atomic():
                    new_portfolio = DemoPortfolio.objects.create(
                        user=demo_portfolio.user,
                        balance=10_000_000,
                        account_name=demo_portfolio.model_type,
                        initial_balance=10_000_000,
                        is_prop=demo_portfolio.is_prop,
                        account_drawdown_limit=demo_portfolio.account_drawdown_limit,
                        model_type=demo_portfolio.model_type,
                        balance_based_drawdown=demo_portfolio.balance_based_drawdown,
                        account_type_level="hamma",
                    )

                    # Update the old portfolio to link to the new one
                    demo_portfolio.has_hamma = new_portfolio
                    demo_portfolio.save()

                    save_and_send_notification(
                        hamma_request.user.id,
                        f"Your Hamma account request has been approved. Check your email.",
                    )
            else:
                save_and_send_notification(
                    hamma_request.user.id,
                    f"Your Hamma account request has been declined. Reason: {comment}",
                )
            data = {
                "id": hamma_request.id,
                "user": hamma_request.user.email,
                "account": hamma_request.account,
                "status": hamma_request.status,
                "created": hamma_request.created,
                "comment": hamma_request.comment,
                "updated": hamma_request.updated,
            }
            return Response(data)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

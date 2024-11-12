from datetime import datetime, timedelta
from decimal import Decimal

from bson import is_valid
import pytz
from django.db.models import Sum, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import serialize

from accounts.models import Referral
from rest_framework import viewsets
from rest_framework.decorators import action
from affilate.models import (
    ReferralWallet,
    RewardActivities,
    ReferralWithdrawalRequest,
    ReferralWalletTransaction,
)
from affilate.serializers import (
    ReferralWalletSerializer,
    RewardActivitiesSerializer,
    ReferralRewardPayoutSerializer,
    ReferralWithdrawalRequestSerializer,
)
from notifications.utils import save_and_send_notification
from .pagination import CustomPageNumberPagination
from accounts.models import AdminUserActivityLog
from competition.managers.utils import sendMail


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

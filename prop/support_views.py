import logging
from curses.ascii import US
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.contrib.auth import get_user_model
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
from competition.managers.utils import sendMail
from execution.models import DemoPortfolio, DemoPosition, PropReceipt
from notifications.utils import save_and_send_notification
from portfolio.models import PayStackReceipts, Receipts

from .models import Payout
from .pay_service import PayoutService
from .serializers import AccountlistSerializer, PayoutDetailSerializer
from .utils import get_account_data, get_equity_balance

logger = logging.getLogger(__name__)

User = get_user_model()


class SupportUserAccounctsList(APIView):

    def get(self, request, email):
        try:
            user = User.objects.get(email=email)
            accounts = DemoPortfolio.objects.filter(
                user=user, is_prop=True, receipt_approved=True
            )
            serializer = AccountlistSerializer(accounts, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response([])

from rest_framework.views import APIView
from rest_framework.response import Response
from accounts import models as acc_models, utils as acc_utils, serializers as acc_serializers
from . import serializers as aff_serializers, models as aff_models
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework import permissions
from rest_framework.generics import get_object_or_404
from portfolio import models
from notifications.utils import save_and_send_notification
from .models import BrokageCommission, RewardActivities, ReferralWallet, ReferralWithdrawalRequest
from django.db.models import Sum
from .utils import get_quarter_dates,get_rank_details
from accounts.utils import get_referees
from datetime import datetime
from decimal import Decimal

User=get_user_model()

class MyRefferalLink(APIView):
    def get(self, request):
        code = acc_models.Profile.objects.get(user=request.user)
        return Response({"detail":code.referral_code})

class InviteFriend(APIView):
    def post(self, request):
        email=request.data.get("email")
        sendmail=acc_utils.send_invite_mail(request.user, email)
        return Response({"detail":'Invitaion sent successfully'})


class RewardActivitiesView(APIView):
    serializer_class=aff_serializers.RewardActivitiesSerializer

    def get(self, request):
        balance = ReferralWallet.objects.get_or_create(user=request.user)[0].balance
        today = datetime.now()
        today_start = today.replace(hour=0,minute=0,second=0,microsecond=0)
        income= RewardActivities.objects.filter(user=request.user, reward_type="Deposit Referral Commission").aggregate(total_commission=Sum('amount'))['total_commission']
        today_income= RewardActivities.objects.filter(user=request.user, reward_type="Deposit Referral Commission", created__gte=today_start).aggregate(total_commission=Sum('amount'))['total_commission']
        
        filter= request.GET.get("email")
        activities=""
        if filter:
            activities= aff_models.RewardActivities.objects.filter(user=request.user, trader__email=filter)
        else:
            activities= aff_models.RewardActivities.objects.filter(user=request.user)
        serializer=self.serializer_class(activities, many=True).data
        
        data1= {
            'wallet_balance':balance,
            'total_income':income,
            'today_income':today_income,
            'reward_activities':serializer
        }
        return Response(data1)
    


class RankingView(APIView):
    # serializer_class=aff_serializers.RankingsSerializer

    def get(self, request):
        first_day, last_day = get_quarter_dates()
        data_list=[]
        # users = User.objects.all()
        users = acc_models.Referral.objects.all()
        for user in users:
            data_list.append(get_rank_details(user.user, first_day))
            
        sorted_data = sorted(data_list, key=lambda x: x['brokerage_commission'], reverse=True)
        return Response(sorted_data)

class HomeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        referres =  get_referees(request.user)
        first_day, last_day = get_quarter_dates()
        
        if referres:
            brokerage_commission = BrokageCommission.objects.filter(user=request.user)
            total_commission = brokerage_commission.aggregate(total_commission=Sum('commission'))['total_commission']
            referral_commission =  ReferralWallet.objects.get(user=request.user).balance
            code = acc_models.Profile.objects.get(user=request.user).referral_code
            reward_activities = RewardActivities.objects.filter(user=request.user, created__gte=first_day)
            active_referees = reward_activities.values('trader').distinct().count()
            min_commission = brokerage_commission.filter(created__gte=first_day).aggregate(total_commission=Sum('commission'))['total_commission']
            
            data = {
                'brokerage_commission':total_commission,
                'referral_commission':referral_commission,
                'referral_code':code,
                'active_referees':active_referees,
                'min_commission':min_commission,
                'first_day':first_day,
                'last_day':last_day
            }
            
            return Response(data)
        else:
            code = acc_models.Profile.objects.get(user=request.user).referral_code
            data = {
                'referral_code':code,
                'first_day':first_day,
                'last_day':last_day,
                'details':'No referees yet'
            }
            
            return Response(data)
        
        
class ReferralWithdrawal(APIView):
    
    def post(self, request):
        amount = Decimal(request.data.get(amount))
        wallet = ReferralWallet.objects.get(user=request.user)
        
        if amount >= wallet.balance:
            ReferralWithdrawalRequest.objects.create(wallet=wallet, amount=amount)
            save_and_send_notification(request.user.id, f"Your referral commission withdrawal has been submitted.")
            return Response('Success')
        else:
            return Response('Insufficient balance')
        
class Referrees(APIView):
    serializer_class = aff_serializers.RefereeListSerializer
    
    def get(self, request):
        referees = get_referees(request.user)
        serializer = self.serializer_class(referees, many=True)
        return Response(serializer.data)
        
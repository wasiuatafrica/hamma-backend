from rest_framework.views import APIView
from rest_framework.response import Response
from accounts import models as acc_models, utils as acc_utils, serializers as acc_serializers
from . import serializers as aff_serializers, models as aff_models
from django.contrib.auth import get_user_model
from rest_framework import permissions
from notifications.utils import save_and_send_notification
from .models import BrokageCommission, RewardActivities, ReferralWallet, ReferralWithdrawalRequest, CampaignQuarter, CampaignSummary
from django.db.models import Sum
from .utils import get_quarter_dates,get_rank_details
from accounts.utils import get_referees
from datetime import datetime,timedelta
from decimal import Decimal
from rest_framework import generics, status

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


# class RewardActivitiesView(APIView):
#     serializer_class=aff_serializers.RewardActivitiesSerializer

#     def get(self, request):
#         balance = ReferralWallet.objects.get_or_create(user=request.user)[0].balance
#         today = datetime.now()
#         today_start = today.replace(hour=0,minute=0,second=0,microsecond=0)
#         income= RewardActivities.objects.filter(user=request.user, reward_type="Deposit Referral Commission").aggregate(total_commission=Sum('amount'))['total_commission']
#         today_income= RewardActivities.objects.filter(user=request.user, reward_type="Deposit Referral Commission", created__gte=today_start).aggregate(total_commission=Sum('amount'))['total_commission']
        
#         filter= request.GET.get("email")
#         activities=""
#         if filter:
#             activities= aff_models.RewardActivities.objects.filter(user=request.user, trader__email=filter)
#         else:
#             activities= aff_models.RewardActivities.objects.filter(user=request.user)
#         serializer=self.serializer_class(activities, many=True).data
        
#         data1= {
#             'wallet_balance':balance,
#             'total_income':income,
#             'today_income':today_income,
#             'reward_activities':serializer
#         }
#         return Response(data1)

from django.db.models import Sum
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import datetime, timedelta

# class RewardActivitiesView(APIView):
#     serializer_class = aff_serializers.RewardActivitiesSerializer

#     def calculate_percentage_change(self, old_value, new_value):
#         if old_value is None or new_value is None or old_value == 0:
#             return None, None

#         percentage_change = ((new_value - old_value) / abs(old_value)) * 100
#         direction = "increase" if percentage_change > 0 else "decrease"

#         return percentage_change, direction

#     def get(self, request):
#         # Retrieve existing data
#         wallet_balance = ReferralWallet.objects.get_or_create(user=request.user)[0].balance
#         today = datetime.now()
#         today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        
#         # Get old value for the period 60 to 30 days ago
#         last_30_days_start = today - timedelta(days=30)
        
#         last_60_to_30_days_start = today - timedelta(days=60)
#         last_60_to_30_days_balance = RewardActivities.objects.filter(
#             user=request.user, created__gte=last_60_to_30_days_start, created__lt=last_30_days_start
#         ).aggregate(total_balance=Sum('amount'))['total_balance']

#         # Get new value for the last 30 days
#         last_30_days_balance = RewardActivities.objects.filter(
#             user=request.user, created__gte=last_30_days_start, created__lt=today_start
#         ).aggregate(total_balance=Sum('amount'))['total_balance']

#         # Get old value for today's income change
#         last_reward_activity_before_today = RewardActivities.objects.filter(
#             user=request.user, created__lt=today_start
#         ).order_by('-created').first()
#         old_today_income = 0 if last_reward_activity_before_today is None else last_reward_activity_before_today.amount

#         # Get new value for today's income change
#         today_income = RewardActivities.objects.filter(
#             user=request.user,  created__gte=today_start
#         ).aggregate(total_commission=Sum('amount'))['total_commission']

#         # Handle None value for today_income
#         today_income = today_income if today_income is not None else 0

#         # Calculate percentage changes
#         last_60_to_30_days_balance_change_percentage, last_60_to_30_days_balance_direction = self.calculate_percentage_change(last_60_to_30_days_balance, last_30_days_balance)
#         total_income_change_percentage, total_income_direction = self.calculate_percentage_change(0, last_30_days_balance + today_income)
#         today_income_change_percentage, today_income_direction = self.calculate_percentage_change(old_today_income, today_income)

#         # Retrieve filtered activities if specified
#         filter = request.GET.get("email")
#         if filter:
#             activities = aff_models.RewardActivities.objects.filter(user=request.user, trader__email=filter)
#         else:
#             activities = aff_models.RewardActivities.objects.filter(user=request.user)
#         serializer = self.serializer_class(activities, many=True).data

#         # Prepare response data
#         data1 = {
#             'wallet_balance': wallet_balance,
#             'last_60_to_30_days_balance_change_percentage': last_60_to_30_days_balance_change_percentage,
#             'last_60_to_30_days_balance_direction': last_60_to_30_days_balance_direction,
#             'total_income': last_30_days_balance + today_income,
#             'total_income_change_percentage': total_income_change_percentage,
#             'total_income_direction': total_income_direction,
#             'today_income': today_income,
#             'today_income_change_percentage': today_income_change_percentage,
#             'today_income_direction': today_income_direction,
#             'reward_activities': serializer
#         }
#         return Response(data1)

class RewardActivitiesView(APIView):
    serializer_class = aff_serializers.RewardActivitiesSerializer

    def calculate_percentage_change(self, old_value, new_value):
        if old_value is None or new_value is None or old_value == 0:
            return None, None

        percentage_change = ((new_value - old_value) / abs(old_value)) * 100
        direction = "increase" if percentage_change > 0 else "decrease"

        return percentage_change, direction

    def get(self, request):
        # Retrieve existing data
        wallet_balance = ReferralWallet.objects.get_or_create(user=request.user)[0].balance
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get old value for the period 60 to 30 days ago
        last_30_days_start = today - timedelta(days=30)
        last_60_to_30_days_start = today - timedelta(days=60)
        last_60_to_30_days_balance = RewardActivities.objects.filter(
            user=request.user, created__gte=last_60_to_30_days_start, created__lt=last_30_days_start
        ).aggregate(total_balance=Sum('amount'))['total_balance']

        # Get new value for the last 30 days
        last_30_days_balance = RewardActivities.objects.filter(
            user=request.user, created__gte=last_30_days_start, created__lt=today_start
        ).aggregate(total_balance=Sum('amount'))['total_balance']

        if last_30_days_balance == None:
            last_30_days_balance = 0
        
        # If no records for the period 60 to 30 days ago, use records for the last 30 days
        if last_60_to_30_days_balance is None:
            last_60_to_30_days_balance = last_30_days_balance

        # Get old value for today's income change
        last_reward_activity_before_today = RewardActivities.objects.filter(
            user=request.user, created__lt=today_start
        ).order_by('-created').first()
        old_today_income = 0 if last_reward_activity_before_today is None else last_reward_activity_before_today.amount

        # Get new value for today's income change
        today_income_records = RewardActivities.objects.filter(
            user=request.user, created__gte=today_start
        )
        today_income = today_income_records.aggregate(total_commission=Sum('amount'))['total_commission']

        # Handle None value for today_income
        today_income = today_income if today_income is not None else 0

        # Calculate percentage changes
        last_60_to_30_days_balance_change_percentage, last_60_to_30_days_balance_direction = self.calculate_percentage_change(last_60_to_30_days_balance, last_30_days_balance)
        total_income_change_percentage, total_income_direction = self.calculate_percentage_change(0, last_30_days_balance + today_income)
        today_income_change_percentage, today_income_direction = self.calculate_percentage_change(old_today_income, today_income)

        if today_income_change_percentage == -100:
            today_income_change_percentage = 0
        # Retrieve filtered activities if specified
        filter = request.GET.get("email")
        if filter:
            activities = aff_models.RewardActivities.objects.filter(user=request.user, trader__email=filter)
        else:
            activities = aff_models.RewardActivities.objects.filter(user=request.user)
        serializer = self.serializer_class(activities, many=True).data

        data1 = {
            'wallet_balance': wallet_balance,
            'last_60_to_30_days_balance_change_percentage': last_60_to_30_days_balance_change_percentage,
            # 'last_60_to_30_days_balance_direction': last_60_to_30_days_balance_direction,
            'total_income': round(last_30_days_balance + today_income,2),
            # 'total_income_change_percentage': total_income_change_percentage,
            # 'total_income_direction': total_income_direction,
            'today_income': round(today_income,2),
            'today_income_change_percentage': today_income_change_percentage,
            # 'today_income_direction': today_income_direction,
            'reward_activities': serializer
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
        amount = Decimal(request.data.get('amount'))
        wallet = ReferralWallet.objects.get(user=request.user)
        
        print(amount, wallet.balance)
        if amount <= wallet.balance:
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
        
class CampaignQuarterView(APIView):
    serializer_class = aff_serializers.CampaignQuarterSerializer
    
    def get(self,request):
        campaigns = CampaignQuarter.objects.all().order_by("-id")
        data  = self.serializer_class(campaigns, many=True).data
        return Response(data)
    
    def post(self, request):
        first_prize =  request.data.get('first_prize')
        second_prize =  request.data.get('second_prize')
        third_prize =  request.data.get('third_prize')
        
        ongoing_campaign = CampaignQuarter.objects.filter(status='ongoing').first()
        if ongoing_campaign:
            ongoing_campaign.status='closed'
            ongoing_campaign.save()
            
        campaign = CampaignQuarter.objects.create(first_prize=first_prize, second_prize=second_prize, third_prize=third_prize)
        
        data = self.serializer_class(campaign).data
        return Response(data)
    
class CampaignSummaryView(APIView):
    serializer_class = aff_serializers.CampaignSummarySerializer
    
    def get(self,request, *args, **kwargs):
        id = self.kwargs.get('id')
        campaigns = CampaignSummary.objects.filter(campaign__id=id)
        data  = self.serializer_class(campaigns, many=True).data
        return Response(data)
    
class ApproveAffiliateReward(APIView):
    
    def post(self,request, *args, **kwargs):
        id = self.kwargs.get('id')
        entry = CampaignSummary.objects.filter(id=id).first()
        if entry or not entry.awarded:
            prizes = {
                '1':entry.campaign.first_prize,
                '2':entry.campaign.second_prize,
                '3':entry.campaign.third_prize,
            }
            referral_wallet= ReferralWallet.objects.get(user=entry.user)
            referral_wallet.balance += Decimal((prizes[str(entry.rank)]))
            referral_wallet.save()
            
            entry.awarded=True
            entry.save()
            
            save_and_send_notification(entry.user.id, "Your  affilaite prize has been deposited into your wallet.")

            return Response('approved', status=status.HTTP_200_OK)
        return Response('Invalid id or award already approved', status=status.HTTP_400_BAD_REQUEST)
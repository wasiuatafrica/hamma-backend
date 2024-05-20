from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.models import Referral as acc_Referral, UserActivityLog 
# from accounts import models 
from accounts import serializers as acc_serializers
import competition
from competition.models import CompetitionPosition, CompetitionTransaction
from . import serializers
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from . import permissions as acc_permissions 
from rest_framework.generics import get_object_or_404
from portfolio import models
from notifications.utils import save_and_send_notification
from decimal import Decimal
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from affilate import models as aff_models, serializers as aff_serializers
from affilate.utils import get_quarter_dates,get_rank_details
from django.db.models import Sum, F, Count, Q, ExpressionWrapper, DecimalField, Count, Subquery, Avg
from django.db.models.functions import Coalesce, TruncDay, TruncWeek
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from execution import models as exec_models
from portfolio.utils import get_price
from accounts.models import  AdminUserActivityLog 
from competition.managers.utils import sendMail 

User=get_user_model()


class LoginView(APIView):
    serializer_class= serializers.LoginSerializer
    permission_classes= ( AllowAny,)
    
    def post(self, request, *args, **kwargs):
        # print(request.data)
        serializer = serializers.LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        # print(email)
        # print(password)
        
        # Authenticate user
        user = authenticate(request, email=email, password=password)
        
        if user is not None and user.is_staff:
            refresh = RefreshToken.for_user(user)
            print(user)
            token_data = {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            activity=AdminUserActivityLog.objects.create(admin=user, user=user, action_type="login",description=f"Admin user login into their account.")
            return Response(token_data, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Invalid credentials or user is not a staff member'}, status=status.HTTP_401_UNAUTHORIZED)


class AdminManageUser(APIView):
    serializer_class= acc_serializers.AdminCustomUserSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get_object(self, user_id):
        # Get a single user by ID
        return get_object_or_404(User, id=user_id)

    def get(self, request, user_id=None):

        # filter user by email
        email=request.GET.get("email")
        if email:
            user=User.objects.filter(email=email)
            serialized_data = self.serializer_class(users, many=True).data
            return Response(serialized_data)
        
        if user_id is not None:
            # Return details of a specific user
            user = self.get_object(user_id)
            serialized_data = self.serializer_class(user).data
            return Response(serialized_data)
        else:
            # Return a list of all users
            users = User.objects.all().order_by("-date_joined")
            serialized_data = self.serializer_class(users, many=True).data
            return Response(serialized_data)
        

    def put(self, request, user_id):
        # Update details of a specific user
        user = self.get_object(user_id)
        user.save()
        serialized_data = self.serializer_class(user, data=request.data, partial=True)
        if serialized_data.is_valid():
            serialized_data.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=user, action_type="updated_account",description=f"Admin user updated a user's account.")
            return Response(serialized_data.data)
        return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        # Delete a specific user
        user = self.get_object(user_id)
        activity=AdminUserActivityLog.objects.create(admin=request.user, user=user, action_type="deleted_account",description=f"Admin user deleted a user's account.")
        user.delete()
        return Response({"detail":"User deleted successfully"},status=status.HTTP_204_NO_CONTENT)


class AdminReceiptsView(APIView):
    serializer_class = serializers.AdminReceiptsViewSerializer
    permission_classes=[permissions.IsAuthenticated]  
    
    
    def get(self, request):
        # receipts=models.Receipts.objects.all().order_by('-id')
        # # print(receipts)
        # serializer = self.serializer_class(data=receipts, many=True)
        # serializer.is_valid()
        # return Response(serializer.data) 
        email=request.GET.get("email")
        filter=request.GET.get('filter')
        receipts_data = []
        if filter == "bank_tranfer":
            for receipt in Receipts.objects.filter(user__email=email).order_by("-created"):
                receipt_dict = {
                    'id': receipt.id,
                    'amount': receipt.amount,
                    'created': receipt.created,
                    'receipt_status': receipt.receipt_status,
                    'payment_method': receipt.payment_method,
                    "fullname":receipt.user.fullname,
                    "comment":receipt.comment,
                    "approved_date":receipt.approved_date,
                    "image_url":receipt.image.url,
                    "user":receipt.user.id,
                    "flag":receipt.flag,
                    "timestamp":receipt.created.timestamp(),
                    
                }
                receipts_data.append(receipt_dict)
        elif filter == "paystack":
            for paystack_receipt in PayStackReceipts.objects.filter(user__email=email).order_by("-date"):
                paystack_receipt_dict = {
                    'id': paystack_receipt.id,
                    'amount': paystack_receipt.amount,
                    'created': paystack_receipt.date,
                    'receipt_status': paystack_receipt.receipt_status,
                    'payment_method': "paystack",
                    "user":paystack_receipt.user.id,
                    "image_url":"",
                    "approved_date":"",
                    "comment":paystack_receipt.comment,
                    "fullname":paystack_receipt.user.fullname,
                    "flag":paystack_receipt.flag,
                    "timestamp":paystack_receipt.date.timestamp(),

                }
                receipts_data.append(paystack_receipt_dict)
        else:
            for receipt in Receipts.objects.all().order_by("-created"):
                receipt_dict = {
                    'id': receipt.id,
                    'amount': receipt.amount,
                    'created': receipt.created,
                    'receipt_status': receipt.receipt_status,
                    'payment_method': receipt.payment_method,
                    "fullname":receipt.user.fullname,
                    "comment":receipt.comment,
                    "approved_date":receipt.approved_date,
                    "image_url":receipt.image.url,
                    "user":receipt.user.id,
                    "flag":receipt.flag,
                    "timestamp":receipt.created.timestamp(),
                }
                receipts_data.append(receipt_dict)

            for paystack_receipt in PayStackReceipts.objects.all().order_by("-date"):
                paystack_receipt_dict = {
                    'id': paystack_receipt.id,
                    'amount': paystack_receipt.amount,
                    'created': paystack_receipt.date,
                    'receipt_status': paystack_receipt.receipt_status,
                    'payment_method': "paystack",
                    "user":paystack_receipt.user.id,
                    "image_url":"",
                    "approved_date":"",
                    "comment":paystack_receipt.comment,
                    "fullname":paystack_receipt.user.fullname,
                    "flag":paystack_receipt.flag,
                    "timestamp":paystack_receipt.date.timestamp(),

                }
                receipts_data.append(paystack_receipt_dict)
        receipts_data2 = sorted(receipts_data, key=lambda x: x['timestamp'], reverse=True)
        return Response(receipts_data2)

    
    def post(self, request):
        
        statuses = ['approved','rejected']
        
        id = request.data["id"]
        amount = request.data["amount"]
        receipt_status =request.data["receipt_status"]
        comment =request.data["comment"]
        
        if receipt_status not in statuses:
            return Response('receipt_status must either be approved or rejected ')
        
        receipt=models.Receipts.objects.get(id=id)
        receipt.receipt_status=receipt_status
        receipt.save()
        
        if receipt_status == 'approved':
            receipt.amount=amount
            receipt.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=receipt.user, action_type="approved_reciept",description=f"Admin user approved reciept.")

            wallet= Wallet.objects.get_or_create(user=receipt.user)[0]
            amount = Decimal(amount)
            wallet.balance += amount
            wallet.save()
            
            save_and_send_notification(wallet.user.id, f"{amount} credited to your wallet.")
            mail=sendMail("general/depositRecieptApproved.html","Deposit receipt Approved",[receipt.user.email],{"first_name":receipt.user.firstname,"amount":amount})
            
            models.Transaction.objects.create(user=wallet.user, transaction_type='deposit',amount=amount, status='completed', channel='Bank Transfer')
            
            refer_object=acc_Referral.objects.filter(person_referred=wallet.user).first()
            
            if refer_object and refer_object.converted == False:
                sum_user_trans=sum(trans.amount for trans in models.Transaction.objects.filter(user=wallet.user, transaction_type = 'deposit'))
                if sum_user_trans >= 50000 :
                    referal_wallet = aff_models.ReferralWallet.objects.get_or_create(user=refer_object.user)[0]
                    referal_wallet.balance += Decimal(5000)
                    referal_wallet.save()
                    
                    refer_object.converted == True
                    refer_object.save()
                    
                    
                    aff_models.RewardActivities.objects.create(trader=wallet.user, amount=5000, reward_type="Deposit Referral Commission", user=refer_object.user)
                    # send notfication
                    # save_and_send_notification(referred_by.referred_by.id, f"{wallet.user.firstname} just depoisted >= 50000. Congratulations")

            receipt_data = {
                'id': receipt.id,
                'user': receipt.user.id,
                'fullname':receipt.user.fullname,
                'amount': receipt.amount,
                'payment_method': receipt.payment_method,
                'receipt_status': receipt.receipt_status,
                'comment': receipt.comment,
                'created': receipt.created,
                'approved_date': receipt.approved_date,
                'image_url': receipt.image.url if receipt.image else None,
            }
            return Response(receipt_data)
        elif receipt_status == 'rejected':
            receipt.comment = comment
            receipt.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=receipt.user, action_type="rejected_reciept",description=f"Admin user rejected reciept.")
            receipt_data = {
                'id': receipt.id,
                'user': receipt.user.id,
                'fullname':receipt.user.fullname,
                'amount': receipt.amount,
                'payment_method': receipt.payment_method,
                'receipt_status': receipt.receipt_status,
                'comment': receipt.comment,
                'created': receipt.created,
                'approved_date': receipt.approved_date,
                'image_url': receipt.image.url if receipt.image else None,
            }
            save_and_send_notification(receipt.user.id, f"Your payment receipt has been rejected. Reason: {receipt.comment}.")
            
            return Response(receipt_data)
        
class WithdrawalView(APIView):
    serializer_class = serializers.WithdrawalSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        receipts=exec_models.WithdrawalRequest.objects.all().order_by('-created')
        serializer = self.serializer_class(data=receipts, many=True)
        serializer.is_valid()
        
        receipts2=aff_models.ReferralWithdrawalRequest.objects.all().order_by('-created')
        serializer2 = aff_serializers.ReferralWithdrawalRequestSerializer(data=receipts2, many=True)
        serializer2.is_valid()
        
        total = serializer.data + serializer2.data
        total_new = sorted(total, key= lambda x : x['created'], reverse=True)
        
        return Response(total_new) 
    
    def post(self, request):
        id = request.data.get('id')
        action = request.data.get('action')
        type = request.data.get('type', None)
        
        if not type or type not in ['main', 'referral']:
            return Response('type key must be present and it be either main or referral', status=status.HTTP_400_BAD_REQUEST)
        
        if type == 'main':
            withdrawal= exec_models.WithdrawalRequest.objects.get(id=id)
            wallet= Wallet.objects.get(user=withdrawal.user)
            
            allowed = ['approved','rejected']
        
            if action not in allowed:
                return Response('action must be approved or rejected')
            
            if action == 'approved' and wallet.balance >= Decimal(withdrawal.amount):
                wallet.balance -= Decimal(withdrawal.amount)
                wallet.save()
                
                withdrawal.status = 'approved'
                withdrawal.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal.user, action_type="approved_withrawal",description=f"Admin user approved withrawal.")
                
                save_and_send_notification(wallet.user.id, f"Your withdrawal of {withdrawal.amount} has been approved.")
                mail=sendMail("general/withdrawlRequestApproved.html","Payout sent",[wallet.user.email],{"first_name":wallet.user.firstname})
                models.Transaction.objects.create(user=wallet.user, transaction_type='withdrawal',amount=Decimal(withdrawal.amount), status='completed')

                
                data = {
                    'id':withdrawal.id,
                    'fullname':withdrawal.user.fullname,
                    'user_id':withdrawal.user.id,
                    'amount':withdrawal.amount,
                    'status':withdrawal.status,
                    'created':withdrawal.created,
                    'type':'main'
                    
                }
                
                return Response(data)
            
            elif action == 'rejected':
                withdrawal.status = 'rejected'
                withdrawal.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal.user, action_type="rejected_withrawal",description=f"Admin user rejected withrawal.")
                save_and_send_notification(wallet.user.id, f"Your withdrawal of {withdrawal.amount} has been rejected.")
                mail=sendMail("general/WithdrawalRequestRejected.html","Payout declined",[wallet.user.email],{"first_name":wallet.user.firstname})
                
                data = {
                    'id':withdrawal.id,
                    'fullname':withdrawal.user.fullname,
                    'user_id':withdrawal.user.id,
                    'amount':withdrawal.amount,
                    'status':withdrawal.status,
                    'created':withdrawal.created,
                    'type':'main'
                }
                
                return Response(data)
            else:
                return Response("Insufficient fund")
        elif type == 'referral':
            withdrawal= aff_models.ReferralWithdrawalRequest.objects.get(id=id)
            wallet = aff_models.ReferralWallet.objects.get(user=withdrawal.user)
            
        # wallet = withdrawal.wallet
            allowed = ['approved','rejected']
            
            if action not in allowed:
                return Response('action must be approved or rejected')
            
            if action == 'approved' and wallet.balance >= Decimal(withdrawal.amount):
                wallet.balance -= Decimal(withdrawal.amount)
                wallet.save()
                
                withdrawal.status = 'approved'
                withdrawal.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal.user, action_type="approved_referral_withrawal",description=f"Admin user approved referral withrawal.")
                
                save_and_send_notification(wallet.user.id, f"Your referral withdrawal of {withdrawal.amount} has been approved.")
                models.Transaction.objects.create(user=wallet.user, transaction_type='referral withdrawal',amount=Decimal(withdrawal.amount), status='completed')
                mail=sendMail("general/withdrawlRequestApproved.html","Payout sent",[wallet.user.email],{"first_name":wallet.user.firstname})
                
                data = {
                    'id':withdrawal.id,
                    'fullname':withdrawal.user.fullname,
                    'user_id':withdrawal.user.id,
                    'amount':withdrawal.amount,
                    'status':withdrawal.status,
                    'created':withdrawal.created,
                    'type':'referral'
                    
                }
                
                return Response(data)
        
            elif action == 'rejected':
                withdrawal.status = 'rejected'
                withdrawal.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal.wallet.user, action_type="rejected_referral_withrawal",description=f"Admin user rejected referral withrawal.")
                save_and_send_notification(wallet.user.id, f"Your referral withdrawal of {withdrawal.amount} has been rejected.")
                mail=sendMail("general/WithdrawalRequestRejected.html","Payout declined",[wallet.user.email],{"first_name":wallet.user.firstname})
                
                data = {
                    'id':withdrawal.id,
                    'fullname':withdrawal.user.fullname,
                    'user_id':withdrawal.user.id,
                    'amount':withdrawal.amount,
                    'status':withdrawal.status,
                    'created':withdrawal.created,
                    'type':'referral'
                    
                }
                
                return Response(data)
        
            else:
                return Response("Insufficient fund")

class CheckBalance(APIView):
    
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def post(self, request):
        id = request.data.get('id')
        type = request.data.get('type', None)
        
        if not type or type not in ['main', 'referral']:
            return Response('type key must be present and it be either main or referral', status=status.HTTP_400_BAD_REQUEST)
        
        if type == 'main':
            withdrawal= exec_models.WithdrawalRequest.objects.get(id=id)
            wallet= Wallet.objects.get(user=withdrawal.wallet.user)
            
            
            if wallet.balance > Decimal(withdrawal.amount):
                return Response(True) 
            else:
                return Response(False)
        elif type == 'referral':
            withdrawal= aff_models.ReferralWithdrawalRequest.objects.get(id=id)
            wallet = aff_models.ReferralWallet.objects.get(user=withdrawal.wallet.user)
            if wallet.balance > Decimal(withdrawal.amount):
                return Response(True)
            else:
                return Response(False)
      
class AdminTradeView(APIView):
    serializer_class = serializers.DemoPositionSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        # trades = models.Trade.objects.all().order_by('-id')
        trades = exec_models.DemoPosition.objects.all().order_by('-updated')
        comp_trades = CompetitionPosition.objects.all().order_by('-updated')
        
        serializer = self.serializer_class(data=trades, many=True)
        serializer2 = serializers.CompeitionPositionSerializer(data=comp_trades, many=True)
        serializer.is_valid()
        serializer2.is_valid()
        
        data = serializer.data + serializer2.data
        sorted_data = sorted(data, key=lambda x: x['updated'], reverse=True)

        return Response(sorted_data)
        


class AdminApproveAndViewRewardActivities(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    def get_object(self, id):
        try:
            return aff_models.RewardActivities.objects.get(id=id)
        except aff_models.RewardActivities.DoesNotExist:
            return None

    def get(self, request):
        filter= request.GET.get("email_value")
        query_type= request.GET.get("query_type")
        activities=""
        
        if filter and query_type:
            # print("fq")
            if query_type == "email":
                # print("email")
                activities= aff_models.RewardActivities.objects.filter(user__email=filter)
            elif query_type == "referral_commission":
                # print("acc")
                activities= aff_models.RewardActivities.objects.filter(reward_type="referral_commission")
            elif query_type == "broker_commission":
                # print("broker")
                activities= aff_models.RewardActivities.objects.filter(reward_type="Brokage Commission")
        else:
            activities= aff_models.RewardActivities.objects.all()
        data = [
            {
                "id":act.id,
                "referring_user":act.user.fullname,
                "referred_user":act.trader.fullname,
                "reward":act.reward_type,
                "amount":act.amount,
                "status":act.status,
                "date": act.created,
                "user_id":act.trader.id,
                "flag":act.flag,
                "tethered_requirements":["10% Brokerayge commission for every trade by the referred user for life", "50,000 deposits from referred user"]
            } for act in activities
        ]
        return Response(data)

    # def put(self, request):
    #     reward_id=request.GET.get("id")
    #     instance=self.get_object(reward_id)
     
    #     if not reward_id:
    #         return Response({"detail":"The reward's ID to be updated is required"}, status.HTTP_400_BAD_REQUEST)
    #     if instance is None:
    #         return Response({"detail": "User instance not found"}, status.HTTP_404_NOT_FOUND)
    #     serializer=self.serializer_class(instance,data=request.data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         if serializer.validated_data["status"]=='approved' :
    #             save_and_send_notification(instance.user.id, f"Your reward commision of {instance.amount} has been processed.")
    #         elif serializer.validated_data["status"]=='declined' :
    #             save_and_send_notification(instance.user.id, f"Your reward commision from {instance.username} has been declined due to {instance.comment}.")
    #         return Response (serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AffilateManagement(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self, request):
        filter= request.GET.get("email")
        
        first_day, last_day = get_quarter_dates()
        
        data_list=[]
        # users = User.objects.all()
        
        if filter:
            users = acc_Referral.objects.filter(user__email=filter)
        else:            
            users = acc_Referral.objects.all()
            
        for user in users:
            data_list.append(get_rank_details(user.user, first_day))
            
        sorted_data = sorted(data_list, key=lambda x: x['brokerage_commission'], reverse=True)
        return Response(sorted_data)

from accounts.models import UserActivityLog
from portfolio.models import Stock, Receipts, PayStackReceipts, Wallet
from execution.models import Portfolio
# from portfolio.serializers import TradeSerializer

class UserActivityLogView(APIView):
    serializer_class=acc_serializers.UserActivityLogSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self,request, *args, **kwargs):
        id=kwargs.get("id")
        filter=request.GET.get("filter")
        if filter:
            activities=UserActivityLog.objects.filter(user__id=id, action_type=filter).order_by("-id")
        else:
            activities=UserActivityLog.objects.filter(user__id=id).order_by("-id")
        serializer=self.serializer_class(activities, many=True)
        return Response(serializer.data)
    
class AllUsersActivityLogView(APIView):
    serializer_class=acc_serializers.UserActivityLogSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self,request):
        filter=request.GET.get("filter")
        if filter:
            if filter == "active":
                activities=UserActivityLog.objects.filter(user__is_active=True).order_by("-timestamp")
            elif filter == "inactive":
                activities=UserActivityLog.objects.filter(user__is_active=False).order_by("-timestamp")
            else:
                activities=UserActivityLog.objects.filter(action_type=filter).order_by("-timestamp")

        else:
            activities=UserActivityLog.objects.all().order_by("-timestamp")
        serializer=self.serializer_class(activities, many=True)
        return Response(serializer.data)
    

class UserTradeActivityLog(APIView):
    serializer_class=serializers.DemoPositionSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self, request, *args, **kwargs):
        id=kwargs.get("id")
        filter=request.GET.get('filter')
        if filter:
            trade_history= exec_models.DemoPosition.objects.filter(portfolio__user__id=id,order_type__icontains=filter).order_by("-id")
        else:
            trade_history= exec_models.DemoPosition.objects.filter(portfolio__user__id=id).order_by("-id")
        serializer=self.serializer_class(trade_history,many=True)
        return Response(serializer.data)

class UserPaymentActivityLog(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self, request, *args, **kwargs):
        id=kwargs.get("id")
        filter=request.GET.get('filter')
        receipts_data = []
        if filter == "bank_tranfer":
            for receipt in Receipts.objects.filter(user__id=id, ).order_by("-id"):
                receipt_dict = {
                    'id': receipt.id,
                    'amount': receipt.amount,
                    'date': receipt.date,
                    'receipt_status': receipt.receipt_status,
                    'payment_method': receipt.payment_method,
                }
                receipts_data.append(receipt_dict)
        elif filter == "paystack":
            for paystack_receipt in PayStackReceipts.objects.filter(user__id=id).order_by("-id"):
                paystack_receipt_dict = {
                    'id': paystack_receipt.id,
                    'amount': paystack_receipt.amount,
                    'date': paystack_receipt.date,
                    'receipt_status': paystack_receipt.receipt_status,
                    'payment_method': "paystack",

                }
                receipts_data.append(paystack_receipt_dict)
        else:
            for receipt in Receipts.objects.filter(user__id=id):
                receipt_dict = {
                    'id': receipt.id,
                    'amount': receipt.amount,
                    'date': receipt.date,
                    'receipt_status': receipt.receipt_status,
                    'payment_method': receipt.payment_method,
                }
                receipts_data.append(receipt_dict)

            for paystack_receipt in PayStackReceipts.objects.filter(user__id=id):
                paystack_receipt_dict = {
                    'id': paystack_receipt.id,
                    'amount': paystack_receipt.amount,
                    'date': paystack_receipt.date,
                    'receipt_status': paystack_receipt.receipt_status,
                    'payment_method': "paystack",

                }
                receipts_data.append(paystack_receipt_dict)
        return Response(receipts_data)
    
class UserAssetBreakDown(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    def get(self, request, *args, **kwargs):
        id=kwargs.get("id")
        portfolio = Portfolio.objects.get(user__id=id)
        holding=portfolio.holdings.all()
        
        holding_data=[
        
            {
                "symbol":data.stock.symbol,
                "company":data.stock.company,
                "value":round(float(data.cur_val),2),
                "amount":data.quantity,
                "seven_days":"47.6"
            } for data in holding]
        # print(holding_data)
        wallet = Wallet.objects.get(user__id=id)
        acc_summary={
            "fiat_acc_balance":wallet.balance,
            "no_of_stocks_owned" : holding.count(),
            "total_val_of_stocks_owned": portfolio.portfolio_value(),
            "seven_days":"47.6"
        }
        print(acc_summary)
        return Response({"acc_summary":acc_summary, "stock_history":holding_data})

    

# class AnalyticsView(APIView):
#     permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
#     def get(self, request):
#         def calculate_percentage_change(old_value, new_value):
#             return round(((new_value - old_value) / old_value) * 100,2) if old_value != 0 else 0
        
#         #users
#         users = User.objects.all()
        
#         active_users= users.filter(is_active=True).count()
        
#         current_month = datetime.now().month
#         current_year = datetime.now().year


#         last_month = datetime(current_year, current_month, 1)
#         users_last_month = User.objects.filter(is_active=True, date_joined__lt=last_month).count()

#         user_percentage_change = calculate_percentage_change(users_last_month, active_users)
#         print(active_users, user_percentage_change)
        
        
#         #Assets        
        
#         positions =exec_models.DemoPosition.objects.all()
        
#         positions_open = positions.filter(status='open')
#         positions_close = positions.filter(status='close')
#         total_portfolio_value = round(sum([position.amount_invested for position in positions_close]),2)
        
#         portfolio_before = positions_close.filter(created__lt=datetime(current_year, current_month, 1))
        
#         portfolios_before_this_month = sum([position.amount_invested for position in portfolio_before]) if portfolio_before else 0
#         percentage_of_total_assets = round(calculate_percentage_change(portfolios_before_this_month, total_portfolio_value),2)
        
        
#         #Transactions
#         transactions = models.DemoTransaction.objects.all()
#         total_transactions = transactions.count()
#         transactions_before = transactions.filter(date__lt=datetime(current_year, current_month, 1)).count()
#         transaction_change = calculate_percentage_change(transactions_before,total_transactions )
        
#         print('transactions', total_transactions, transaction_change)
        
#         # Calculate average daily active users
#         users_activity = UserActivityLog.objects.values('user', 'timestamp__date').annotate(daily_activity=Count('id'))
#         total_daily_active_users = users_activity.values('timestamp__date').annotate(total_activity=Count('user')).aggregate(total_users=Sum('total_activity'))['total_users']
#         average_daily_users = total_daily_active_users / users_activity.values('timestamp__date').count() if users_activity.values('timestamp__date').count() != 0 else 0
        
#         users_activity_before_this_month = UserActivityLog.objects.filter(timestamp__date__lt=datetime(current_year, current_month, 1)).values('user', 'timestamp__date').annotate(daily_activity=Count('id'))
#         total_daily_active_users_before_this_month = users_activity_before_this_month.values('timestamp__date').annotate(total_activity=Count('user')).aggregate(total_users=Sum('total_activity'))['total_users']
#         average_daily_users_before_this_month = total_daily_active_users_before_this_month / users_activity_before_this_month.values('timestamp__date').count() if users_activity_before_this_month.values('timestamp__date').count() != 0 else 0

#         percentage_change_average_daily_users = calculate_percentage_change(average_daily_users_before_this_month,average_daily_users)

#         print('activities',average_daily_users,percentage_change_average_daily_users)
        
       
        
#         positions_closed = positions.filter(status='close')
#         top_10 = positions_closed.order_by("-profit_loss")[:10]
#         top_performing = [
#             {   'user':position.portfolio.user.fullname,
#                 'profit':position.profit_loss,
#                 'symbol':position.stock.symbol,
#                 }
#             for position in top_10
#         ]
        
        
#         # most_traded_stock = Stock.objects.annotate(num_positions=Count('demopositions2')).filter(num_positions__gt=0).order_by('-num_positions')
#         most_traded_stock = Stock.objects.annotate(num_positions=Count('demopositions2', filter=Q(demopositions2__status='open'))).filter(num_positions__gt=0).order_by('-num_positions')

#         # print(most_traded_stock)
        
#         def get_stock(stock):
#             data=get_price(stock.symbol)
#             if data:
#                 price= data.get('current_price')
#                 change = data.get('percentage_change',0)
#                 unique_users_count = positions_open.filter(stock=stock).values('portfolio__user').distinct().count()
                
#                 data = {
#                     'symbol':stock.symbol,
#                     'current_price':price,
#                     'percentage_change':change,
#                     'num_positions': stock.num_positions,
#                     'num_users': unique_users_count
#                 }
#                 return data
        
#         with ThreadPoolExecutor() as executor:
#                 futures = executor.map(get_stock, most_traded_stock)
#                 traded_stock = [result for result in futures if result]
                
#         traded_stock = sorted(traded_stock, key=lambda x: x['num_users'], reverse=True)
            
#         data = {
#             'total_registered_users': active_users,
#             'percentage_change_registered_users': user_percentage_change,  
#             'total_assets_under_mgmt': total_portfolio_value,
#             'percentage_change_assets_under_mgmt': percentage_of_total_assets,  
#             'total_transactions': total_transactions,
#             'percentage_change_total_transactions': transaction_change,  
#             'average_daily_active_users': int(average_daily_users),
#             'percentage_change_daily_active_users': percentage_change_average_daily_users, 
#             "top_performing_stock":top_performing,
#             "most_traded_stock":traded_stock
             
#             # Add other metrics as needed
#         }

#         return Response(data)



def get_user_activity_stats(query):
    import datetime
    # Get the start date (April 15, 2024)
    start_date = datetime.date(2024, 4, 15)

    # Get the current date
    current_date = timezone.now().date()

    # Get the last month's start and end dates
    last_month_start = (current_date.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    last_month_end = current_date.replace(day=1) - datetime.timedelta(days=1)

    # Get the daily average user count since April 15, 2024
    daily_average_users = query.filter(
        timestamp__date__gte=start_date
    ).annotate(
        day=TruncDay('timestamp')
    ).values('day').annotate(
        count=Count('user', distinct=True)
    ).aggregate(
        avg=Avg('count')
    )['avg']

    # Get the average user count for the last month
    last_month_average_users = query.filter(
        timestamp__date__range=(last_month_start, last_month_end)
    ).annotate(
        day=TruncDay('timestamp')
    ).values('day').annotate(
        count=Count('user', distinct=True)
    ).aggregate(
        avg=Avg('count')
    )['avg']

    # Calculate the percentage change
    if last_month_average_users:
        percentage_change = (daily_average_users - last_month_average_users) / last_month_average_users * 100
    else:
        percentage_change = 0

    return daily_average_users, int(percentage_change)

class AnalyticsView(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    def get(self, request):
        def calculate_percentage_change(old_value, new_value):
            return round(((new_value - old_value) / old_value) * 100,2) if old_value != 0 else 0
        
        #users
        users = User.objects.all()
        
        active_users= users.filter(is_active=True).count()
        
        current_month = datetime.now().month
        current_year = datetime.now().year


        last_month = datetime(current_year, current_month, 1)
        users_last_month = User.objects.filter(is_active=True, date_joined__lt=last_month).count()

        user_percentage_change = calculate_percentage_change(users_last_month, active_users)
        print(active_users, user_percentage_change)
        
        
        #Assets        
        
        positions = exec_models.DemoPosition.objects.all()
        comp_positions = CompetitionPosition.objects.all()
        
        positions_open = positions.filter(status='open')
        positions_close = positions.filter(status='close')
        comp_positions_open = comp_positions.filter(status='open')
        comp_positions_close = comp_positions.filter(status='close')
        
        total_portfolio_value = round(sum([position.amount_invested for position in positions_close]) + sum([position.amount_invested for position in comp_positions_close]), 2)
        
        portfolio_before = positions_close.filter(created__lt=datetime(current_year, current_month, 1))
        comp_portfolio_before = comp_positions_close.filter(created__lt=datetime(current_year, current_month, 1))
        
        portfolios_before_this_month = sum([position.amount_invested for position in portfolio_before]) + sum([position.amount_invested for position in comp_portfolio_before]) if portfolio_before or comp_portfolio_before else 0
        percentage_of_total_assets = round(calculate_percentage_change(portfolios_before_this_month, total_portfolio_value),2)
        
        
        #Transactions
        transactions = models.DemoTransaction.objects.all()
        comp_transactions = CompetitionTransaction.objects.all()
        total_transactions = transactions.count() + comp_transactions.count()
        transactions_before = transactions.filter(date__lt=datetime(current_year, current_month, 1)).count()
        comp_transactions_before = comp_transactions.filter(date__lt=datetime(current_year, current_month, 1)).count()
        transaction_change = calculate_percentage_change(transactions_before + comp_transactions_before, total_transactions)
        
        print('transactions', total_transactions, transaction_change)
        
        # # Calculate average daily active users
        # users_activity = UserActivityLog.objects.values('user', 'timestamp__date').annotate(daily_activity=Count('id'))
        # total_daily_active_users = users_activity.values('timestamp__date').annotate(total_activity=Count('user')).aggregate(total_users=Sum('total_activity'))['total_users']
        # # average_daily_users = total_daily_active_users / users_activity.values('timestamp__date').count() if users_activity.values('timestamp__date').count() != 0 else 0
        
        # current_date = datetime.now()
        # april_15_2024 = datetime(2024, 4, 15)

        # # Calculate the number of days since April 15, 2024
        # days_since_start = (current_date - april_15_2024).days

        # # Query UserActivityLog since April 15, 2024
        # # users_activity = UserActivityLog.objects.filter(timestamp__date__gte=april_15_2024).values('timestamp__date').annotate(total_activity=Count('user', distinct=True))

        # # Calculate total active users since April 15, 2024
        # # total_daily_active_users = sum(item['total_activity'] for item in users_activity)

        # # Calculate average daily active users since April 15, 2024
        # average_daily_users = total_daily_active_users / days_since_start if days_since_start != 0 else 0

        # users_activity_before_this_month = UserActivityLog.objects.filter(timestamp__date__lt=datetime(current_year, current_month, 1)).values('user', 'timestamp__date').annotate(daily_activity=Count('id'))
        # total_daily_active_users_before_this_month = users_activity_before_this_month.values('timestamp__date').annotate(total_activity=Count('user')).aggregate(total_users=Sum('total_activity'))['total_users']
        # average_daily_users_before_this_month = total_daily_active_users_before_this_month / users_activity_before_this_month.values('timestamp__date').count() if users_activity_before_this_month.values('timestamp__date').count() != 0 else 0

        # percentage_change_average_daily_users = calculate_percentage_change(average_daily_users_before_this_month,average_daily_users)

        # print('activities',average_daily_users,percentage_change_average_daily_users)
        
        user_activity_queryset = UserActivityLog.objects.all()
        daily_average_users, percentage_change_average_daily_users = get_user_activity_stats(user_activity_queryset)
        
       
        
        positions_closed = positions.filter(status='close')
        comp_positions_closed = comp_positions.filter(status='close')
        # top_10 = list(positions_closed.order_by("-profit_loss")[:10]) + list(comp_positions_closed.order_by("-profit_loss")[:10])
        top_10 = list(positions_closed) + list(comp_positions_closed)
        top_10.sort(key=lambda x: x.profit_loss, reverse=True)
        top_10 = top_10[:10]
        
        top_performing = [
            {   'user':position.portfolio.user.fullname,
                'profit':position.profit_loss,
                'symbol':position.stock.symbol,
                }
            for position in top_10
        ]
        
        
        # most_traded_stock = Stock.objects.annotate(num_positions=Count('demopositions2')).filter(num_positions__gt=0).order_by('-num_positions')
        most_traded_stock = Stock.objects.annotate(num_positions=Count('demopositions2', filter=Q(demopositions2__status='open')) + Count('composition', filter=Q(composition__status ='open'))).filter(num_positions__gt=1).order_by('-num_positions')
        most_traded_stock = most_traded_stock[:10]
        # print(most_traded_stock)
        
        def get_stock(stock):
            data=get_price(stock.symbol)
            if data:
                price= data.get('current_price')
                change = data.get('percentage_change',0)
                unique_users_count = positions_open.filter(stock=stock).values('portfolio__user').distinct().count() + comp_positions_open.filter(stock=stock).values('portfolio__user').distinct().count()
                
                data = {
                    'symbol':stock.symbol,
                    'current_price':price,
                    'percentage_change':change,
                    'num_positions': stock.num_positions,
                    'num_users': unique_users_count
                }
                return data
        
        with ThreadPoolExecutor() as executor:
                futures = executor.map(get_stock, most_traded_stock)
                traded_stock = [result for result in futures if result]
                
        traded_stock = sorted(traded_stock, key=lambda x: x['num_users'], reverse=True)
            
        data = {
            'total_registered_users': active_users,
            'percentage_change_registered_users': user_percentage_change,  
            'total_assets_under_mgmt': total_portfolio_value,
            'percentage_change_assets_under_mgmt': percentage_of_total_assets,  
            'total_transactions': total_transactions,
            'percentage_change_total_transactions': transaction_change,  
            'average_daily_active_users': int(daily_average_users),
            'percentage_change_daily_active_users': percentage_change_average_daily_users, 
            "top_performing_stock":top_performing,
            "most_traded_stock":traded_stock
             
            # Add other metrics as needed
        }

        return Response(data)


class DeactivateAccount(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    def post(self, request):
        user_id=request.data.get("user_id")
        keyword=request.data.get("keyword")
        user= User.objects.filter(id=user_id).first()
        if not user_id and keyword:
            return Response({"detail":"user_id and keyword is must not be empty"}, status.HTTP_400_BAD_REQUEST)
        if not user:
            return Response({"detail":"user not found"}, status.HTTP_404_NOT_FOUND)
        if keyword == "deactivate":
            user.is_active=False
            user.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=user, action_type="deactivated_account",description=f"Admin user deactivated user account.")
            return Response({"detail":"user account deactivated successfully"}, status.HTTP_200_OK)
        elif keyword == "activate":
            user.is_active=True
            user.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=user, action_type="activated_account",description=f"Admin user activated user account.")
            return Response({"detail":"user account activated successfully"}, status.HTTP_200_OK)
        return Response({"detail":"Invalid keyword. Use activate or deactivate"}, status.HTTP_400_BAD_REQUEST)

from affilate.models import RewardActivities,ReferralWallet  
from  affilate import serializers as aff_serializers  
class RewardActivitiesView(APIView):
    serializer_class = aff_serializers.RewardActivitiesSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def calculate_percentage_change(self, old_value, new_value):
        if old_value is None or new_value is None or old_value == 0:
            return None, None

        percentage_change = ((new_value - old_value) / abs(old_value)) * 100
        direction = "increase" if percentage_change > 0 else "decrease"

        return percentage_change, direction

    def get(self, request, *args, **kwargs):
        user_id=kwargs.get("user_id")
        user=User.objects.filter(id=user_id).first()
        if not user:
            return Response({"detail":f"user with id {user_id} not found"}, status.HTTP_404_NOT_FOUND)
        # Retrieve existing data
        wallet_balance = ReferralWallet.objects.get_or_create(user=user)[0].balance
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get old value for the period 60 to 30 days ago
        last_30_days_start = today - timedelta(days=30)
        last_60_to_30_days_start = today - timedelta(days=60)
        last_60_to_30_days_balance = RewardActivities.objects.filter(
            user=user, created__gte=last_60_to_30_days_start, created__lt=last_30_days_start
        ).aggregate(total_balance=Sum('amount'))['total_balance']

        # Get new value for the last 30 days
        last_30_days_balance = RewardActivities.objects.filter(
            user=user, created__gte=last_30_days_start, created__lt=today_start
        ).aggregate(total_balance=Sum('amount'))['total_balance']

        # If no records for the period 60 to 30 days ago, use records for the last 30 days
        if last_60_to_30_days_balance is None:
            last_60_to_30_days_balance = last_30_days_balance

        # Get old value for today's income change
        last_reward_activity_before_today = RewardActivities.objects.filter(
            user=user, created__lt=today_start
        ).order_by('-created').first()
        old_today_income = 0 if last_reward_activity_before_today is None else last_reward_activity_before_today.amount

        # Get new value for today's income change
        today_income_records = RewardActivities.objects.filter(
            user=user, created__gte=today_start
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
            activities = aff_models.RewardActivities.objects.filter(user=user, trader__email=filter)
        else:
            activities = aff_models.RewardActivities.objects.filter(user=user)
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
    
class FlagReciept(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    def post(self, request, *args, **kwargs):
        reciept_id= kwargs.get("reciept_id")
        keyword =request.data.get("keyword")
        if not reciept_id and keyword:
            return Response({"detail":"reciept_id and keyword must not be empty"}, status.HTTP_400_BAD_REQUEST)
        recipt=Receipts.objects.filter(id=reciept_id).first()
        if not recipt:
            return Response({"detail":f"recipt with id {reciept_id} not found"}, status.HTTP_404_NOT_FOUND)
        if keyword == "unflag":
            recipt.flag=False
            recipt.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=recipt.user, action_type="unflagged_reciept",description=f"Admin user unflagged reciept.")
            return Response({"detail":"recipt unflagged successfully"}, status.HTTP_200_OK)
        elif keyword == "flag":
            recipt.flag=True
            recipt.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=recipt.user, action_type="flagged_reciept",description=f"Admin user flagged reciept.")
            return Response({"detail":"recipt flagged successfully"}, status.HTTP_200_OK)
        return Response({"detail":"Invalid keyword. Use flagged or unflagged"}, status.HTTP_400_BAD_REQUEST)
    
class FlagRewardActivities(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    def post(self, request, *args, **kwargs):
        reward_activity_id= kwargs.get("reward_activity_id")
        keyword =request.data.get("keyword")
        if not reward_activity_id and keyword:
            return Response({"detail":"reward_activity_id and keyword must not be empty"}, status.HTTP_400_BAD_REQUEST)
        reward_activity=RewardActivities.objects.filter(id=reward_activity_id).first()
        if not reward_activity:
            return Response({"detail":f"reward_activity with id {reward_activity_id} not found"}, status.HTTP_404_NOT_FOUND)
        if keyword == "unflag":
            reward_activity.flag=False
            reward_activity.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=reward_activity.user, action_type="unflagged_reward_activity",description=f"Admin user unflagged reward_activity.")
            return Response({"detail":"reward_activity unflagged successfully"}, status.HTTP_200_OK)
        elif keyword == "flag":
            reward_activity.flag=True
            reward_activity.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=reward_activity.user, action_type="flagged_reward_activity",description=f"Admin user flagged reward_activity.")
            return Response({"detail":"reward_activity flagged successfully"}, status.HTTP_200_OK)
        return Response({"detail":"Invalid keyword. Use flagged or unflagged"}, status.HTTP_400_BAD_REQUEST)
    
class FlagWithdrawalRequest(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    def post(self, request,*args, **kwargs):
        withdrawal_request_id= kwargs.get("withdrawal_request_id")
        type =  request.data.get('type', None)
        
        if not type or type not in ['main', 'referral']:
            return Response('type key must be present and it be either main or referral', status=status.HTTP_400_BAD_REQUEST)
        if type == 'main':
            keyword =request.data.get("keyword")
            if not withdrawal_request_id and keyword:
                return Response({"detail":"withdrawal_request_id and keyword must not be empty"}, status.HTTP_400_BAD_REQUEST)
            withdrawal_request=exec_models.WithdrawalRequest.objects.filter(id=withdrawal_request_id).first()
            if not withdrawal_request:
                return Response({"detail":f"withdrawal_request with id {withdrawal_request_id} not found"}, status.HTTP_404_NOT_FOUND)
            if keyword == "unflag":
                withdrawal_request.flag=False
                withdrawal_request.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal_request.wallet.user, action_type="unflagged_withdrawal_request",description=f"Admin user unflagged withdrawal request.")
                return Response({"detail":"withdrawal_request unflagged successfully"}, status.HTTP_200_OK)
            elif keyword == "flag":
                withdrawal_request.flag=True
                withdrawal_request.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal_request.wallet.user, action_type="flagged_withdrawal_request",description=f"Admin user flagged withdrawal request.")
                return Response({"detail":"withdrawal_request flagged successfully"}, status.HTTP_200_OK)
            return Response({"detail":"Invalid keyword. Use flagged or unflagged"}, status.HTTP_400_BAD_REQUEST)
        elif type == 'referral':
            keyword =request.data.get("keyword")
            if not withdrawal_request_id and keyword:
                return Response({"detail":"withdrawal_request_id and keyword must not be empty"}, status.HTTP_400_BAD_REQUEST)
            
            withdrawal_request=aff_models.ReferralWithdrawalRequest.objects.filter(id=withdrawal_request_id).first()
            
            if not withdrawal_request:
                return Response({"detail":f"referral withdrawal_request with id {withdrawal_request_id} not found"}, status.HTTP_404_NOT_FOUND)
            if keyword == "unflag":
                withdrawal_request.flag=False
                withdrawal_request.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal_request.wallet.user, action_type="unflagged_referral_withdrawal_request",description=f"Admin user unflagged referral withdrawal request.")
                return Response({"detail":"referral withdrawal_request unflagged successfully"}, status.HTTP_200_OK)
            elif keyword == "flag":
                withdrawal_request.flag=True
                withdrawal_request.save()
                activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal_request.wallet.user, action_type="flagged_referral_withdrawal_request",description=f"Admin user flagged referral withdrawal request.")
                return Response({"detail":"referral withdrawal_request flagged successfully"}, status.HTTP_200_OK)
            return Response({"detail":"Invalid keyword. Use flagged or unflagged"}, status.HTTP_400_BAD_REQUEST)


from django.utils import timezone
from django.db.models import Count, DateTimeField, DateField, CharField
from django.db.models.functions import Trunc,ExtractWeekDay,ExtractWeek, TruncDate

class AnalyticsGraphView(APIView):
    def get(self, request):
        users = User.objects.filter(is_active=True)
        # For the last 1 week in daily points
        last_week_data1 = users.filter(date_joined__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('date_joined', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 month in daily points
        last_month_data1 = users.filter(date_joined__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('date_joined', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data1 = users.filter(date_joined__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('date_joined', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 year in monthly points
        last_year_data1 = users.filter(date_joined__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('date_joined', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Total registered users in monthly points
        total_users_data1 = users.annotate(
            date=Trunc('date_joined', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 week in daily points
        transactions = models.DemoTransaction.objects.all()
        last_week_data21 = transactions.filter(date__gte=timezone.now() - timedelta(days=7)).annotate(
            transaction_date=Trunc('date', 'day', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 1 month in daily points
        last_month_data21 = transactions.filter(date__gte=timezone.now() - timedelta(days=30)).annotate(
            transaction_date=Trunc('date', 'day', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 3 months in weekly points
        last_3_months_data21 = transactions.filter(date__gte=timezone.now() - timedelta(days=90)).annotate(
            transaction_date=Trunc('date', 'week', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 1 year in monthly points
        last_year_data21 = transactions.filter(date__gte=timezone.now() - timedelta(days=365)).annotate(
            transaction_date=Trunc('date', 'month', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # Total transactions in monthly points
        total_transactions_data21 = transactions.annotate(
            transaction_date=Trunc('date', 'month', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')



        #####Competition transactions
        # For the last 1 week in daily points
        last_week_data5 = CompetitionTransaction.objects.filter(date__gte=timezone.now() - timedelta(days=7)).annotate(
            transaction_date=Trunc('date', 'day', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 1 month in daily points
        last_month_data5 = CompetitionTransaction.objects.filter(date__gte=timezone.now() - timedelta(days=30)).annotate(
            transaction_date=Trunc('date', 'day', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 3 months in weekly points
        last_3_months_data5 = CompetitionTransaction.objects.filter(date__gte=timezone.now() - timedelta(days=90)).annotate(
            transaction_date=Trunc('date', 'week', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 1 year in monthly points
        last_year_data5 = CompetitionTransaction.objects.filter(date__gte=timezone.now() - timedelta(days=365)).annotate(
            transaction_date=Trunc('date', 'month', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # Total competition transactions in monthly points
        total_competition_transactions_data5 = CompetitionTransaction .objects.annotate(
            transaction_date=Trunc('date', 'month', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')
        
        # print('demo',last_week_data21)
        # print('comp',last_week_data5)
        last_week_data2 = self.merge_transaction_data(last_week_data21,last_week_data5)
        last_month_data2 = self.merge_transaction_data(last_month_data21,last_month_data5)
        last_3_months_data2 = self.merge_transaction_data(last_3_months_data21,last_3_months_data5)
        last_year_data2 = self.merge_transaction_data(last_year_data21,last_year_data5)
        total_transactions_data2 = self.merge_transaction_data(total_transactions_data21,total_competition_transactions_data5)
                
        # For the last 1 week in daily points
        useractivity = UserActivityLog.objects.all()
        last_week_data3 = useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('timestamp', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # For the last 1 month in daily points
        last_month_data3 = useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('timestamp', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data3 =useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('timestamp', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # For the last 1 year in monthly points
        last_year_data3 = useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('timestamp', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # Total active users in monthly points
        total_active_users_data3 = useractivity.annotate(
            date=Trunc('timestamp', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        
        positions =exec_models.DemoPosition.objects.filter(status='close')
        
        # For the last 1 week in daily points
        last_week_data41 = positions.filter(created__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('updated', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 month in daily points
        last_month_data41 = positions.filter(created__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('updated', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data41 = positions.filter(created__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('updated', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 year in monthly points
        last_year_data41 = positions.filter(created__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('updated', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Total positions created in monthly points
        total_positions_data41 = positions.annotate(
            date=Trunc('updated', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        ####Competitionpositions
        competitionpositions = CompetitionPosition.objects.filter(status='close')
        
        # For the last 1 week in daily points
        last_week_data61 = competitionpositions.filter(created__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('updated', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 month in daily points
        last_month_data61 = competitionpositions.filter(created__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('updated', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data61 = competitionpositions.filter(created__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('updated', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 year in monthly points
        last_year_data61 = competitionpositions.filter(created__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('updated', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Total competition positions created in monthly points
        total_competition_positions_data61 = competitionpositions.annotate(
            date=Trunc('updated', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')
        
        last_week_data4 = self.merge_position_data(last_week_data41,last_week_data61)
        last_month_data4 = self.merge_position_data(last_month_data41,last_month_data61)
        last_3_months_data4 = self.merge_position_data(last_3_months_data41,last_3_months_data61)
        last_year_data4 = self.merge_position_data(last_year_data41,last_year_data61)
        total_positions_data4 = self.merge_position_data(total_positions_data41,total_competition_positions_data61)
        
        result = (
            positions.annotate(
                truncated_created=TruncDate('created'),
                stock_symbol=F('stock__symbol')  
            )
            .values('truncated_created', 'stock_symbol')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('truncated_created', 'stock_symbol')
        )

        competition_positions_result = (
            competitionpositions.annotate(
                truncated_created=TruncDate('created'),
                stock_symbol=F('stock__symbol')  
            )
            .values('truncated_created', 'stock_symbol')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('truncated_created', 'stock_symbol')
        )
                
        weekday_mapping = {
            0: 'Monday',
            1: 'Tuesday',
            2: 'Wednesday',
            3: 'Thursday',
            4: 'Friday',
            5: 'Saturday',
            6: 'Sunday',
        }

        volume_data = {}
        volume_data_competition = {}

        # Extract weekday for each date
        for entry in result:
            truncated_created = entry['truncated_created']
            weekday_digit = truncated_created.weekday()
            weekday = weekday_mapping.get(weekday_digit, 'Unknown')
            stock_symbol = entry['stock_symbol']
            volume = entry['total_quantity']

            if stock_symbol not in volume_data:
                volume_data[stock_symbol] = []

            data = {
                'date': truncated_created,
                'weekday': weekday,
                'volume': volume,
                'type': 'demo'
            }

            volume_data[stock_symbol].append(data)

        
        for entry in competition_positions_result:
            truncated_created = entry['truncated_created']
            weekday_digit = truncated_created.weekday()
            weekday = weekday_mapping.get(weekday_digit, 'Unknown')
            stock_symbol = entry['stock_symbol']
            volume = entry['total_quantity']

            if stock_symbol not in volume_data_competition:
                volume_data_competition[stock_symbol] = []
            
            data = {
                'date': truncated_created,
                'weekday': weekday,
                'volume': volume,
                'type': 'competition'
            }

            volume_data_competition[stock_symbol].append(data)
        # print(last_week_data2)
        grouped_data = {
            'last_week_data': self.organize_data(list(last_week_data1),list(last_week_data2),list(last_week_data3),list(last_week_data4)),
            'last_month_data': self.organize_data(list(last_month_data1),list(last_month_data2),list(last_month_data3),list(last_month_data4)),
            'last_3_months_data': self.organize_data(list(last_3_months_data1),list(last_3_months_data2),list(last_3_months_data3),list(last_3_months_data4)),
            'last_year_data': self.organize_data(list(last_year_data1),list(last_year_data2),list(last_year_data3),list(last_year_data4)),
            'total_users_data': self.organize_data(list(total_users_data1),list(total_transactions_data2), list(total_active_users_data3), list(total_positions_data4)),
            "volume_data":volume_data,
            "volume_data_competition":volume_data_competition
        }

        return Response(grouped_data)

    def organize_data(self, data_list1,data_list2,data_list3,data_list4):
        # Create a dictionary to store data organized by date
        organized_data = {}

        # Iterate over the data list and organize by date
        for data_point in data_list1:
            date = data_point['date']
            
            # If the date is not present in the organized_data, add it with default values
            if date not in organized_data:
                organized_data[date] = {
                    'date': date,
                    'registered_users': 0,
                    'transaction_data': 0,
                    'user_activity_data': 0,
                    'positions_data': 0,
                }

            # Update the corresponding values based on the data type
            organized_data[date]['registered_users'] = data_point.get('count', 0)
            # Update other data types similarly
        for data_point2 in data_list2:
            # print(data_point2)
            date = data_point2['transaction_date']
            
            # If the date is not present in the organized_data, add it with default values
            if date not in organized_data:
                organized_data[date] = {
                    'date': date,
                    'registered_users': 0,
                    'transaction_data': 0,
                    'user_activity_data': 0,
                    'positions_data': 0,
                }

            # Update the corresponding values based on the data type
            organized_data[date]['transaction_data'] = data_point2.get('count', 0)
        for data_point3 in data_list3:
            date = data_point3['date']
            
            # If the date is not present in the organized_data, add it with default values
            if date not in organized_data:
                organized_data[date] = {
                    'date': date,
                    'registered_users': 0,
                    'transaction_data': 0,
                    'user_activity_data': 0,
                    'positions_data': 0,
                }

            # Update the corresponding values based on the data type
            organized_data[date]['user_activity_data'] = data_point3.get('count', 0)
        for data_point4 in data_list4:
            date = data_point4['date']
            
            # If the date is not present in the organized_data, add it with default values
            if date not in organized_data:
                organized_data[date] = {
                    'date': date,
                    'registered_users': 0,
                    'transaction_data': 0,
                    'user_activity_data': 0,
                    'positions_data': 0,
                }

            # Update the corresponding values based on the data type
            organized_data[date]['positions_data'] = data_point4.get('count', 0)
        # Convert the organized data into a list of dictionaries
        result = list(organized_data.values())
        
        # Sort the result by date
        result = sorted(result, key=lambda x: x['date'])

        return result
    
    

    def merge_position_data(self,data_list1, data_list2):
        from collections import defaultdict
        # Convert query results to dictionaries for easier manipulation
        positions_data1 = {entry['date']: entry['count'] for entry in data_list1}
        positions_data2 = {entry['date']: entry['count'] for entry in data_list2}

        # Merge the data using a defaultdict to aggregate counts for each date
        merged_data = defaultdict(int)

        # Add counts from the first list
        for date, count in positions_data1.items():
            merged_data[date] += count

        # Add counts from the second list
        for date, count in positions_data2.items():
            merged_data[date] += count

        # Convert defaultdict back to a list of dictionaries
        merged_data_list = [{'date': date, 'count': count} for date, count in merged_data.items()]

        # Sort the merged data by date
        merged_data_list.sort(key=lambda x: x['date'])

        return merged_data_list

    def merge_transaction_data(self,data_list1, data_list2):
        from collections import defaultdict

        # Convert query results to dictionaries for easier manipulation
        positions_data1 = {entry['transaction_date']: entry['count'] for entry in data_list1}
        positions_data2 = {entry['transaction_date']: entry['count'] for entry in data_list2}

        # Merge the data using a defaultdict to aggregate counts for each date
        merged_data = defaultdict(int)

        # Add counts from the first list
        for date, count in positions_data1.items():
            merged_data[date] += count

        # Add counts from the second list
        for date, count in positions_data2.items():
            merged_data[date] += count

        # Convert defaultdict back to a list of dictionaries
        merged_data_list = [{'transaction_date': date, 'count': count} for date, count in merged_data.items()]

        # Sort the merged data by date
        merged_data_list.sort(key=lambda x: x['transaction_date'])

        return merged_data_list


class AllAdminUsersActivityLogView(APIView):
    serializer_class=acc_serializers.AdminUserActivityLogSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self,request):
        filter=request.GET.get("filter")
        if filter:
            activities=AdminUserActivityLog.objects.filter(action_type__icontains=filter).order_by("-timestamp")

        else:
            activities=AdminUserActivityLog.objects.all().order_by("-timestamp")
        serializer=self.serializer_class(activities, many=True)
        return Response(serializer.data)

# class AdminClanUpdateLogoAndLInk(APIView):
#     serializer_class = competion_serializers.ClanNameChangeRequestSerializer
#     permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]

#     # get all requests
#     def get(self, request):
#         clan_name_requests = competion_models.ClanNameChangeRequest.objects.all()
#         serializer = self.serializer_class(clan_name_requests, many=True)
#         return Response(serializer.data)
        

# class AdminClanMemeberRemoverRequest(APIView):
#     serializer_class = competion_serializers.ClanMemeberRemoverRequestSerializer
#     permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]

#     # get all requests
#     def get(self, request):
#         clan_member_removal_requests = competion_models.ClanMemeberRemoverRequest.objects.all()
#         serializer = self.serializer_class(clan_member_removal_requests, many=True)
#         return Response(serializer.data)
        
        




# class UserActivityChartData(APIView):
#     def get(self, request):
#         # Define Friday as the start of the week
#         def get_friday_of_week(date):
#             days_to_friday = (4 - date.weekday() + 7) % 7
#             friday_date = date + timedelta(days=days_to_friday)
#             return friday_date

#         active_users = UserActivityLog.objects.filter(
#             action_type__in=["competition_open_trade", "demo_open_trade"]
#         )

#         # Group active_users by week (using Friday as the start of the week) and count number of users in each week
#         weekly_active_users = active_users.annotate(
#             week=TruncWeek('timestamp', output_field=DateField())
#         ).values('week').annotate(total_users=Count('user', distinct=True))

#         # Calculate number of key active users (opened 10 or more trades) in each week
#         user_trade_counts = active_users.values('user').annotate(
#             total_trades=Count('id')
#         ).filter(total_trades__gte=10).values('user')

#         key_active_users = active_users.annotate(
#             week=TruncWeek('timestamp', output_field=DateField())
#         ).filter(
#             user__in=Subquery(user_trade_counts)
#         ).values('week').annotate(
#             key_active_users=Count('user', distinct=True)
#         )

#         # Prepare data for chart and table
#         chart_data = [{'week': get_friday_of_week(item['week']), 'active_users': item['total_users']} for item in weekly_active_users]
#         table_data = [{'week': get_friday_of_week(item['week']), 'active_users': item['total_users'], 'key_active_users': next((key_item['key_active_users'] for key_item in key_active_users if key_item['week'] == item['week']), 0)} for item in weekly_active_users]

#         return Response({'chart_data': chart_data, 'table_data': table_data})




# from django.db.models import Count, TruncWeek, Subquery
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from datetime import datetime, timedelta
# from .models import UserActivityLog

# class UserActivityChartData(APIView):
#     def get(self, request):
#         active_users = UserActivityLog.objects.filter(
#             action_type__in=["competition_open_trade", "demo_open_trade"]
#         )

#         # Group active_users by week and count number of users in each week
#         weekly_active_users = (
#             active_users.annotate(
#                 week=TruncWeek('timestamp')
#             )
#             .values('week')
#             .annotate(total_users=Count('user', distinct=True))
#             .order_by('week')
#         )

#         # Calculate number of key active users (opened 10 or more trades) in each week
#         user_trade_counts = (
#             active_users.values('user')
#             .annotate(total_trades=Count('id'))
#             .filter(total_trades__gte=10)
#             .values('user')
#         )

#         key_active_users = (
#             active_users.annotate(week=TruncWeek('timestamp'))
#             .filter(user__in=Subquery(user_trade_counts))
#             .values('week')
#             .annotate(key_active_users=Count('user', distinct=True))
#             .order_by('week')
#         )

#         data = []
#         for week in weekly_active_users:
#             week_start = week['week']
#             week_end = week_start + timedelta(days=7)  # Monday of the next week
#             key_active_user_count = next(
#                 (item['key_active_users'] for item in key_active_users if item['week'] == week['week']),
#                 0
#             )
#             # List of active users for the week
#             active_user_list = list(
#                 active_users.filter(
#                     timestamp__date__gte=week_start, 
#                     timestamp__date__lt=week_end
#                 ).values_list('user', flat=True).distinct()
#             )
#             # List of key active users for the week
#             key_active_user_list = list(
#                 active_users.filter(
#                     timestamp__date__gte=week_start,
#                     timestamp__date__lt=week_end,
#                     user__in=Subquery(user_trade_counts)
#                 ).values_list('user', flat=True).distinct()
#             )
#             data.append({
#                 'date': week_start.date(),
#                 'active_users': week['total_users'],
#                 'key_active_users': key_active_user_count,
#                 'active_user_list': active_user_list,
#                 'key_active_user_list': key_active_user_list
#             })

#         return Response({'data': data})

class UserActivityChartData(APIView):
    def get(self, request):
        active_users = UserActivityLog.objects.filter(
            action_type__in=["competition_open_trade", "demo_open_trade"]
        )

        # Group active_users by week and count number of users in each week
        weekly_active_users = (
            active_users.annotate(
                week=TruncWeek('timestamp')
            )
            .values('week')
            .annotate(total_users=Count('user', distinct=True))
            .order_by('week')
        )

        data = []
        for week in weekly_active_users:
            week_start = week['week']
            week_end = week_start + timedelta(days=7)  # Monday of the next week

            # Filter active_users for the current week
            users_this_week = active_users.filter(timestamp__date__gte=week_start, timestamp__date__lt=week_end)

            # Count the number of trades made by each user in this week
            user_trade_counts = users_this_week.values('user').annotate(total_trades=Count('id'))

            # Filter users who have made 10 or more trades in this week
            key_active_users_this_week = user_trade_counts.filter(total_trades__gte=10)

            data.append({
                'date': week_start.date(),
                'active_users': week['total_users'],
                'key_active_users': key_active_users_this_week.count(),
                'active_user_list': list(users_this_week.values_list('user', flat=True).distinct()),
                'key_active_user_list': list(key_active_users_this_week.values_list('user', flat=True).distinct())
            })

        return Response(data)

class UserDetails(APIView):
    def post(self, request):
        # Get the list of user IDs from the request data
        user_ids = request.data.get('user_ids', [])
        # print(user_ids)

        # Fetch user details for each user ID
        users = User.objects.filter(id__in=user_ids)
        serializer = acc_serializers.AdminCustomUserSerializer(users, many=True)
               

        return Response(serializer.data)

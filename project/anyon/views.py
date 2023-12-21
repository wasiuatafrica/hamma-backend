
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.models import Referral as acc_Referral
from accounts import models 
from accounts import serializers as acc_serializers
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
            
            token_data = {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            return Response(token_data, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'Invalid credentials or user is not a staff member'}, status=status.HTTP_401_UNAUTHORIZED)


class AdminManageUser(APIView):
    serializer_class= acc_serializers.CustomUserSerializer
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
            users = User.objects.all()
            serialized_data = self.serializer_class(users, many=True).data
            return Response(serialized_data)
        

    def put(self, request, user_id):
        # Update details of a specific user
        user = self.get_object(user_id)
        user.save()
        serialized_data = self.serializer_class(user, data=request.data, partial=True)
        if serialized_data.is_valid():
            serialized_data.save()
            return Response(serialized_data.data)
        return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        # Delete a specific user
        user = self.get_object(user_id)
        user.delete()
        return Response({"detail":"User deleted successfully"},status=status.HTTP_204_NO_CONTENT)

class AdminReceiptsView(APIView):
    serializer_class = serializers.AdminReceiptsViewSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        receipts=models.Receipts.objects.all().order_by('-id')
        # print(receipts)
        serializer = self.serializer_class(data=receipts, many=True)
        serializer.is_valid()
        return Response(serializer.data) 
    
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
            
            wallet=models.Wallet.objects.get(user=receipt.user)
            amount = Decimal(amount)
            wallet.balance += amount
            wallet.save()
            
            save_and_send_notification(wallet.user.id, f"{amount} credited to your wallet.")
            
            models.Transaction.objects.create(user=wallet.user, transaction_type='deposit',amount=amount)
            
            refer_object=acc_Referral.objects.get(person_referred=wallet.user)
            
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
            save_and_send_notification(receipt.user.id, f"Yoour payment receipt has been rejected. Reason: {receipt.comment}.")
            
            return Response(receipt_data)
        
class WithdrawalView(APIView):
    serializer_class = serializers.WithdrawalSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        receipts=models.WithdrawalRequest.objects.all().order_by('-id')
        serializer = self.serializer_class(data=receipts, many=True)
        serializer.is_valid()
        return Response(serializer.data) 
    
    def post(self, request):
        id = request.data.get('id')
        action = request.data.get('action')
        withdrawal= models.WithdrawalRequest.objects.get(id=id)
        wallet = withdrawal.wallet
        allowed = ['approved','rejected']
        
        if action not in allowed:
            return Response('action must be approved or rejected')
        
        if action == 'approved' and wallet.balance > Decimal(withdrawal.amount):
            wallet.balance -= Decimal(withdrawal.amount)
            wallet.save()
            
            withdrawal.status = 'approved'
            withdrawal.save()
            
            save_and_send_notification(wallet.user.id, f"Your withdrawal of {withdrawal.amount} has been processed.")
            models.Transaction.objects.create(user=wallet.user, transaction_type='withdrawal',amount=withdrawal.amount)
            
            data = {
                'id':withdrawal.id,
                'fullname':withdrawal.wallet.user.fullname,
                'user_id':withdrawal.wallet.user.id,
                'amount':withdrawal.amount,
                'status':withdrawal.status,
                'created':withdrawal.created,
            }
            
            return Response(data)
        
        elif action == 'rejected':
            withdrawal.status = 'rejected'
            withdrawal.save()
            
            save_and_send_notification(wallet.user.id, f"Your withdrawal of {withdrawal.amount} has been rejected.")
            
            data = {
                'id':withdrawal.id,
                'fullname':withdrawal.wallet.user.fullname,
                'user_id':withdrawal.wallet.user.id,
                'amount':withdrawal.amount,
                'status':withdrawal.status,
                'created':withdrawal.created,
            }
            
            return Response(data)
        
        else:
            return Response("Insufficient fund")
        
class AdminTradeView(APIView):
    serializer_class = serializers.TradeSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        trades = models.Trade.objects.all().order_by('-id')
        serializer = self.serializer_class(data=trades, many=True)
        serializer.is_valid()
        return Response(serializer.data)
        


class AdminApproveAndViewRewardActivities(APIView):
    serializer_class=aff_serializers.RewardActivitiesSerializer


    def get_object(self, id):
        try:
            return aff_models.RewardActivities.objects.get(id=id)
        except aff_models.RewardActivities.DoesNotExist:
            return None

    def get(self, request):
        filter= request.GET.get("filter_params")
        query_type= request.GET.get("query_type")
        activities=""
        
        if filter and query_type:
            print("fq")
            if query_type == "email":
                print("email")
                activities= aff_models.RewardActivities.objects.filter(user__email=filter)
            elif query_type == "purhase_account":
                print("acc")
                activities= aff_models.RewardActivities.objects.filter(reward_type="Purchased an account")
            elif query_type == "broker_commission":
                print("broker")
                activities= aff_models.RewardActivities.objects.filter(reward_type="Brokage Commission")
        else:
            activities= aff_models.RewardActivities.objects.all()
        serializer=self.serializer_class(activities, many=True).data
        return Response(serializer)

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

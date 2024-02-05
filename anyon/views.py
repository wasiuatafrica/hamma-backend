
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts.models import Referral as acc_Referral, UserActivityLog 
# from accounts import models 
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
from django.db.models import Sum, F, Count, Q, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from execution import models as exec_models
from portfolio.utils import get_price
from accounts.models import  AdminUserActivityLog 



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
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=user, action_type="updated_account",description=f"Admin user updated a user's account.")
            return Response(serialized_data.data)
        return Response(serialized_data.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        # Delete a specific user
        user = self.get_object(user_id)
        activity=AdminUserActivityLog.objects.create(admin=request.user, user=user, action_type="deleted_account",description=f"Admin user deleted a user's account.")
        user.delete()
        return Response({"detail":"User deleted successfully"},status=status.HTTP_204_NO_CONTENT)

from itertools import zip_longest
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
                    "image_url":str(receipt.image),
                    "user":receipt.user.id,
                    "flag":receipt.flag
                    
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
                    "flag":paystack_receipt.flag

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
                    "image_url":str(receipt.image),
                    "user":receipt.user.id,
                    "flag":receipt.flag
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
                    "flag":paystack_receipt.flag

                }
                receipts_data.append(paystack_receipt_dict)
        receipts_data.sort(key=lambda x: x['created'], reverse=True)
        return Response(receipts_data)

    
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
            # wallet=models.Wallet.objects.get(user=receipt.user)
            wallet= exec_models.Portfolio.objects.get(user=request.user)
            amount = Decimal(amount)
            wallet.balance += amount
            wallet.save()
            
            save_and_send_notification(wallet.user.id, f"{amount} credited to your wallet.")
            
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
            save_and_send_notification(receipt.user.id, f"Yoour payment receipt has been rejected. Reason: {receipt.comment}.")
            
            return Response(receipt_data)
        
class WithdrawalView(APIView):
    serializer_class = serializers.WithdrawalSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        receipts=exec_models.WithdrawalRequest.objects.all().order_by('-id')
        serializer = self.serializer_class(data=receipts, many=True)
        serializer.is_valid()
        return Response(serializer.data) 
    
    def post(self, request):
        id = request.data.get('id')
        action = request.data.get('action')
        withdrawal= exec_models.WithdrawalRequest.objects.get(id=id)
        # wallet = withdrawal.wallet
        wallet= exec_models.Portfolio.objects.get(user=withdrawal.wallet.user)
        allowed = ['approved','rejected']
        
        if action not in allowed:
            return Response('action must be approved or rejected')
        
        if action == 'approved' and wallet.balance > Decimal(withdrawal.amount):
            wallet.balance -= Decimal(withdrawal.amount)
            wallet.save()
            
            withdrawal.status = 'approved'
            withdrawal.save()
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal.wallet.user, action_type="approved_withrawal",description=f"Admin user approved withrawal.")
            
            save_and_send_notification(wallet.user.id, f"Your withdrawal of {withdrawal.amount} has been approved.")
            models.Transaction.objects.create(user=wallet.user, transaction_type='withdrawal',amount=Decimal(withdrawal.amount), status='completed')
            
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
            activity=AdminUserActivityLog.objects.create(admin=request.user, user=withdrawal.wallet.user, action_type="rejected_withrawal",description=f"Admin user rejected withrawal.")
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
    serializer_class = serializers.PositionSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    
    
    def get(self, request):
        trades = models.Trade.objects.all().order_by('-id')
        trades = exec_models.DemoPosition.objects.all().order_by('-updated')
        serializer = self.serializer_class(data=trades, many=True)
        serializer.is_valid()
        return Response(serializer.data)
        


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
            elif query_type == "purhase_account":
                # print("acc")
                activities= aff_models.RewardActivities.objects.filter(reward_type="Purchased an account")
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
from portfolio.models import Stock, Trade, Holding, Receipts, PayStackReceipts, Portfolio, Wallet
from portfolio.serializers import TradeSerializer

class UserActivityLogView(APIView):
    serializer_class=acc_serializers.UserActivityLogSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self,request, *args, **kwargs):
        id=kwargs.get("id")
        filter=request.GET.get("filter")
        if filter:
            activities=UserActivityLog.objects.filter(user__id=id, action_type=filter)
        else:
            activities=UserActivityLog.objects.filter(user__id=id)
        serializer=self.serializer_class(activities, many=True)
        return Response(serializer.data)
    
class AllUsersActivityLogView(APIView):
    serializer_class=acc_serializers.UserActivityLogSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self,request):
        filter=request.GET.get("filter")
        if filter:
            if filter == "active":
                activities=UserActivityLog.objects.filter(user__is_active=True)
            elif filter == "inactive":
                activities=UserActivityLog.objects.filter(user__is_active=False)
            else:
                activities=UserActivityLog.objects.filter(action_type=filter)

        else:
            activities=UserActivityLog.objects.all()
        serializer=self.serializer_class(activities, many=True)
        return Response(serializer.data)
    

class UserTradeActivityLog(APIView):
    serializer_class=TradeSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self, request, *args, **kwargs):
        id=kwargs.get("id")
        filter=request.GET.get('filter')
        if filter:
            trade_history= Trade.objects.filter(user__id=id,order_type__icontains=filter)
        else:
            trade_history= Trade.objects.filter(user__id=id)
        serializer=self.serializer_class(trade_history,many=True)
        return Response(serializer.data)

class UserPaymentActivityLog(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self, request, *args, **kwargs):
        id=kwargs.get("id")
        filter=request.GET.get('filter')
        receipts_data = []
        if filter == "bank_tranfer":
            for receipt in Receipts.objects.filter(user__id=id, ):
                receipt_dict = {
                    'id': receipt.id,
                    'amount': receipt.amount,
                    'date': receipt.date,
                    'receipt_status': receipt.receipt_status,
                    'payment_method': receipt.payment_method,
                }
                receipts_data.append(receipt_dict)
        elif filter == "paystack":
            for paystack_receipt in PayStackReceipts.objects.filter(user__id=id):
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

        # users_this_month = User.objects.filter(is_active=True, date_joined__month=current_month, date_joined__year=current_year).count()

        last_month = datetime(current_year, current_month, 1)
        # last_month = datetime(current_year, current_month, 1) - timedelta(days=1)
        
        # users_last_month = User.objects.filter(is_active=True, date_joined__month=last_month.month, date_joined__year=last_month.year).count()
        users_last_month = User.objects.filter(is_active=True, date_joined__lt=last_month).count()

        user_percentage_change = calculate_percentage_change(users_last_month, active_users)
        print(active_users, user_percentage_change)
        
        
        #Assets        
        # portfolios = Portfolio.objects.all()
        
        # total_portfolio_value = round(sum(portfolio.portfolio_value() for portfolio in portfolios),2)
        
        # portfolio_before= portfolios.filter(created__lt=datetime(current_year, current_month, 1))
        
        # # total_assets_under_mgmt = portfolios.aggregate(Sum('portfolio_value'))['portfolio_value__sum'] or Decimal(0)
        # portfolios_before_this_month = sum(port.portfolio_value() for port in portfolio_before) if portfolio_before else 0
        # percentage_of_total_assets = round(calculate_percentage_change(portfolios_before_this_month, total_portfolio_value),2)

        # print(total_portfolio_value, percentage_of_total_assets)
        
        positions =exec_models.DemoPosition.objects.all()
        
        positions_open = positions.filter(status='open')
        total_portfolio_value = round(sum([position.amount_invested for position in positions]),2)
        
        portfolio_before = positions.filter(created__lt=datetime(current_year, current_month, 1))
        
        portfolios_before_this_month = sum([position.amount_invested for position in portfolio_before]) if portfolio_before else 0
        percentage_of_total_assets = round(calculate_percentage_change(portfolios_before_this_month, total_portfolio_value),2)
        
        
        #Transactions
        transactions = models.DemoTransaction.objects.all()
        total_transactions = transactions.count()
        transactions_before = transactions.filter(date__lt=datetime(current_year, current_month, 1)).count()
        transaction_change = calculate_percentage_change(transactions_before,total_transactions )
        
        print('transactions', total_transactions, transaction_change)
        
        # Calculate average daily active users
        users_activity = UserActivityLog.objects.values('user', 'timestamp__date').annotate(daily_activity=Count('id'))
        total_daily_active_users = users_activity.values('timestamp__date').annotate(total_activity=Count('user')).aggregate(total_users=Sum('total_activity'))['total_users']
        average_daily_users = total_daily_active_users / users_activity.values('timestamp__date').count() if users_activity.values('timestamp__date').count() != 0 else 0
        
        users_activity_before_this_month = UserActivityLog.objects.filter(timestamp__date__lt=datetime(current_year, current_month, 1)).values('user', 'timestamp__date').annotate(daily_activity=Count('id'))
        total_daily_active_users_before_this_month = users_activity_before_this_month.values('timestamp__date').annotate(total_activity=Count('user')).aggregate(total_users=Sum('total_activity'))['total_users']
        average_daily_users_before_this_month = total_daily_active_users_before_this_month / users_activity_before_this_month.values('timestamp__date').count() if users_activity_before_this_month.values('timestamp__date').count() != 0 else 0

        percentage_change_average_daily_users = calculate_percentage_change(average_daily_users_before_this_month,average_daily_users)

        print('activities',average_daily_users,percentage_change_average_daily_users)
        
        # #top traded stocks
        # def symbol_details(symbol):
        #     stock= get_object_or_404(Stock, symbol=symbol)
        #     return {'symbol':symbol, 'price':stock.ltp, 'change':round(uniform(-4,4),2)}
        # def most_traded_stocks():
        #     # Aggregate the total quantity traded for each stock
        #     traded_stocks = Trade.objects.filter(status='completed').values('holding__stock__symbol').annotate(total_quantity=Sum('quantity'))
        #     # print(traded_stocks)
            
        #     traded_stocks_tuples = [(entry['holding__stock__symbol'], entry['total_quantity']) for entry in traded_stocks]
            
        #     most_traded_stocks = sorted(traded_stocks_tuples, key=lambda x: x[1], reverse=True)[:10]
        #     # print(most_traded_stocks)
            
        #     with ThreadPoolExecutor() as executor:
        #         futures = [executor.submit(symbol_details, stock_symbol) for stock_symbol, total_quantity in most_traded_stocks]
        #         top_10_symbols = [future.result() for future in futures]
        #     # top_10_symbols = [symbol_details(stock_symbol) for stock_symbol, total_quantity in most_traded_stocks]

        #     return top_10_symbols
        
        # top_most_traded_stock_symbols = most_traded_stocks()
        # # print(top_most_traded_stock_symbols)
        
        positions_closed = positions.filter(status='close')
        top_10 = positions_closed.order_by("-profit_loss")[:10]
        top_performing = [
            {   'user':position.portfolio.user.fullname,
                'profit':position.profit_loss,
                'symbol':position.stock.symbol,
                }
            for position in top_10
        ]
        
        # def top_performing_stocks():
        #     # Get all holdings
        #     all_holdings = Holding.objects.all()
        #     def hold_details(holding):
        #         return holding.stock.symbol, holding.pnl, holding.portfolio.user.fullname
            
        #     with ThreadPoolExecutor() as executor:
        #         futures = [executor.submit(hold_details, holding) for holding in all_holdings]
        #         performance_data = [future.result() for future in futures]

        #     # Calculate profit/loss for each holding
        #     # performance_data = [(holding.stock.symbol, holding.pnl, holding.portfolio.user.fullname) for holding in all_holdings]

        #     # Sort holdings based on profit/loss in descending order
        #     sorted_performance = sorted(performance_data, key=lambda x: x[1], reverse=True)

        #     # Extract the top-performing stocks
        #     top_performing_stocks = [{
        #         "symbol": symbol,
        #         "pnl": pnl,
        #         "user":user
        #     }
        #         for symbol,pnl,user in sorted_performance[:10]]

        #     return top_performing_stocks
        # top_performing_stock=top_performing_stocks()
        
        most_traded_stock = Stock.objects.annotate(num_positions=Count('demopositions2')).filter(num_positions__gt=0).order_by('-num_positions')
        # print(most_traded_stock)
        
        def get_stock(stock):
            data=get_price(stock.symbol)
            if data:
                price= data.get('current_price')
                change = data.get('percentage_change',0)
                unique_users_count = positions.filter(stock=stock).values('portfolio__user').distinct().count()
                
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
            'average_daily_active_users': int(average_daily_users),
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
    
class FlagWithdrawalRequest(APIView):
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  
    def post(self, request,*args, **kwargs):
        withdrawal_request_id= kwargs.get("withdrawal_request_id")
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

from django.utils import timezone
from django.db.models import Count, DateTimeField, DateField, CharField
from django.db.models.functions import Trunc,ExtractWeekDay,ExtractWeek, TruncDate

class AnalyticsGraphView(APIView):
    def get(self, request):
        users = User.objects.all()
        # For the last 1 week in daily points
        last_week_data = users.filter(date_joined__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('date_joined', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 month in daily points
        last_month_data = users.filter(date_joined__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('date_joined', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data = users.filter(date_joined__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('date_joined', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 year in monthly points
        last_year_data = users.filter(date_joined__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('date_joined', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Total registered users in monthly points
        total_users_data = users.annotate(
            date=Trunc('date_joined', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Format the data as per your requirement
        registered_data = {
            'last_week_data': list(last_week_data),
            'last_month_data': list(last_month_data),
            'last_3_months_data': list(last_3_months_data),
            'last_year_data': list(last_year_data),
            'total_users_data': list(total_users_data),
        }
        
        # For the last 1 week in daily points
        transactions = models.DemoTransaction.objects.all()
        last_week_data = transactions.filter(date__gte=timezone.now() - timedelta(days=7)).annotate(
            transaction_date=Trunc('date', 'day', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 1 month in daily points
        last_month_data = transactions.filter(date__gte=timezone.now() - timedelta(days=30)).annotate(
            transaction_date=Trunc('date', 'day', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 3 months in weekly points
        last_3_months_data = transactions.filter(date__gte=timezone.now() - timedelta(days=90)).annotate(
            transaction_date=Trunc('date', 'week', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # For the last 1 year in monthly points
        last_year_data = transactions.filter(date__gte=timezone.now() - timedelta(days=365)).annotate(
            transaction_date=Trunc('date', 'month', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # Total transactions in monthly points
        total_transactions_data = transactions.annotate(
            transaction_date=Trunc('date', 'month', output_field=DateField())
        ).values('transaction_date').annotate(count=Count('id')).order_by('transaction_date')

        # Format the data as per your requirement
        transaction_data = {
            'last_week_data': list(last_week_data),
            'last_month_data': list(last_month_data),
            'last_3_months_data': list(last_3_months_data),
            'last_year_data': list(last_year_data),
            'total_transactions_data': list(total_transactions_data),
        }

        # For the last 1 week in daily points
        useractivity = UserActivityLog.objects.all()
        last_week_data = useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('timestamp', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # For the last 1 month in daily points
        last_month_data = useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('timestamp', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data =useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('timestamp', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # For the last 1 year in monthly points
        last_year_data = useractivity.filter(timestamp__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('timestamp', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # Total active users in monthly points
        total_active_users_data = useractivity.annotate(
            date=Trunc('timestamp', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('user', distinct=True)).order_by('date')

        # Format the data as per your requirement
        user_activity_data = {
            'last_week_data': list(last_week_data),
            'last_month_data': list(last_month_data),
            'last_3_months_data': list(last_3_months_data),
            'last_year_data': list(last_year_data),
            'total_active_users_data': list(total_active_users_data),
        }

        positions =exec_models.DemoPosition.objects.all()
        
        # For the last 1 week in daily points
        last_week_data = positions.filter(created__gte=timezone.now() - timedelta(days=7)).annotate(
            date=Trunc('created', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 month in daily points
        last_month_data = positions.filter(created__gte=timezone.now() - timedelta(days=30)).annotate(
            date=Trunc('created', 'day', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 3 months in weekly points
        last_3_months_data = positions.filter(created__gte=timezone.now() - timedelta(days=90)).annotate(
            date=Trunc('created', 'week', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # For the last 1 year in monthly points
        last_year_data = positions.filter(created__gte=timezone.now() - timedelta(days=365)).annotate(
            date=Trunc('created', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Total positions created in monthly points
        total_positions_data = positions.annotate(
            date=Trunc('created', 'month', output_field=DateField())
        ).values('date').annotate(count=Count('id')).order_by('date')

        # Format the data as per your requirement
        positions_data = {
            'last_week_data': list(last_week_data),
            'last_month_data': list(last_month_data),
            'last_3_months_data': list(last_3_months_data),
            'last_year_data': list(last_year_data),
            'total_positions_data': list(total_positions_data),
        }

        positions = exec_models.DemoPosition.objects.all()

        result = (
            positions.annotate(
                truncated_created=TruncDate('created'),
                stock_symbol=F('stock__symbol')  # Replace 'symbol' with the actual field name in Stock model
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
                'volume': volume
            }

            volume_data[stock_symbol].append(data)

        
        grouped_data = {
            'registered_users':registered_data,
            'transaction_data':transaction_data,
            "user_activity_data":user_activity_data,
            "positions_data":positions_data,
            "volume_data":volume_data
        }
        
        
        
        
        return Response(grouped_data)


class AllAdminUsersActivityLogView(APIView):
    serializer_class=acc_serializers.AdminUserActivityLogSerializer
    permission_classes=[permissions.IsAdminUser, permissions.IsAuthenticated]  

    def get(self,request):
        filter=request.GET.get("filter")
        if filter:
            activities=AdminUserActivityLog.objects.filter(action_type__icontains=filter)

        else:
            activities=AdminUserActivityLog.objects.all()
        serializer=self.serializer_class(activities, many=True)
        return Response(serializer.data)
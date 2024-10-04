
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from random import randint

import pytz
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import close_old_connections
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.shortcuts import get_list_or_404, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django_celery_beat.models import (CrontabSchedule, IntervalSchedule,
                                       PeriodicTask)
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import (AllowAny, BasePermission,
                                        IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Referral, UserActivityLog
from affilate.models import ReferralWallet, RewardActivities
from competition.managers.utils import sendMail
from competition.tasks import create_crontab
from execution import models as exec_models
from lock.models import Saving
from notifications.utils import save_and_send_notification

from .models import (Alert, AlertAI, AlertAITracker, ButtonClick, Conversation,
                     DashboardFeed, FeedReaction, FeedsCategory, Message,
                     PayStackReceipts, Receipts, Stock, StockWatchlist,
                     Transaction, UserSubscribedCategory, Wallet,
                     WithdrawalOTPRequest)
from .serializers import (AlertSerializer, ButtonClickSerializer,
                          ConversationSerializer, DashboardFeedSerializer,
                          FeedReactionSerializer, FeedsCategorySerializer,
                          PayStackReceipts, PayStackReceiptsSerializer,
                          ReceiptsViewSerializer, StockSerializer,
                          TransactionSerializer)
from .utils import (get_details3, get_historical_data, get_mini_data,get_symbol_overview,
                    get_price, get_symbol_data)
from .utils import client

User= get_user_model()


db_details = client["ngxlistedcompanies"]

class IsStaffOrAnalyst(BasePermission):
    def has_permission(self, request, view):
        return request.user and (request.user.is_staff or request.user.is_analyst)

class IsStaffOrAnalystOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_analyst)

 
class WalletBalance(APIView):

    def get(self, request):
        portfolios = exec_models.Portfolio.objects.filter(user=request.user)
        wallet = Wallet.objects.get_or_create(user=request.user)[0]
        transactions = Transaction.objects.filter(user=request.user)
        
        positions_sum = 0
        for portfolio in portfolios:
            positions= portfolio.positions2.filter(status='open')
            sum1 = sum([post.amount_invested for post in positions])
            positions_sum += (sum1 + portfolio.balance)
            
        savings = Saving.objects.filter(user=request.user,status='ongoing')
        
        deposited = sum([trans.amount for trans in transactions if trans.transaction_type == "deposit"]) - sum([trans.amount for trans in transactions if trans.transaction_type == "withdrawal"])
        invested= positions_sum + sum([lock.amount for lock in savings])
        balance = wallet.balance
        uninvested = deposited - invested
        
        data = {
            "deposited":deposited,
            "invested":invested,
            # "uninvested":uninvested ,
            "uninvested":balance ,
            "balance":balance,
            "reserve": balance,
            # "reserve": uninvested + balance
            
        }
        
        return Response(data)

class SupportWalletBalance(APIView):
    

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        portfolios = exec_models.Portfolio.objects.filter(user=user)
        wallet = Wallet.objects.get_or_create(user=user)[0]
        transactions = Transaction.objects.filter(user=user)

        positions_sum = 0
        for portfolio in portfolios:
            positions= portfolio.positions2.filter(status='open')
            sum1 = sum([post.amount_invested for post in positions])
            positions_sum += (sum1 + portfolio.balance)
            
        savings = Saving.objects.filter(user=user,status='ongoing')
        
        deposited = sum([trans.amount for trans in transactions if trans.transaction_type == "deposit"]) - sum([trans.amount for trans in transactions if trans.transaction_type == "withdrawal"])
        invested= positions_sum + sum([lock.amount for lock in savings])
        
        balance = wallet.balance
        uninvested = deposited - invested
        
        data = {
            "deposited":deposited,
            "invested":invested,
            # "uninvested":uninvested ,
            "uninvested":balance ,
            "balance":balance,
            "reserve": balance,
            # "reserve": uninvested + balance
            
        }
        
        return Response(data)

class WalletWithdraw(APIView):
    from decimal import Decimal
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        stage = request.data.get('stage')
        device_type=request.data.get("device_type",None)
        
        amount = request.data.get('amount')
        portfolio = exec_models.Portfolio.objects.get_or_create(user=request.user)[0]
        wallet = Wallet.objects.get(user=request.user)
        positions= portfolio.positions2.all()
        
        # deposited = sum([trans.amount for trans in transactions])
        # invested= sum([post.amount_invested for post in positions])
        balance = wallet.balance
        # uninvested = deposited - invested

        # balance1 = uninvested + balance
        balance1 = balance
        
        if not amount or not stage:
            return Response("amount and stage must be sent")
        if int(stage) > 2:
            return Response("stage must be 1 or 2")
        
        if stage == '1':
            
            if balance1 >= Decimal(amount):
                # Stage 1: Generate OTP and send to user
                otp = self.generate_otp()
                otp_request =WithdrawalOTPRequest.objects.create(user=request.user, otp=otp,
                                                        expiration_time=timezone.now() + timezone.timedelta(minutes=10))

                # Send OTP to the user
                self.send_otp(user=request.user, otp=otp)

                return Response({"detail": "OTP has been sent to your email for verification.",
                                    "otp_request_id": otp_request.id},
                                status=status.HTTP_200_OK)
            else:
                # Handle insufficient funds error
                raise serializers.ValidationError("Insufficient funds in the wallet.")

        elif request.data['stage'] == '2':
            # Stage 2: Verify OTP and create withdrawal request
            otp_request_id = request.data.get('otp_request_id')
            provided_token = request.data.get('otp_token', '')
            amount = request.data.get('amount')

            otp_request = self.get_valid_otp_request(otp_request_id)                

            if otp_request and self.verify_otp(otp_request, provided_token):
                # Proceed with withdrawal request creation
                exec_models.WithdrawalRequest.objects.create(user=request.user, amount=amount)
                otp_request.used = True
                otp_request.save()
                save_and_send_notification(request.user.id, 'Your withdrawal is processing.')
                UserActivityLog.objects.create(user=request.user, action_type="withdrawal_request_initaiated",description="User requested for a withdrawal",device_type=device_type)
                Transaction.objects.create(user=request.user,transaction_type="initiate_wallet_withdrawal", amount=amount, status='completed')
                mail=sendMail("general/WIthdrawalRequesReceived.html","Withdrawal Request Received",[request.user.email],{"first_name":request.user.firstname,"amount":amount})
                
                return Response({"detail": "Withdrawal request has been created successfully."},
                                status=status.HTTP_200_OK)
            else:
                # Handle invalid OTP or expired OTP request
                raise serializers.ValidationError("Invalid or expired OTP. Please try again.")

        else:
            # Handle insufficient funds error
            raise serializers.ValidationError("Insufficient funds in the wallet.")

    def generate_otp(self):
        # Generate a 6-digit OTP
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    # def send_otp(self, user, otp):
    #     # Send OTP via email (you can add SMS or other methods here)
    #     send_mail(
    #         'Withdrawal OTP',
    #         f'Your withdrawal OTP is: {otp}',
    #         'teamft9ja@gmail.com',
    #         [user.email],
    #         fail_silently=False,
    #     )
    def send_otp(self, user, otp):
        # Send token to users email
        context={
            "firstname":user.firstname.title(),
            'token':otp
        }
        html_message = render_to_string('portfolio/token.html', context)
        plain_message = ""
        subject = 'Gohamma Withdrawal OTP'
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
        
    def get_valid_otp_request(self, otp_request_id):
        try:
            otp_request = WithdrawalOTPRequest.objects.get(id=otp_request_id, user=self.request.user, used=False,
                                                 expiration_time__gte=timezone.now())
            return otp_request
        except WithdrawalOTPRequest.DoesNotExist:
            return None

    def verify_otp(self, otp_request, provided_token):
        # Verify OTP token
        
        return otp_request.otp == int(provided_token)
    
class ResendWithdrawalOtp(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):

        otp_instance= self.get_valid_otp(request.user)
        
        # Send OTP to the user
        self.send_otp(user=request.user, otp=otp_instance.otp)

        return Response({"detail": "OTP has been sent to your email for verification.",
                            "otp_request_id": otp_instance.id},
                        status=status.HTTP_200_OK)
    
    def generate_otp(self):
        # Generate a 6-digit OTP
        return "".join([str(random.randint(0, 9)) for _ in range(6)])

    def send_otp(self, user, otp):
        # Send token to users email
        context = {"firstname": user.firstname.title(), "token": otp}
        html_message = render_to_string("portfolio/token.html", context)
        plain_message = ""
        subject = "Gohamma Withdrawal OTP"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )

    def get_valid_otp(self, user):

        otp_request = WithdrawalOTPRequest.objects.filter(
            user=self.request.user,
            used=False,
            expiration_time__gte=timezone.now(),
        ).first()
        if not otp_request:
            otp = self.generate_otp()
            otp_request =WithdrawalOTPRequest.objects.create(user=user, otp=otp,
                                                expiration_time=timezone.now() + timezone.timedelta(minutes=10))
        return otp_request


            
# class StockList(generics.ListAPIView):
#     queryset = Stock.objects.filter(active=True). order_by('symbol')
#     permission_classes =[AllowAny,]
    
#     def get(self, request, *args, **kwargs):
        
#         queryset = self.get_queryset()
#         first = queryset.first()
        
#         details = get_details3(queryset)
#         watchlist = [ watch.stock.symbol for watch in StockWatchlist.objects.filter(user=request.user)]
#         for detail in details:
#             if detail['symbol'] in watchlist:
#                 detail['in_watchlist'] = True
#             else:
#                 detail['in_watchlist'] = False
            
        
#         response_data = {
#             'stock_list': details,
#             'first_symbol_order_book': [],
#         }
#         return Response(response_data)
    
class StockList(generics.ListAPIView):
    queryset = Stock.objects.filter(active=True).order_by('symbol')
    permission_classes = [AllowAny,]

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Fetch stock details
        details = get_details3(queryset)

        # Initialize empty watchlist
        watchlist = []

        # Check if the user is authenticated
        if request.user.is_authenticated:
            # Get the watchlist for the logged-in user
            watchlist = [watch.stock.symbol for watch in StockWatchlist.objects.filter(user=request.user)]

        # Add 'in_watchlist' flag to stock details
        for detail in details:
            detail['in_watchlist'] = detail['symbol'] in watchlist

        response_data = {
            'stock_list': details,
            'first_symbol_order_book': [],
        }

        return Response(response_data)


class MiniData(APIView):
    def get(self, request):
        data = get_mini_data()
        return Response(data)
    
class GetSingleStock(APIView):
    serializer_class = StockSerializer
    permission_classes =[AllowAny,]
    
    def get(self, request, *args, **kwargs):
        symbol = self.kwargs.get('symbol')
        queryset = get_object_or_404(Stock, symbol=symbol)
        
        details = get_details3([queryset])
        overview = get_symbol_overview(symbol)
        
        response_data = {
            'stock_detail': details,
            'order_book': [],
            'overview': overview,
            # 'historical_data':historical_data
        }
        return Response(response_data)

class StockDetail(generics.RetrieveAPIView):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


def get_holding_detail(holding, trades):
    from .utils import get_price
    stock= holding.stock.symbol
    data=get_price(stock)
    id = holding.id
    quantity=holding.quantity
    created = holding.created
    updated = holding.updated
    filled = trades.filter(status='completed').aggregate(total_quantity=Sum('quantity'))['total_quantity'] if trades else 0
    incomplete_ = trades.filter(status='pending')
    
    if not filled :
        filled = 0
    
    if incomplete_:
        incomplete1 = incomplete_.aggregate(total_quantity=Sum('quantity'))['total_quantity']
        if incomplete1:
            incomplete = incomplete1
        else:
            incomplete = 0
    else:
        incomplete = 0
        
    shares= filled + incomplete
    avg_cost = holding.avg_cost() 
    ltp =  Decimal(data['current_price'])
    cur_val = round((ltp * quantity),2)
    pnl = round((ltp - avg_cost) * filled, 2) if avg_cost else 0
    change = round(ltp- avg_cost ,2) if avg_cost else 0
    percent_change = round((change/avg_cost) * 100,2) if avg_cost else 0
    avg_volume_3_months =60000
    volume = 9000000
    return {
            'id':id,
            'stock':stock,
            'quantity':quantity,
            'created':created,
            'updated':updated,
            'filled':filled,
            'incomplete':incomplete,
            'shares':shares,
            'avg_cost':avg_cost,
            'ltp':ltp,
            'cur_val':cur_val,
            'pnl':pnl,
            'change':change,
            'percent_change':percent_change,
            'avg_volume_3_months':avg_volume_3_months,
            'volume':volume,}

def get_portfolio_data(holdings_data):
    cur_vals = [holding['cur_val'] for holding in holdings_data]
    avg_costs = [holding['avg_cost'] * holding['filled'] for holding in holdings_data]
    pls = [(holding['ltp'] - holding['avg_cost']) * holding['filled'] for holding in holdings_data]
    
    portfolio_value = sum(cur_vals)
    total_invested = sum(avg_costs)
    profit_loss = sum(pls)
    return {
        'portfolio_value':round(portfolio_value,2),
        'total_invested':round(total_invested,2),
        'profit_loss': round(profit_loss,2)
    }

def get_amount_invested(transaction):
    """_summary_

    THe total amount in depoisted which has occured in the user's trnscations, us sumed and retured

    Args:
        trasaction (array): the transcation objects related to the users.
        
    """
    total=sum([trans.amount for trans in transaction])
    return total

def get_holding_details_concurrently(holding):
    try:
        trades = holding.trades.all()
        return get_holding_detail(holding, trades)
    finally:
        # Close the old database connections to avoid connection exhaustion
        close_old_connections()
        
def get_demo_holding_details_concurrently(holding):
    try:
        trades = holding.demotrades.all()
        return get_holding_detail(holding, trades)
    finally:
        # Close the old database connections to avoid connection exhaustion
        close_old_connections()
  
        
class ReceiptsView(APIView):
    serializer_class = ReceiptsViewSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializers = ReceiptsViewSerializer(data=request.data)
        device_type=request.data.get("device_type",None)
        if serializers.is_valid():
            image = serializers.validated_data["image"]
            print(image,"sadbscv")
            receipt=Receipts.objects.create(user=request.user, image=image)
            # sendreciptsmail(request,receipt)
            # sendreciptsmail(request,image)
            save_and_send_notification(request.user.id, "Receipt Upload Successful.")
            activity=UserActivityLog.objects.create(user=request.user, action_type="receipt",description="User uploaded a payment receipt.",device_type=device_type)
            mail=sendMail("general/depositRecieptRecieved.html","Deposit Receipt Reviewed",[request.user.email],{"first_name":request.user.firstname})
            return Response({"message": "File uploaded successfully"})
        return Response(serializers.errors)
    
@api_view(['POST',])
def PayStackReceiptsView(request):
    amount=request.data.get("amount")
    device_type=request.data.get("device_type",None)
    paystack_recipt=PayStackReceipts.objects.create(
        user = request.user,
        reference=request.data.get("reference"),
        transaction=request.data.get("transaction"),
        amount=amount,
        receipt_status = 'confirmed'

    )
    
    wallet= exec_models.Portfolio.objects.get(user=request.user)
    wallet.balance += Decimal(amount)
    wallet.save()
    
    save_and_send_notification(wallet.user.id, f"{amount} credited to your wallet.")
            
    
    refer_object=Referral.objects.filter(person_referred=wallet.user).first()
    
    if refer_object and refer_object.converted == False:
        sum_user_trans=sum(trans.amount for trans in Transaction.objects.filter(user=wallet.user, transaction_type = 'deposit'))
        if sum_user_trans >= 50000 :
            referal_wallet = ReferralWallet.objects.get_or_create(user=refer_object.user)[0]
            referal_wallet.balance += Decimal(5000)
            referal_wallet.save()
            
            refer_object.converted == True
            refer_object.save()
            
            
            RewardActivities.objects.create(trader=wallet.user, amount=5000, reward_type="Deposit Referral Commission", user=refer_object.user)
                    
    
    Transaction.objects.create(user=request.user, amount=Decimal(amount),transaction_type='deposit', status='completed',channel='paystack')
    activity=UserActivityLog.objects.create(user=request.user, action_type="paystack",description="User made a payment via paystack",device_type=device_type)
    serializer=PayStackReceiptsSerializer(paystack_recipt, many=False)
    return Response({"detail":serializer.data}, status=status.HTTP_201_CREATED)

class TransactionList(generics.ListAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only retrieve transactions for the logged-in user
        return Transaction.objects.filter(user=self.request.user)

class SupportTransactionList(APIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        transactions = Transaction.objects.filter(user=user)
        serializer=TransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    


class Symbols(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        stocks = Stock.objects.filter(active=True)
        symbols = [{stock.symbol:stock.id} for stock in stocks]
        return Response(symbols)

class AlertView(APIView):
    serializer_class= AlertSerializer


    def get(self, request):
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_end = current_month_start.replace(month=current_month_start.month + 1) - timezone.timedelta(seconds=1)

        alerts_query = Alert.objects.filter(
            created__range=(current_month_start, current_month_end), user=request.user, trigerred = False
        )
        conversation_query = Conversation.objects.annotate(
            has_messages=Exists(Message.objects.filter(room=OuterRef('pk')))
        ).filter(user=request.user, has_messages=True)
                
        alerts =   [  {
            "id":alert.id,
            "stock": alert.stock.symbol,
            "stock_id": alert.stock.id,
            "alert_name": alert.alert_name,
            "description": alert.description,
            "alert_type": alert.alert_type,
            "action": alert.action,
            "to_price": alert.to_price,
            "to_volume": alert.to_volume,
            "frequency": alert.frequency,
            "expire": alert.created,
            "trigerred": alert.trigerred
        } for alert in alerts_query]
        
        conversations = [{
            'conversation_id': conver.name,
            'created':conver.created
        } for conver in conversation_query]
        data = {
            'alerts': alerts,
            'conversations': conversations
        }
        return Response(data)
    
    def post(self, request):
        device_type=request.data.get("device_type",None)
        types= ['price', 'volume']
        # counter = AlertAITracker.objects.get_or_create(user=request.user)[0]
        current_date = timezone.now()
        start_of_month = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Filter condition for the current month
        filter_condition = {
            'user': request.user,
            'created__month': start_of_month.month,
            'created__year': start_of_month.year,
        }

        # Get or create AlertAITracker instance
        counter, created = AlertAITracker.objects.get_or_create(**filter_condition, defaults={'count': 0})


        if counter.count >= 10:
            return Response({"detail": "You have reached the maximum limit of 10 alerts for this month."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            # ensure below < above for price and volume
            if serializer.validated_data["alert_type"] not in types:
                return Response({"detail": "alert type must be 'price' or 'volume' "}, status=status.HTTP_400_BAD_REQUEST)
            
            price = serializer.validated_data["to_price"] if serializer.validated_data["alert_type"] == "price" else None
            symbol2 = serializer.validated_data["stock"].symbol
            # print(type(symbol2))
            current_price = get_price(symbol2)['current_price']
            if price:
                if price <= 0:
                    return Response({"detail": "Price must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)
                if serializer.validated_data["action"] == "below" and price > current_price:
                    serializer.validated_data['frequency'] = 'Once'  
                elif serializer.validated_data["action"] == "above" and price <= current_price:
                    serializer.validated_data['frequency'] = 'Once'
            stock = get_object_or_404(Stock, symbol =serializer.validated_data["stock"])
            # print(type(stock))
            name = serializer.validated_data["alert_name"]
            task_name=serializer.validated_data["alert_name"]  + str(randint(10, 9999999))
            serializer.save(user=request.user,stock=stock, alert_name=name, task_name=task_name)
            
            counter.count += 1
            counter.save()
            activity=UserActivityLog.objects.create(user=request.user, action_type="alert",description="User created an alert.",device_type=device_type)

            return Response(serializer.data, status.HTTP_201_CREATED)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

class SupportAlertView(APIView):
    serializer_class= AlertSerializer


    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_end = current_month_start.replace(month=current_month_start.month + 1) - timezone.timedelta(seconds=1)

        alerts_query = Alert.objects.filter(
            created__range=(current_month_start, current_month_end), user=user, trigerred = False
        )
        conversation_query = Conversation.objects.annotate(
            has_messages=Exists(Message.objects.filter(room=OuterRef('pk')))
        ).filter(user=user, has_messages=True)
                
        alerts =   [  {
            "id":alert.id,
            "stock": alert.stock.symbol,
            "stock_id": alert.stock.id,
            "alert_name": alert.alert_name,
            "description": alert.description,
            "alert_type": alert.alert_type,
            "action": alert.action,
            "to_price": alert.to_price,
            "to_volume": alert.to_volume,
            "frequency": alert.frequency,
            "expire": alert.created,
            "trigerred": alert.trigerred
        } for alert in alerts_query]
        
        conversations = [{
            'conversation_id': conver.name,
            'created':conver.created
        } for conver in conversation_query]
        data = {
            'alerts': alerts,
            'conversations': conversations
        }
        return Response(data)


  
class AlertUpdateView(APIView):
    serializer_class = AlertSerializer

    def get_queryset(self, id, user):
        alert = Alert.objects.filter(id=id, user=user).first()
        return alert

    def get(self, request, *args, **kwargs):
        id = kwargs.get("id")
        alert = self.get_queryset(id, request.user)
        if alert is not None:
            serializer = AlertSerializer(alert, many=False)
            return Response(serializer.data)
        return Response({"detail": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, *args, **kwargs):
        id = kwargs.get("id")
        alert = self.get_queryset(id, request.user)
        action= ['price', 'volume']
        # print(alert.alert_name)
        if alert is not None:
            serializer = self.serializer_class(alert, data=request.data)
            # print(serializer)
            if serializer.is_valid():
                # ensure below < above for price and volume
                if serializer.validated_data["alert_type"] not in action:
                    return Response({"detail": "alert type must be 'price' or 'volume' "}, status=status.HTTP_400_BAD_REQUEST)
                
                serializer.save()
                
                alert.trigerred = False
                alert.save()
                
                task=PeriodicTask.objects.get(name=alert.task_name)
                task.enabled=True
                task.save()
                
                save_and_send_notification(request.user.id, f"Alert {alert.alert_name} has been updated.")
                
                return Response(serializer.data)
            return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
        
    def delete(self, request, *args, **kwargs):
        id = kwargs.get("id")
        alert = self.get_queryset(id, request.user)
        
        if alert is not None:
            alert_name = alert.alert_name   
            
            task=PeriodicTask.objects.get(name=alert.task_name)
            task.delete()
            
            alert.delete()
            save_and_send_notification(request.user.id, f"Alert {alert_name} has been deleted.")
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
        

class ConversationsView(APIView):
    serializer_class = ConversationSerializer
    
    def get(self, request):
        conversations = Conversation.objects.filter(user= request.user)
        serializer = AlertSerializer(conversations, many=True)
        return Response(serializer.data)

# class GetWalletSummary(APIView):
#     def get(self, request):

#         portfolio = Portfolio.objects.get(user=request.user)
#         holdings = portfolio.holdings.all()

#         # Use ThreadPoolExecutor to execute get_holding_detail concurrently.
#         with ThreadPoolExecutor() as executor:
#             # Map the holdings to the executor, it will return a generator.
#             futures = [executor.submit(get_holding_details_concurrently, holding) for holding in holdings]
#             holdings_data = [future.result() for future in futures]

#         portfolio_data = get_portfolio_data(holdings_data)

#         user_trans= Transaction.object.filter(user=request.user, transaction_type="deposit")
#         user_wallet= Wallet.object.filter(user=request.user).first()

#         amount_depoisted=get_amount_invested(user_trans)
#         amount_invested= amount_depoisted - user_wallet.balance
#         uninvested=user_wallet.balance
#         balance=portfolio_data.portfolio_value
#         reserved= balance + uninvested

#         summary={
#             "amount_depoisted":amount_depoisted,
#             "amount_invested":amount_invested,
#             "uninvested":uninvested,
#             "balance":balance,
#             "reserved":reserved
#         }
#         return Response(summary)



class FundLiveAccount(APIView):
    
    def post(self,request):
        account_id = request.data.get('account_id')
        amount = request.data.get('amount')
        device_type=request.data.get("device_type",None)
        portfolio = exec_models.Portfolio.objects.filter(id=account_id).first()
        
        wallet = Wallet.objects.get(user=request.user)
        
        if Decimal(amount) > wallet.balance:
            return Response({'error': 'Insufficient funds'}, status=status.HTTP_400_BAD_REQUEST)
        
        wallet.balance -= Decimal(amount) 
        wallet.save()
        
        portfolio.balance += Decimal(amount)
        portfolio.save()
        
        save_and_send_notification(request.user.id, f'You transferred {amount} to {portfolio.account_name} trading account.')
        UserActivityLog.objects.create(user=request.user, action_type="fund_live_account",description=f"User funded {portfolio.account_name} with {amount}.",device_type=device_type)
        Transaction.objects.create(user=request.user,transaction_type=f"funded Live Account {portfolio.account_name}", amount=amount, status='completed')
        return Response({'success': 'Funds successfully transferred'}, status=status.HTTP_200_OK)
    
class WithdrawLiveAccount(APIView):

    def post(self, request):
        device_type=request.data.get("device_type",None)
        account_id = request.data.get('account_id')
        amount = request.data.get('amount')
        portfolio = exec_models.Portfolio.objects.filter(id=account_id).first()

        wallet = Wallet.objects.get(user=request.user)

        if Decimal(amount) > portfolio.balance:
            return Response({'error': 'Insufficient funds'}, status=status.HTTP_400_BAD_REQUEST)

        portfolio.balance -= Decimal(amount)
        portfolio.save()

        wallet.balance += Decimal(amount)
        wallet.save()
        
        save_and_send_notification(request.user.id, f'You withdrew {amount} from {portfolio.account_name} to wallet.')
        UserActivityLog.objects.create(user=request.user, action_type="withdraw_live_account",description=f"User withdrew {amount} from  {portfolio.account_name} trading account .",device_type=device_type)
        Transaction.objects.create(user=request.user,transaction_type=f"withdrew from  Live Account {portfolio.account_name}", amount=amount, status='completed')

        
        return Response({'success': 'Funds successfully transferred'}, status=status.HTTP_200_OK)
    
class ButtonClickCreateView(APIView):
    
    def post(self, request):
        serializer = ButtonClickSerializer(data=request.data)
        device_type=request.data.get("device_type",None)
        if serializer.is_valid():
            ButtonClick.objects.create(
                user=request.user,
                button_name=serializer.validated_data['button_name'],
                page=serializer.validated_data['page'],
                device_type=device_type
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class StockWatchlistAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        seven_days_ago = timezone.now() - timedelta(days=7)

        # Get the feeds that are published within the last 7 days
        published_feeds = DashboardFeed.objects.filter(
            status='published',
            published_date__gte=seven_days_ago
        ).order_by('-created')

        # Get the queryset of stocks related to these feeds
        analyst = Stock.objects.filter(feed__in=published_feeds).distinct()
        analyst_pick = get_details3(analyst)

        response_data = {
            'analyst_pick': analyst_pick
        }

        if request.user.is_authenticated:
            queryset = Stock.objects.filter(watchlisted_by__user=request.user)
            details = get_details3(queryset)
            response_data['watchlist'] = details
        else:
            response_data['watchlist'] = []

        return Response(response_data)
    
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        
        user = request.user
        symbol = request.data.get('symbol')
        
        try:
            stock = Stock.objects.get(symbol=symbol)
        except Stock.DoesNotExist:
            return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)

        watchlist_item, created = StockWatchlist.objects.get_or_create(user=user, stock=stock)

        if created:
            return Response({'message': 'Stock added to watchlist'}, status=status.HTTP_201_CREATED)
        else:
            return Response({'message': 'Stock is already in the watchlist'}, status=status.HTTP_200_OK)

    def delete(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        
        
        user = request.user
        symbol = request.data.get('symbol')

        try:
            stock = Stock.objects.get(symbol=symbol)
        except Stock.DoesNotExist:
            return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            watchlist_item = StockWatchlist.objects.get(user=user, stock=stock)
            watchlist_item.delete()
            return Response({'message': 'Stock removed from watchlist'}, status=status.HTTP_204_NO_CONTENT)
        except StockWatchlist.DoesNotExist:
            return Response({'error': 'Stock is not in the watchlist'}, status=status.HTTP_404_NOT_FOUND)

class SupportStockWatchlistAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request,*args, **kwargs ):
        
        email = kwargs.get('email')
        print(email)
        
        queryset = Stock.objects.filter(watchlisted_by__user__email=email)
        details = get_details3(queryset)

        response_data = {
            'watchlist': details,
            'analyst_pick':[],
        
        }
        return Response(response_data)

class MostTradedStocks(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        most_traded_stock = Stock.objects.annotate(num_positions=Count('demopositions2', filter=Q(demopositions2__status='open')) + Count('composition', filter=Q(composition__status ='open'))).filter(num_positions__gt=1).order_by('-num_positions').order_by('-num_positions')
        most_traded_stock = most_traded_stock[:10]
       
                
        details = get_details3(most_traded_stock)

        response_data = {
            'trending':details,
        
        }
        return Response(response_data)
    
class FeedView(APIView):
    parser_classes =   [MultiPartParser, FormParser]
    permission_classes = [IsStaffOrAnalystOrReadOnly]
    
    def get(self, request):
        feed = DashboardFeed.objects.all().order_by("-created")
        serializer = DashboardFeedSerializer(feed, many=True)
        return Response(serializer.data)
    
    
    def post(self, request):
         
        topic = request.data.get('topic')
        title = request.data.get('title')
        image = request.data.get('image')
        content = request.data.get('content')
        category = request.data.get('category')
        image_caption = request.data.get('image_caption')
        symbol = request.data.get('symbol')
        subtitle = request.data.get('subtitle',None)
        bullet_1 = request.data.get('bullet_1',None)
        bullet_2 = request.data.get('bullet_2',None)
        bullet_3 = request.data.get('bullet_3',None)
        bullet_4 = request.data.get('bullet_4',None)
        bullet_5 = request.data.get('bullet_5',None)
        bullet_6 = request.data.get('bullet_6',None)
        
        stock = Stock.objects.get(symbol=symbol)
        feedcategory = FeedsCategory .objects.get(name=category)
        
        feed = DashboardFeed.objects.create(
            topic=topic,
            title=title,
            image=image,
            content=content,
            category=feedcategory,
            image_caption=image_caption,
            stock=stock,
            subtitle=subtitle,
            user=request.user,
            bullet_1=bullet_1,
            bullet_2=bullet_2,
            bullet_3=bullet_3,
            bullet_4=bullet_4,
            bullet_5=bullet_5,
            bullet_6=bullet_6
        )
        
        serializer = DashboardFeedSerializer (feed)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        

    def put(self, request):
        id = request.data.get('id')
        try:
            feed = DashboardFeed.objects.get(id=id)
        except DashboardFeed.DoesNotExist:
            return Response({"error": "Feed not found"}, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data.copy()
        
        # Retain existing file fields if they are not included in the request data
        if 'image' not in data:
            data['image'] = feed.image
        if 'image_caption' not in data:
            data['image_caption'] = feed.image_caption
        
        stock_symbol = data.get('symbol')
        if stock_symbol:
            try:
                stock = Stock.objects.get(symbol=stock_symbol)
                data['stock'] = stock.id
            except Stock.DoesNotExist:
                return Response({"error": "Stock not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = DashboardFeedSerializer(feed, data=data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
    def delete(self, request):
        id = request.data.get('id')
        feed = DashboardFeed.objects.get(id=id)
        feed.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

    

class PublishFeed(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAnalyst]
    
    def post(self, request):
        id = request.data.get('id')
        feed = DashboardFeed.objects.get(id=id)
        feed.status = 'published'
        feed.published_date = datetime.now()
        feed.save()
        
        lagos_tz = pytz.timezone('Africa/Lagos')
        now_lagos = datetime.now(lagos_tz)
        
        schedule3 = create_crontab(now_lagos + timedelta(hours=1))
        
        PeriodicTask.objects.create(
            name=f"published {now_lagos.strftime('%Y-%m-%d %H:%M')} trading idea",
            task='competition.tasks.trading_ideas_task',
            one_off=True,
            crontab = schedule3,
            args=json.dumps([feed.id])
            
        )
        
        return Response(status=status.HTTP_200_OK)
    
class UnpublishFeed(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAnalyst]
    
    def post(self, request):
        id = request.data.get('id')
        feed = DashboardFeed.objects.get(id=id)
        feed.status = 'unpublished'
        feed.save()
        return Response(status=status.HTTP_200_OK)
        
class FeedCategoryView(APIView):
    def get(self, request):
        category = FeedsCategory.objects.all()
        serializer = FeedsCategorySerializer(category, many=True)
        return Response(serializer.data)


class SubscribeCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        category_name = request.data.get('category')
        category = get_object_or_404(FeedsCategory, name=category_name)
        if request.user.subscribed_categories.filter(category=category).exists():
             return Response("Already Subscribed", status=status.HTTP_204_NO_CONTENT )
        else:
            # Subscribe to category
            UserSubscribedCategory .objects.create(user=request.user, category=category)
            
            return Response({'subscribed': True}, status=status.HTTP_200_OK)
        
class UnsubscribeCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        category_name = request.data.get('category')
        category = get_object_or_404(FeedsCategory, name=category_name)
        
        try:
            subscription = request.user.subscribed_categories.get(category=category)
        except UserSubscribedCategory.DoesNotExist:
            return Response("Not Subscribed to this Category", status=status.HTTP_404_NOT_FOUND)
        
        # Unsubscribe from category
        subscription.delete()
        return Response({'unsubscribed': True}, status=status.HTTP_200_OK)

class UserDashboardFeedsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        seven_days_ago = timezone.now() - timedelta(days=6)
        feeds = DashboardFeed.objects.filter(status='published', published_date__gte=seven_days_ago).order_by('-created')
        serializer = DashboardFeedSerializer(feeds, many=True)
        return Response(serializer.data)


# class DashboardFeedReactionAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, feed_id):
#         # Retrieve the DashboardFeed object
#         feed = get_object_or_404(DashboardFeed, pk=feed_id)
        
#         # Extract reaction data from request
#         # agree = bool(request.data.get('agree', False))
#         # disagree = bool(request.data.get('disagree', False))
#         # like = bool(request.data.get('like', False))
#         # trading = bool(request.data.get('trading', False))
#         # monitoring = bool(request.data.get('monitoring', False))

#         agree = request.data.get('agree', 'false')
#         disagree = request.data.get('agree', 'false')
#         like = request.data.get('agree', 'false')
#         trading = request.data.get('agree', 'false')
#         monitoring = request.data.get('agree', 'false')

#         # Get or create reaction for current user and feed
#         reaction, created = FeedReaction .objects.get_or_create(user=request.user, feed=feed)

#         # Update reaction fields
#         reaction.agree = agree
#         reaction.disagree = disagree
#         reaction.like = like
#         reaction.trading = trading
#         reaction.monitoring = monitoring
#         reaction.save()

#         return Response({'message': 'Reaction updated successfully'}, status=status.HTTP_200_OK)

class DashboardFeedReactionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, feed_id):
        # Retrieve the DashboardFeed object
        feed = get_object_or_404(DashboardFeed, id=feed_id)
        
        # Extract reaction data from request
        agree = request.data.get('agree')
        disagree = request.data.get('disagree')
        like = request.data.get('like')
        trading = request.data.get('trading')
        monitoring = request.data.get('monitoring')

        # Get or create reaction for current user and feed
        reaction, created = FeedReaction.objects.get_or_create(user=request.user, feed=feed)
        print(like)
        
        # Handle voting and unvoting
        if agree is not None:
            if agree == 'true':
                reaction.agree = True
                reaction.disagree = False
                reaction.like = False
                reaction.trading = False
                reaction.monitoring = False
            elif agree == 'false':
                reaction.agree = False

        if disagree is not None:
            if disagree == 'true':
                reaction.agree = False
                reaction.disagree = True
                reaction.like = False
                reaction.trading = False
                reaction.monitoring = False
            elif disagree == 'false':
                reaction.disagree = False

        if like is not None:
            if like == 'true':
                reaction.agree = False
                reaction.disagree = False
                reaction.like = True
                reaction.trading = False
                reaction.monitoring = False
            elif like == 'false':
                reaction.like = False

        if trading is not None:
            if trading == 'true':
                reaction.agree = False
                reaction.disagree = False
                reaction.like = False
                reaction.trading = True
                reaction.monitoring = False
            elif trading == 'false':
                reaction.trading = False

        if monitoring is not None:
            if monitoring == 'true':
                reaction.agree = False
                reaction.disagree = False
                reaction.like = False
                reaction.trading = False
                reaction.monitoring = True
            elif monitoring == 'false':
                reaction.monitoring = False

        # Save the updated reaction
        reaction.save()
        print(reaction.like)

        return Response({'message': 'Reaction updated successfully'}, status=status.HTTP_200_OK)

class CheckReaction(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, feed_id):
        # feed_id = request.data.get('feed_id')
        feed = get_object_or_404(DashboardFeed, id=feed_id)
        reaction = FeedReaction.objects.get_or_create(user=request.user, feed=feed)[0]
        print(reaction)
        if reaction:
            serializer = FeedReactionSerializer(reaction)
            return Response(serializer.data)
        else:
            return Response({'message': 'Reaction not found'}, status=status.HTTP_404_NOT_FOUND)


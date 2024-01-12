from urllib import request
import portfolio
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import (Wallet, Stock, Portfolio, Holding, Receipts, PayStackReceipts, WithdrawalRequest, Alert,Trade,
                     Transaction, WithdrawalOTPRequest, AlertAI, AlertAITracker, DemoPortfolio, Conversation, Message)
from .serializers import (StockSerializer,ReceiptsViewSerializer, PayStackReceipts, PayStackReceiptsSerializer,
                          AlertSerializer,TradeSerializer,   TransactionSerializer, ConversationSerializer)
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
import random
from django.core.mail import send_mail
from django.utils import timezone
from .utils import get_symbol_data,get_historical_data, get_mini_data, get_details3
from notifications.utils import save_and_send_notification
from django.shortcuts import get_object_or_404
from decimal import Decimal
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from lock.models import SavingsLock
from django.db.models import Sum
from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from random import randint
from django.db.models import Exists, OuterRef

 
User= get_user_model()

class WalletBalance(APIView):
    def get(self, request):
        wallet = Wallet.objects.get(user=request.user)
        savings = SavingsLock.objects.filter(user=request.user, status='ongoing')
        if savings:
            savings_amount= savings.aggregate(total_quantity=Sum('amount'))['total_quantity'] 
        else:
            savings_amount= Decimal(0)
        data = {
                'balance': wallet.balance,
                'reserved':savings_amount,
                'total':wallet.balance + savings_amount
            }
        return Response(data)


class WalletWithdraw(APIView):
    from decimal import Decimal
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        stage = request.data.get('stage')
        
        amount = request.data.get('amount')
        wallet = Wallet.objects.get(user=request.user)

        if not amount or not stage:
            return Response("amount and stage must be sent")
        if int(stage) > 2:
            return Response("stage must be 1 or 2")
        
        if stage == '1':
            
            if wallet.balance >= Decimal(amount):
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
                WithdrawalRequest.objects.create(wallet=wallet, amount=amount)
                otp_request.used = True
                otp_request.save()
                save_and_send_notification(request.user.id, 'Your withdrawal is processing.')
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
        return ''.join([str(random.randint(0, 9)) for _ in range(8)])

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
        plain_message = strip_tags(html_message)
        subject = 'Gohamma Withdrawal OTP'
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
        
    def get_valid_otp_request(self, otp_request_id):
        try:
            otp_request =WithdrawalOTPRequest.objects.get(id=otp_request_id, user=self.request.user, used=False,
                                                 expiration_time__gte=timezone.now())
            return otp_request
        except WithdrawalOTPRequest.DoesNotExist:
            return None

    def verify_otp(self, otp_request, provided_token):
        # Verify OTP token
        
        return otp_request.otp == int(provided_token)

class StockList(generics.ListAPIView):
    queryset = Stock.objects.all()
    permission_classes =[AllowAny,]
    
    def get(self, request, *args, **kwargs):
        
        queryset = self.get_queryset()
        first = queryset.first()
        
        details = get_details3(queryset)
        symbol_data = get_symbol_data(first.symbol)
        historical_data=get_historical_data(first.symbol)
        
        response_data = {
            'stock_list': details,
            'first_symbol_order_book': symbol_data,
            'historical_data':historical_data,
        }
        return Response(response_data)
# class StockList(generics.ListAPIView):
#     queryset = Stock.objects.all()
#     permission_classes = [AllowAny]

#     async def async_get_queryset(self):
#         return await sync_to_async(lambda: list(self.queryset.all()))()

#     async def get(self, request, *args, **kwargs):
#         from .utils import get_details3, get_symbol_data, get_historical_data

#         queryset = await self.async_get_queryset()
#         details = await sync_to_async(get_details3)(queryset)

#         # Assume that get_symbol_data and get_historical_data are already async or being converted
#         first_symbol = queryset[0].symbol if queryset else None

#         if first_symbol:
#             symbol_data = await get_symbol_data(first_symbol)
#             historical_data = await get_historical_data(first_symbol)
#         else:
#             symbol_data = historical_data = None  # Handle case with no data

#         response_data = {
#             'stock_list': details,
#             'first_symbol_order_book': symbol_data,
#             'historical_data': historical_data,
#         }

#         return Response(response_data)

class MiniData(APIView):
    def get(self, request):
        data = get_mini_data()
        return Response(data)
    
class GetSingleStock(APIView):
    serializer_class = StockSerializer
    permission_classes =[AllowAny,]
    
    def get(self, request, *args, **kwargs):
        symbol = self.kwargs.get('symbol')
        # queryset = Stock.objects.get(symbol=symbol)
        queryset = get_object_or_404(Stock, symbol=symbol)
        symbol_data = get_symbol_data(symbol)
        historical_data=get_historical_data(symbol)
        
        # serializer = self.serializer_class(queryset)
        details = get_details3([queryset])
        
        response_data = {
            'stock_detail': details,
            'order_book': symbol_data,
            'historical_data':historical_data
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
    
    if incomplete_:
        incomplete = incomplete_.aggregate(total_quantity=Sum('quantity'))['total_quantity']
    else:
        incomplete = 0
        
    shares= filled + incomplete
    avg_cost = holding.avg_cost()
    ltp =  Decimal(data['current_price'])
    cur_val = round((ltp * quantity),2)
    pnl = round((ltp - avg_cost) * filled, 2)
    change = round(ltp- avg_cost ,2)
    percent_change = round((change/avg_cost) * 100,2)
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
        
class PortfolioDetail(APIView):
   def get(self, request, *args, **kwargs):
        mode = self.kwargs.get('mode')
        if not mode or mode == "demo":
            portfolio = DemoPortfolio.objects.get_or_create(user=request.user)[0]
            holdings = portfolio.demoholdings.all()

            # Use ThreadPoolExecutor to execute get_holding_detail concurrently.
            with ThreadPoolExecutor() as executor:
                # Map the holdings to the executor, it will return a generator.
                futures = [executor.submit(get_demo_holding_details_concurrently, holding) for holding in holdings]
                holdings_data = [future.result() for future in futures]

           
        if mode == 'live':
            portfolio = Portfolio.objects.get(user=request.user)
            holdings = portfolio.holdings.all()

            # Use ThreadPoolExecutor to execute get_holding_detail concurrently.
            with ThreadPoolExecutor() as executor:
                # Map the holdings to the executor, it will return a generator.
                futures = [executor.submit(get_holding_details_concurrently, holding) for holding in holdings]
                holdings_data = [future.result() for future in futures]

        portfolio_data = get_portfolio_data(holdings_data)

        data = {
            'portfolio': portfolio_data,
            'holdings': holdings_data
        }
        return Response(data)
  
        
class ReceiptsView(APIView):
    serializer_class = ReceiptsViewSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializers = ReceiptsViewSerializer(data=request.data)
        if serializers.is_valid():
            image = serializers.validated_data["image"]
            receipt=Receipts.objects.create(user=request.user, image=image)
            # sendreciptsmail(request,receipt)
            # sendreciptsmail(request,image)
            return Response({"message": "File uploaded successfully"})
        return Response(serializers.errors)
    
@api_view(['POST',])
def PayStackReceiptsView(request):
    amount=request.data.get("amount")
    paystack_recipt=PayStackReceipts.objects.create(
        user = request.user,
        reference=request.data.get("reference"),
        transaction=request.data.get("trans"),
        amount=amount,
        receipt_status = 'Confirmed'

    )
    wallet= Wallet.objects.get(user=request.user)
    wallet.balance += float(amount)
    wallet.save()
    Transaction.objects.create(user=request.user, amount=float(amount),transaction_type='deposit')
    serializer=PayStackReceiptsSerializer(paystack_recipt, many=False)
    return Response({"detail":serializer.data}, status=status.HTTP_201_CREATED)

class TransactionList(generics.ListAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only retrieve transactions for the logged-in user
        return Transaction.objects.filter(user=self.request.user)

class Symbols(APIView):
    def get(self, request):
        stocks = Stock.objects.all()
        symbols = [{stock.symbol:stock.id} for stock in stocks]
        return Response(symbols)

class AlertView(APIView):
    serializer_class= AlertSerializer


    def get(self, request):
        alerts=Alert.objects.filter(user=request.user)
        # conversation_query =  Conversation.objects.filter(user=request.user)
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
        } for alert in alerts  if alerts]
        
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
        action= ['price', 'volume']
        counter = AlertAITracker.objects.get_or_create(user=request.user)[0]

        if counter.count >= 10:
            return Response({"detail": "You have reached the maximum limit of 10 alerts for this month."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            # ensure below < above for price and volume
            if serializer.validated_data["alert_type"] not in action:
                return Response({"detail": "alert type must be 'price' or 'volume' "}, status=status.HTTP_400_BAD_REQUEST)
            
            stock = get_object_or_404(Stock, symbol =serializer.validated_data["stock"])
            name = serializer.validated_data["alert_name"] + str(randint(23, 456789))
            serializer.save(user=request.user,stock=stock, alert_name=name)
            
            counter.count += 1
            counter.save()
            
            return Response(serializer.data, status.HTTP_201_CREATED)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)
    
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
                return Response(serializer.data)
            return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)
        
    def delete(self, request, *args, **kwargs):
        id = kwargs.get("id")
        alert = self.get_queryset(id, request.user)
        if alert is not None:
            alert.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Alert not found"}, status=status.HTTP_404_NOT_FOUND)
        

class ConversationsView(APIView):
    serializer_class = ConversationSerializer
    
    def get(self, request):
        conversations = Conversation.objects.filter(user= request.user)
        serializer = AlertSerializer(conversations, many=True)
        return Response(serializer.data)

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import (Wallet, Stock, Portfolio, Holding, Receipts, PayStackReceipts, WithdrawalRequest, 
                     Transaction, WithdrawalOTPRequest)
from .serializers import (WalletSerializer, StockSerializer, PortfolioSerializer, 
                          HoldingSerializer, ReceiptsViewSerializer, PayStackReceipts, PayStackReceiptsSerializer,
                          TransactionSerializer)
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
import random
from django.core.mail import send_mail
from django.utils import timezone
from .utils import get_symbol_data,get_historical_data
from notifications.utils import save_and_send_notification
from django.shortcuts import get_object_or_404
from decimal import Decimal
from django.template.loader import render_to_string
from django.utils.html import strip_tags
 
User= get_user_model()

class WalletDetail(generics.RetrieveAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.queryset.get(user=self.request.user)

class WalletDeposit(generics.UpdateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.queryset.get(user=self.request.user)

    def perform_update(self, serializer):
        amount = self.request.data.get('amount', 0)
        wallet = self.get_object()
        wallet.balance += float(amount)
        wallet.save()


class WalletWithdraw(APIView):
    from decimal import Decimal
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        stage = request.data.get('stage')
        
        amount = request.data.get('amount')
        wallet = Wallet.objects.get(user=request.user)

        if not amount or not stage:
            return Response("amount and stage must be sent sent")
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
        from_email = "teamft9ja@gmail.com"
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
    serializer_class = StockSerializer
    permission_classes =[AllowAny,]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        first = queryset.first()
        symbol_data = get_symbol_data(first.symbol)
        serializer = self.get_serializer(queryset, many=True)
        historical_data=get_historical_data(first.symbol)
        
        response_data = {
            'stock_list': serializer.data,
            'first_symbol_order_book': symbol_data,
            'historical_data':historical_data
        }
        return Response(response_data)
    
class GetSingleStock(APIView):
    serializer_class = StockSerializer
    permission_classes =[AllowAny,]
    
    def get(self, request, *args, **kwargs):
        symbol = self.kwargs.get('symbol')
        # queryset = Stock.objects.get(symbol=symbol)
        queryset = get_object_or_404(Stock, symbol=symbol)
        symbol_data = get_symbol_data(symbol)
        historical_data=get_historical_data(symbol)
        serializer = self.serializer_class(queryset)
        response_data = {
            'stock_detail': serializer.data,
            'order_book': symbol_data,
            'historical_data':historical_data
        }
        return Response(response_data)

class StockDetail(generics.RetrieveAPIView):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    
# class HoldingListCreate(generics.ListCreateAPIView):
#     queryset = Holding.objects.all()
#     serializer_class = HoldingSerializer
#     permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

# class HoldingDetail(generics.RetrieveUpdateDestroyAPIView):
#     queryset = Holding.objects.all()
#     serializer_class = HoldingSerializer
#     permission_classes = [IsAuthenticated]

# class PortfolioDetail(generics.RetrieveAPIView):
#     queryset = Portfolio.objects.all()
#     serializer_class = PortfolioSerializer
#     permission_classes = [IsAuthenticated]

#     def retrieve(self, request, *args, **kwargs):
#         instance = self.get_object()
#         serializer = self.get_serializer(instance)

#         # Add calculated values to the response data
#         response_data = serializer.data
#         response_data['equity'] = instance.calculate_equity()
#         response_data['current_value'] = instance.calculate_current_value()
#         response_data['positions'] = instance.get_positions()

#         return Response(response_data)
    
    
class PortfolioDetail(APIView):
    def get(self, request):
        portfolio= Portfolio.objects.get(user=request.user)
        serializer1= PortfolioSerializer(portfolio)
        serializer2=HoldingSerializer(portfolio.holdings.all(), many=True)
        data = {
            'porfolio':serializer1.data,
            'holdings':serializer2.data
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
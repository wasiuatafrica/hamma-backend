from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import SavingsLock, Saving
from .serializers import SavingsLockSerializer, SavingSerializer
from rest_framework.permissions import IsAuthenticated
from portfolio.models import Wallet, Transaction
from notifications.utils import save_and_send_notification
from decimal import Decimal
from accounts.models import UserActivityLog
from execution.models import Portfolio


class SavingList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        savings_locks = Saving.objects.filter(user=request.user).order_by('-id')
        serializer = SavingSerializer(savings_locks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SavingSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data.get('amount')
            
            # Check if the amount is less than the amount in the wallet
            # user_wallet = Wallet.objects.get(user=request.user)
            user_wallet = Portfolio.objects.get_or_create(user=request.user)[0]
            if amount > user_wallet.balance:
                save_and_send_notification(request.user.id, f"You do not have enough funds to put {amount} in savings.")
                return Response({'error': 'Insufficient balance.'}, status=status.HTTP_400_BAD_REQUEST)
            
            user_wallet.balance -= Decimal(amount)
            user_wallet.save()
            
            serializer.save(user=request.user)
            
            save_and_send_notification(request.user.id, f"You transferred {amount} to Savings.")
            Transaction.objects.create(user=request.user, transaction_type = 'Transferred to Savings.', amount= Decimal(amount), status='completed')
            activity=UserActivityLog.objects.create(user=request.user, action_type="savings_lock",description=f"User transfered {amount} to savings.")
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SavingDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Saving, pk=pk, user=self.request.user)

    def get(self, request, pk):
        savings_lock = self.get_object(pk)
        serializer = SavingSerializer(savings_lock)
        return Response(serializer.data)

    def delete(self, request, pk):
        savings_lock = self.get_object(pk)
        savings_lock.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class Savingclose(APIView):
    def post(self, request, *args, **kwargs):
        id = self.kwargs.get('id')
        portfolio = Portfolio.objects.get(user=request.user)
        
        saving = get_object_or_404(Saving, pk=id, user=self.request.user)
        
        saving.status = 'closed'
        saving.save()
        
        profit = saving.amount + Decimal(saving.potential_interest)
        
        portfolio.balance += profit
        portfolio.save()
        
        save_and_send_notification(request.user.id, f"Saving closed, {profit} deposited to your wallet.")
        
        serializer = SavingSerializer(saving)
        return Response(serializer.data)


class SavingsLockList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        savings_locks = SavingsLock.objects.filter(user=request.user).order_by('-id')
        serializer = SavingsLockSerializer(savings_locks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SavingsLockSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data.get('amount')
            
            # Check if the amount is less than the amount in the wallet
            # user_wallet = Wallet.objects.get(user=request.user)
            user_wallet = Portfolio.objects.get_or_create(user=request.user)[0]
            if amount > user_wallet.balance:
                save_and_send_notification(request.user.id, f"You do not have enough funds to lock {amount} in savings.")
                return Response({'error': 'Insufficient balance in the wallet.'}, status=status.HTTP_400_BAD_REQUEST)
            
            user_wallet.balance -= Decimal(amount)
            user_wallet.save()
            
            serializer.save(user=request.user)
            
            save_and_send_notification(request.user.id, f"You transferred {amount} to Savings Lock")
            Transaction.objects.create(user=request.user, transaction_type = 'Transferred to Savings Lock', amount= Decimal(amount), status='completed')
            activity=UserActivityLog.objects.create(user=request.user, action_type="savings_lock",description=f"User transfered .{amount} to their savings lock.")
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SavingsLockDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(SavingsLock, pk=pk, user=self.request.user)

    def get(self, request, pk):
        savings_lock = self.get_object(pk)
        serializer = SavingsLockSerializer(savings_lock)
        return Response(serializer.data)

    def delete(self, request, pk):
        savings_lock = self.get_object(pk)
        savings_lock.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import SavingsLock
from .serializers import SavingsLockSerializer
from rest_framework.permissions import IsAuthenticated
from portfolio.models import Wallet, Transaction
from notifications.utils import save_and_send_notification
from decimal import Decimal
from accounts.models import UserActivityLog


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
            user_wallet = Wallet.objects.get(user=request.user)
            if amount > user_wallet.balance:
                save_and_send_notification(request.user.id, f"You do not have enough funds in wallet to lock {amount} in savings.")
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

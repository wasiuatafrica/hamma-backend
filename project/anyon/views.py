
from rest_framework.views import APIView
from rest_framework.response import Response
from accounts import models
from accounts import serializers as acc_serializers
from . import serializers
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework import permissions
from . import permissions as acc_permissions 
from rest_framework.generics import get_object_or_404
from portfolio import models
from rest_framework.parsers import MultiPartParser, FormParser
from notifications.utils import save_and_send_notification
from decimal import Decimal
from django.forms.models import model_to_dict

User=get_user_model()

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
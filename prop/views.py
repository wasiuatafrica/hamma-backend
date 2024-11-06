from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .utils import get_account_data
from rest_framework.permissions import AllowAny


class AccountDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, account_id):
        try:
            account_data = get_account_data(account_id)
            return Response(account_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

from rest_framework.views import APIView
from rest_framework.response import Response
from accounts import models as acc_models, utils as acc_utils, serializers as acc_serializers
from . import serializers as aff_serializers, models as aff_models
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework import permissions
from rest_framework.generics import get_object_or_404
from portfolio import models
from notifications.utils import save_and_send_notification


class MyRefferalLink(APIView):
    def get(self, request):
        code = acc_models.Profile.objects.get(user=request.user)
        return Response({"detail":code.referral_code})

class InviteFriend(APIView):
    def post(self, request):
        email=request.data.get("email")
        sendmail=acc_utils.send_invite_mail(request.user, email)
        return Response({"detail":'Invitaion sent successfully'})


class RewardActivitiesView(APIView):
    serializer_class=aff_serializers.RewardActivitiesSerializer

    def get(self, request):
        filter= request.GET.get("email")
        activities=""
        if filter:
            activities= aff_models.RewardActivities.objects.filter(user=request.user, trader__email=filter)
        else:
            activities= aff_models.RewardActivities.objects.filter(user=request.user)
        serializer=self.serializer_class(activities, many=True).data
        return Response(serializer)
    


class RankingView(APIView):
    serializer_class=aff_serializers.RankingsSerializer

    def get(self, request):
        rank=aff_models.Rankings.objects.all().order_by("min_brokage_commission")
        serializer=self.serializer_class(rank, many=True).data
        return Response(serializer)

# Create a rank
# refer 10 active trader in 3months 
# referee must pay >= 50000


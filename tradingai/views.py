from django.shortcuts import render
from rest_framework.views import APIView, Response
from .utils import process_recommendation


# Create your views here.


class TradeRecommendationView(APIView):
    def get(self, request):
        # try:
        #     profile = request.user.trade_profile
        #     if not profile:
        #         return Response({"error": "User has no trade profile"}, status=400)
        #     recommendations = process_recommendation(request.user.trade_profile)
        #     return Response(recommendations)
        # except Exception as e:
        #     return Response({"error": str(e)}, status=500)

        profile = request.user.trade_profile
        if not profile:
            return Response({"error": "User has no trade profile"}, status=400)
        recommendations = process_recommendation(request.user.trade_profile)
        return Response(recommendations)

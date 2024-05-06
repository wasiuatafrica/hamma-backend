from django.shortcuts import render
from rest_framework.response import Response,SimpleTemplateResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from portfolio.models import Conversation
from django.contrib.auth import get_user_model
from pymongo import MongoClient
import os
from bson import ObjectId 

User=get_user_model()

# class Home(APIView):
#     permission_classes = [AllowAny]

#     def get(self, request):
#         links = [
#             'path("register/", views.Registration.as_view(), name="register")',
#             'path("verify_token/", views.VerifyToken.as_view(), name="verify_token")',
#             'path("profile/", views.ProfileView.as_view(), name="profile")',
#             'path("2fa_on_off/", views.SetOrOff2FA.as_view(), name="2fa_on_off")',
#             'path("login/", views.LoginWithEmailView.as_view(), name="login")',
#             'path("login-with-2fa/", views.LoginWith2FA.as_view())',
#             'path("update-password-dashboard/", views.DashBoardUpdatePassword.as_view(), name="update-password-dashboard")',
#             'path("reset-password/", views.ResetForgettenPassword.as_view())',
#             ]
#         return Response(links)

  
    
def docuser(request):
    return render(request, 'docs/docuser.html')

def docadmin(request):
    return render(request, 'docs/docadmin.html')

def testai(request):
    # Get the user based on the provided email
    # email = request.GET.get('email')
    # if email:
    #     user = User.objects.get(email=email)

    #     # Fetch conversations for the user
    #     conversations = Conversation.objects.filter(user=user).order_by('-created')

    #     context = {
    #         'conversations': conversations,
    #     }

    #     return render(request, 'docs/testai.html', context)
    return render(request, 'docs/testai.html')

def alertai(request):
    
    return render(request, 'docs/alertai.html')

def connect_to_mongodb():
    client = MongoClient(os.environ.get("MONGO_STRING"),tls=True,
                             tlsAllowInvalidCertificates=True)
    # db = client["anyon_orderbook"]
    db = client["chart_data0"]
    return db

def get_price(symbol):
    db = connect_to_mongodb()
    collection = db[symbol]
    last_item = collection.find()
    # print(symbol)
    return last_item

def serialize_document(document):
    if isinstance(document, dict):
        # Traverse through the dictionary and convert ObjectId to string
        return {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in document.items()}
    return document


class ChartData(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        symbol = request.data.get("symbol")  # Use query params instead of data for GET
        data = list(get_price(symbol))
        
        # Convert ObjectId to string for all documents
        serialized_data = [serialize_document(doc) for doc in data] 

        return Response(serialized_data)
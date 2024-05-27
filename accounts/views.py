from math import e
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework import permissions

from portfolio.models import Wallet
from . import serializers
from . import models
from .utils import verify_token, resendToken,SetTOTP, verifyTOTP,sms_2FA
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone  
from execution.models import Portfolio, DemoPortfolio, DemoDailyReturns, DailyReturns
from .tasks import set_up_user, send_welcome_email
from affilate.models import ReferralWallet

User=get_user_model()
class Registration(APIView):
    serializer_class=serializers.CustomUserSerializer
    permission_classes=[permissions.AllowAny]
    def post(self, request):
        serializer=self.serializer_class(data=request.data)
        ref_code= request.data.get('ref_code')
        if serializer.is_valid():
            user=serializer.save()
            user.set_password(request.data.get("password"))
            # user.signup_type="email"
            user.save()
            # Create the referral object. 
            referred_by= models.Profile.objects.filter(referral_code=ref_code).first()
            if referred_by:
                referral=models.Referral.objects.create(user=referred_by.user, person_referred=user)
                # print(referral.status, referral.user, "hhhhh")
            return Response({"detail":"A token has been sent to your mail","user":serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    # Allow users request for resending of token for users who
    # could not activate account at first
    def put(self, request):
        email=request.data.get("email")
        user=User.objects.filter(email=email).first()
        if not user:
            return Response({"detail":"User with email not found"}, status=status.HTTP_404_NOT_FOUND)
        resendToken(user, "signup")
        return Response("Token Resent")

class VerifyToken(APIView):
    serializer_class=serializers.TokenSerializer
    permission_classes=[permissions.AllowAny]
    def post(self, request):
        token=request.data.get("token")
        user_email=request.data.get("user_email")
        if not token and user_email:
            return Response({"detail":"Token or user_email missing"}, status=status.HTTP_400_BAD_REQUEST)
        token_reponse=verify_token(user_email, token)
        if not token_reponse:
            return Response({"detail":"Token or user_email is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        
        user=User.objects.get(email=user_email)
                
        # Portfolio.objects.create(user=user)
        # ReferralWallet.objects.create(user=user)
        # DemoPortfolio.objects.create(user=user)
        # send_welcome_email.delay(user.id)
        # # set_up_user.delay(user_email)
        # activity=models.UserActivityLog.objects.create(user=user, action_type="verified_account",description="User verified their account.")
        
        # return Response({"detail":"Account verifed."})
                
        # Portfolio.objects.create(user=user)
        Wallet.objects.create(user=user)
        ReferralWallet.objects.create(user=user)
        # DemoPortfolio.objects.create(user=user)
        send_welcome_email.delay(user.id)
        activity=models.UserActivityLog.objects.create(user=user, action_type="verified_account",description="User verified their account.")
        
        refresh = RefreshToken.for_user(user)
        user_data =serializers.CustomUserSerializer(user, many=False).data
        user.last_login=timezone.now()
        user.save()
        token_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            "user": user_data
        }
        activity=models.UserActivityLog.objects.create(user=user, action_type="login",description="User logged into their account")
        return Response(token_data, status=status.HTTP_200_OK)

class ProfileView(APIView):
    queryset = models.Profile.objects.all()
    serializer_class = serializers.ProfileSerializer

    def get_object(self, request):
        try:
            return models.Profile.objects.get(user=request.user)
        except models.Profile.DoesNotExist:
            return None

    def get(self, request):
        # Get an instance by ID
        instance = self.get_object(request)
        if instance is None:
            return Response({"detail": "User instance not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(instance)
        user=serializers.CustomUserSerializer(request.user, many=False).data
        return Response({"detail":serializer.data, "user":user}, status=status.HTTP_200_OK)

    def put(self, request):
        instance = self.get_object(request)
        serializer=self.serializer_class(instance,data=request.data)
        user_serializer=serializers.UpdateCustomUserSerializer(request.user, data=request.data)
        if instance is None:
            return Response({"detail": "User instance not found"}, status=status.HTTP_404_NOT_FOUND)
        if serializer.is_valid():
            serializer.save()
            if user_serializer.is_valid():
                user_serializer.save()
            else:
                return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            user=serializers.CustomUserSerializer(request.user, many=False).data
            activity=models.UserActivityLog.objects.create(user=request.user, action_type="updated_profile",description="User updated their profile")
            return Response({"detail":serializer.data, "user":user})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Set up 2fa for account
class SetOrOff2FA(APIView):

    serializer_class=serializers.Turn2FAOnOrOff
    def post(self, request):
        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            user=request.user
            if user.twofa_type==serializer.validated_data["action"] or serializer.validated_data["action"] == "none":
                # this means the users wants to turn off 
                # user.has_2fa=False
                user.twofa_type = "email"
                user.save()
                return Response({"detail":"2fa changed to email.", "user":serializers.CustomUserSerializer(request.user, many=False).data})
            # else the user wants to turn on 2fa
            user.has_2fa=True
            user.twofa_type = serializer.validated_data["action"]
            user.save()
            if serializer.validated_data["action"] == "authapps":#user wants to set authapp 2fa
                user.twofa_type = "email"
                user.save()
                authapp=SetTOTP(user)
                return Response({"detail":"2FA turn on successsfully, but you must provide token for your authentication app to activate.","qr_url":authapp, "user":serializers.CustomUserSerializer(request.user, many=False).data})
            return Response({"detail":"2FA turn on successsfully", "user":serializers.CustomUserSerializer(request.user, many=False).data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DashBoardUpdatePassword(APIView):
    serializer_class = serializers.DashBoardChangePassword 

    def post(self, request):
        serializer=self.serializer_class(data=request.data)
        user=request.user
        if serializer.is_valid(): 
            if not serializer.validated_data["new_password1"] == serializer.validated_data["new_password2"]:
                return Response({"detail":"new_password1 and new_passowrd2 must match"}, status=status.HTTP_400_BAD_REQUEST)
            if user.check_password(serializer.validated_data["current_password"]):
                user.set_password(serializer.validated_data["new_password1"])
                user.save()
                activity=models.UserActivityLog.objects.create(user=user, action_type="change_password",description="User changed their password")
                return Response({"detail":"Password updated successfully"})
            return Response({"detail":"current_password is wrong"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# verify_one_time_token
class LoginWithEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = serializers.LoginWithEmailSeriailizer  # Use the correct serializer class

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        ip_address = request.data.get("ip_address")
        location = request.data.get("location")
        device = request.data.get("device")
        
        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data["email"])
            except User.DoesNotExist:
                return Response({"detail": "This account does not exist"}, status=status.HTTP_404_NOT_FOUND)
            if not user.is_active :
                    return Response({"detail": "This account is not active. Please verify account before login."}, status=status.HTTP_400_BAD_REQUEST)
            
            if user.check_password(password):
                # requires_2fa = self.requires_2fa(user, ip_address, location, device)
                requires_2fa = False
                print(requires_2fa)
                
                if requires_2fa:
                    if user.has_2fa:
                        if user.twofa_type =="authapps": #send the user to the login
                            return Response({"detail": "Please provide token from your 2fa application"}, status=status.HTTP_202_ACCEPTED)
                        elif user.twofa_type =="sms": #send the user to the login
                            user_phone=models.Profile.objects.get(user=user).phone
                            sms_token=resendToken(user, "sms")
                            send_sms_2fa=sms_2FA(user_phone,sms_token)
                            return Response({"detail": "Please provide  sms token sent to your phone", "sms":sms_token}, status=status.HTTP_202_ACCEPTED)
                        user = User.objects.get(email=email, is_active=True)
                        resendToken(user, "login")
                        return Response({"detail": "Please check your mail for your 2fa token"}, status=status.HTTP_202_ACCEPTED)
                # Successful login without 2FA prompt
                refresh = RefreshToken.for_user(user)
                # refresh.save()
                user_data =serializers.CustomUserSerializer(user, many=False).data
                # update last_login
                user.last_login=timezone.now()
                user.save()
                token_data = {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    "user": user_data
                }
                #Add activity
                activity=models.UserActivityLog.objects.create(user=user, action_type="login",description="User logged into their account")
                return Response(token_data, status=status.HTTP_200_OK)
                # return Response({"detail": "Login successful"}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        #     if user.check_password(password):
        #         if user.has_2fa:
        #             if user.twofa_type =="authapps": #send the user to the login
        #                 return Response({"detail": "Please provide token from your 2fa application"}, status=status.HTTP_202_ACCEPTED)
        #             elif user.twofa_type =="sms": #send the user to the login
        #                 user_phone=models.Profile.objects.get(user=user).phone
        #                 sms_token=resendToken(user, "sms")
        #                 send_sms_2fa=sms_2FA(user_phone,sms_token)
        #                 return Response({"detail": "Please provide  sms token sent to your phone", "sms":sms_token}, status=status.HTTP_202_ACCEPTED)
        #             user = User.objects.get(email=email, is_active=True)
        #             resendToken(user, "login")
        #             return Response({"detail": "Please check your mail for your 2fa token"}, status=status.HTTP_202_ACCEPTED)
               
        #     else:
        #         return Response({"detail": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
        # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def requires_2fa(self, user, ip_address, location, device):
        # Check if any of the conditions for requiring 2FA are met
        if ip_address is None or location is None or device is None:
        # If any of these fields are missing, return True to indicate 2FA is required
            return True

        try:
            first_time = models.FirstLogin.objects.get(user=user)
        except models.FirstLogin.DoesNotExist:
            first_time = None
            
        if not first_time:
            print('first_time', True)
            # first_time = models.FirstLogin(user=user)
            # first_time.save()
            return True
        
        # if user.last_ip != ip_address:
        #     print('ip_address', True)
            
        #     # user.last_ip = ip_address
        #     # user.save()
        #     return True
        
        # if user.last_location != location:
        #     print('location', True)
            
        #     # user.last_location = location
        #     # user.save()
        #     return True
        
        if user.last_device != device:
            print(device, user.last_device)
            print('device', True)
            
            # user.last_device = device
            # user.save()
            return True
        return False

        
    
class LoginWith2FA(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class =serializers.LoginTokenSeriailizer
    
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        # password = request.data.get("password")
        token = request.data.get("token")
        ip_address = request.data.get("ip_address")
        location = request.data.get("location")
        device = request.data.get("device")

        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:

                return Response({"detail": "User not found or user account not active"}, status=status.HTTP_404_NOT_FOUND)
            
            if user.twofa_type =="authapps": #user is bringing token from authapps
                v_token= verifyTOTP(user, token)
            else:
                v_token=verify_token(email, token) 
            if v_token:
                refresh = RefreshToken.for_user(user)
                # refresh.save()
                user_data =serializers.CustomUserSerializer(user, many=False).data
                # update last_login
                user.last_login=timezone.now()
                user.last_ip = ip_address
                user.last_location = location
                user.last_device = device             
                user.save()
                
                token_data = {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    "user": user_data
                }
                #Add activity
                first_time = models.FirstLogin.objects.get_or_create(user=user)
                activity=models.UserActivityLog.objects.create(user=user, action_type="login",description="User logged into their account")
                return Response(token_data, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

            # else:
            #     return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActivteAuthApp2fa(APIView): 
    serializer_class=serializers.TokenSerializer  

    def post(self, request): 
        serializer=self.serializer_class(data=request.data)
        user=request.user
        if serializer.is_valid():            
            v_token= verifyTOTP(user, serializer.validated_data["token"])
            if v_token:
                user.twofa_type = "authapps" 
                user.save() 
                return Response({"detail":"Authapp 2fa enabled successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 

class ResetForgettenPassword(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class=serializers.ResetForgottenPassword

    def get_user(self, email):
        return User.objects.filter(email=email).first()

    def post(self, request):
        email = request.data.get("email")
        user =  self.get_user(email)

        if not user and email:
            return Response({"detail": "User not found or invalid email"}, status=status.HTTP_404_NOT_FOUND)

        resendToken(user, "password")

        return Response({"detail": "Reset password token has been sent to your email. Token will expire in 10mins"})

    def get(self, request):
        email=request.GET.get("email")
        token=request.GET.get("token")
        if email and token:
            validate_token=  verify_token(email, token,"validate")
            if validate_token:
                return Response({"detail":"Ok"})
            return Response({"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"detail":"email and token is required"}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        serializer=self.serializer_class(data=request.data)
        if serializer.is_valid():
            user= self.get_user(serializer.validated_data["email"])
            if user:
                validate_token=   verify_token(user.email, serializer.validated_data["token"])
                if validate_token:
                    if serializer.validated_data["new_password1"] == serializer.validated_data["new_password2"]:
                        user.set_password(serializer.validated_data["new_password1"])
                        user.save()
                        activity=models.UserActivityLog.objects.create(user=user, action_type="change_password",description="User changed their password")
                        return Response({"detail":"Password updated successfully"}) 
                    return Response({"detail":"new_password1 and new_passowrd2 must match"}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"detail":"User with this email not found."}, status=status.HTTP_404_NOT_FOUND) 
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UnsubscribeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_user(self, email):
        user=User.objects.filter(email=email).first()
        if not user:
            return None
        return user 
    
    def get(self, request):
        email=request.GET.get("email")
        if not email:
            return Response({"detail":"email is required in params"}, status=status.HTTP_400_BAD_REQUEST)
        user = self.get_user(email)
        if user is None:
            return Response({"detail": f"User with this email {email} does not exist"}, status=status.HTTP_404_NOT_FOUND)
        unsubscribe =models.Unsubscribe.objects.filter(email=email).first()
        if not unsubscribe:
            unsubscribe =models.Unsubscribe.objects.create(email=email)
            return Response({"detail":"Ok"})
        return Response({"detail":"Cannot unsubscribed same email twice."}, status=status.HTTP_400_BAD_REQUEST)

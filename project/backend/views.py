from django.shortcuts import render
from rest_framework.response import Response,SimpleTemplateResponse
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny



class Home(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        links = [
            'path("register/", views.Registration.as_view(), name="register")',
            'path("verify_token/", views.VerifyToken.as_view(), name="verify_token")',
            'path("profile/", views.ProfileView.as_view(), name="profile")',
            'path("2fa_on_off/", views.SetOrOff2FA.as_view(), name="2fa_on_off")',
            'path("login/", views.LoginWithEmailView.as_view(), name="login")',
            'path("login-with-2fa/", views.LoginWith2FA.as_view())',
            'path("update-password-dashboard/", views.DashBoardUpdatePassword.as_view(), name="update-password-dashboard")',
            'path("reset-password/", views.ResetForgettenPassword.as_view())',
            ]
        return Response(links)

  
    
def docuser(request):
    return render(request, 'docs/docuser.html')

def docadmin(request):
    return render(request, 'docs/docadmin.html')
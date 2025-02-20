from django.urls import path
from . import views


urlpatterns = [
    path("register/", views.Registration.as_view(), name="register"),
    # path("sign-with-google/", views.SignupwithGoogle.as_view()),
    path("verify_token/", views.VerifyToken.as_view(), name="verify_token"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("support-profile/", views.SupportProfileView.as_view(), name="profile"),
    path("2fa_on_off/", views.SetOrOff2FA.as_view(), name="2fa_on_off"),
    path("login/", views.LoginWithEmailView.as_view(), name="login"),
    path("login-with-2fa/", views.LoginWith2FA.as_view()),
    path(
        "update-password-dashboard/",
        views.DashBoardUpdatePassword.as_view(),
        name="update-password-dashboard",
    ),
    path("reset-password/", views.ResetForgettenPassword.as_view()),
    path("activate-authapp/", views.ActivteAuthApp2fa.as_view()),
    path("unsubscribe/", views.UnsubscribeView.as_view()),
    path(
        "trading-profile/", views.TradingProfileView.as_view(), name="trading-profile"
    ),
]

# external_trading/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"connections", views.ExternalConnectionViewSet, basename="connection")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "api/<str:account_type>/<int:account_id>/positions/",
        views.ExternalTradeAPI.as_view(),
        name="external-positions",
    ),
    path(
        "api/<str:account_type>/<int:account_id>/trade/",
        views.ExternalTradeAPI.as_view(),
        name="external-trade",
    ),
    path(
        "api/auth/",
        views.AuthenticateAndConnect.as_view(),
        name="authenticate-and-connect",
    ),
    # Account listing for external platforms
    path(
        "api/accounts/",
        views.ConnectionAccountsView.as_view(),
        name="connection-accounts",
    ),
    # path(
    #     "api/<str:account_type>/<int:account_id>/trade/<int:position_id>/",
    #     views.ExternalTradeAPI.as_view(),
    #     name="external-close-trade",
    # ),
    path(
        "api/delete-connection/",
        views.DeleteConnectionView.as_view(),
        name="delete-connection",
    ),
]

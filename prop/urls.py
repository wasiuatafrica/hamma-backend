from django.urls import path
from .views import AccountDataView

urlpatterns = [
    path("account-data/<account_id>/", AccountDataView.as_view(), name="account-data"),
]

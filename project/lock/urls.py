from django.urls import path
from .views import SavingsLockList, SavingsLockDetail

urlpatterns = [
    path('savings/', SavingsLockList.as_view(), name='savings_lock_list_api'),
    path('savings/<int:pk>/', SavingsLockDetail.as_view(), name='savings_lock_detail_api'),
]

from django.urls import path
from .views import SavingsLockList, SavingsLockDetail, SavingList,SavingDetail, Savingclose

urlpatterns = [
    path('savings/', SavingsLockList.as_view(), name='savings_lock_list_api'),
    path('savings/<int:pk>/', SavingsLockDetail.as_view(), name='savings_lock_detail_api'),
    path('saving/', SavingList.as_view(), ),
    path('saving/<int:pk>/', SavingDetail.as_view(), ),
    path('saving/close/<str:id>/', Savingclose.as_view(), ),
]

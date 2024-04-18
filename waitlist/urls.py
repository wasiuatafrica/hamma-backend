from django.urls import path
from . import views

urlpatterns = [
    path('waitlist/', views.WaitlistListCreateView.as_view(), name='waitlist-list-create'),
    path('wait-list/', views.waitlist_users, name='wait-list'),
    path('joinclick/', views.joinclick, name='joinclick'),
    path('joinclicks/', views.JoinClickView.as_view())
]
from django.urls import path
from . import views

urlpatterns = [
    path('waitlist/', views.WaitlistListCreateView.as_view(), name='waitlist-list-create'),
]
from django.urls import path
from . import views

urlpatterns = [
    path("update-notification/", views.UpdateNotification.as_view()),
    path("user-email-notifications/", views.FetchNotification.as_view()),
]

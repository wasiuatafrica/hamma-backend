from django.urls import path, include
from django.urls.conf import re_path
from . import views

urlpatterns = [
   path("manage-users/", views.AdminManageUser.as_view(), name="manage-users"),
   path("manage-users/<user_id>/", views.AdminManageUser.as_view(), name="manage-users"),
]

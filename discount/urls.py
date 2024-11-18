from django.urls import path
from . import views

urlpatterns = [
    path("validity/<str:code>/", views.DiscountCodeValidity.as_view()),
    path(
        "codes/",
        views.DiscountCodeListCreateView.as_view(),
        name="discount-code-list-create",
    ),
    path(
        "codes/<int:pk>/",
        views.DiscountCodeDetailView.as_view(),
        name="discount-code-detail",
    ),
]

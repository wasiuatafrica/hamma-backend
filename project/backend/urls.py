
from django.contrib import admin
from django.urls import path, include
from backend import views
from django.conf import settings
from django.conf.urls.static import static


from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns =  (   [
        path("devadmin/", admin.site.urls),
        path("home/", views.Home.as_view(), name="home"),
        path("", views.docuser,),
        path("docadmin/", views.docadmin,),
        path("", include("django.contrib.auth.urls")),
        path('drf/', include('rest_framework.urls')),
        path("auth/", include("accounts.urls")),
        path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
        path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
        path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
        path('blog/',include("blog.urls")),
        path('anyon/',include("anyon.urls")),
        path('execution/',include("execution.urls")),
        path('portfolio/',include("portfolio.urls")),
        path('reporting/',include("reporting.urls")),
        path('affilate/',include("affilate.urls")),
        path('lock/',include("lock.urls")),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)

urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
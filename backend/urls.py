from django.contrib import admin
from django.urls import path, include
from backend import views
from django.conf import settings
from django.conf.urls.static import static
import os

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# from django.http import HttpResponse
# from django.utils import timezone
# import logging
# import datetime
# from PIL import Image

# # Set up logging to a file
# logger = logging.getLogger(__name__)
# logging.basicConfig(filename="email_open_log.log", level=logging.INFO)


# def track_daily_mail(request, user_id=None):
#     # print("heloo")
#     # # # Log when the email is opened
#     # log_info = f"Email opened by User ID: {user_id} at {datetime.datetime.now()} from IP: {request.META.get('REMOTE_ADDR')}"
#     # logger.info(log_info)
#     # print(log_info)  # Also print to console for immediate feedback

#     # Serve a 1x1 pixel image (tracking pixel)
#     pixel = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b"
#     return HttpResponse(pixel, content_type="image/gif")
#     # print("\nImage Loaded\n")
#     # red = Image.new("RGB", (1, 1))
#     # response = HttpResponse(content_type="image/png")
#     # red.save(response, "PNG")
#     # return response


urlpatterns = (
    [
        path("devadmin/", admin.site.urls),
        # path("track-mail", track_daily_mail, name="track_daily_mail"),
        # path("home/", views.Home.as_view(), name="home"),
        path(
            "",
            views.docuser,
        ),
        path(
            "docadmin/",
            views.docadmin,
        ),
        path(
            "marketsai/",
            views.testai,
        ),
        path(
            "alertai/",
            views.alertai,
        ),
        path("", include("django.contrib.auth.urls")),
        path("drf/", include("rest_framework.urls")),
        path("auth/", include("accounts.urls")),
        path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
        path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
        path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
        path("blog/", include("blog.urls")),
        path("anyon/", include("anyon.urls")),
        path("execution/", include("execution.urls")),
        path("portfolio/", include("portfolio.urls")),
        path("reporting/", include("reporting.urls")),
        path("affilate/", include("affilate.urls")),
        path("lock/", include("lock.urls")),
        path("leaderboard/", include("competition.urls")),
        # path('hackathon/',include("hackathon.urls")),
        path("", include("notifications.urls")),
        path("", include("waitlist.urls")),
        path("", include("tradingai.urls")),
        path("streaks/", include("streaks.urls")),
        path("prop/", include("prop.urls")),
        path(
            "chart-data/",
            views.ChartData.as_view(),
        ),
        path("support/", include("supportwithemail.urls")),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)
if os.environ.get("server") == "local":
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]

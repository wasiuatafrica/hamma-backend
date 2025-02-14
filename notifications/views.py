from httpx import get
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .tasks import update_notifications_task
from .utils import get_all_notifications
from django.contrib.auth import get_user_model

User = get_user_model()


class UpdateNotification(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = str(request.user.id)

        # Trigger the Celery task
        update_notifications_task.delay(user_id)

        return Response({"message": "Notification update process has been initiated"})


class FetchNotification(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        email = request.query_params.get("email", None)
        if not email:
            return Response({"message": "Email is required"})
        user = User.objects.get(email=email)

        # Trigger the Celery task
        nots = get_all_notifications(user.id)

        return Response({"notifications": nots})

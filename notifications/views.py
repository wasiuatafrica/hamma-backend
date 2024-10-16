from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .tasks import update_notifications_task


class UpdateNotification(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = str(request.user.id)

        # Trigger the Celery task
        update_notifications_task.delay(user_id)

        return Response({"message": "Notification update process has been initiated"})

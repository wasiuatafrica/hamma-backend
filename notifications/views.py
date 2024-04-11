from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from .utils import update_notification

class UpdateNotification(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        data = request.data
        if data:
            notification_id = data.get('ids')
            print(notification_id)
            for id in notification_id:
                notification = id.split('-')
                if notification:
                    update_notification(notification[1], notification[0])
        return Response({"message": "Notification marked as read"})

                    
                    
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from .utils import update_notification, table

# class UpdateNotification(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         data = request.data
#         if data:
#             notification_id = data.get('ids')
#             print(notification_id)
#             for id in notification_id:
#                 notification = id.split('-')
#                 if notification:
#                     update_notification(notification[1], notification[0])
#         return Response({"message": "Notification marked as read"})


class UpdateNotification(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = str(request.user.id)

        response = table.query(
            KeyConditionExpression="user_id = :uid",
            FilterExpression="is_read = :ir",
            ExpressionAttributeValues={
                ":uid": str(user_id),
                ":ir": "False",
            },
        )

        notifications = response.get("Items", [])

        # Update each notification
        for notification in notifications:
            table.update_item(
                Key={
                    "user_id": user_id,
                    "notification_id": notification["notification_id"],
                },
                UpdateExpression="SET is_read = :ir",
                ExpressionAttributeValues={":ir": True},
            )

        return Response({"message": "Notification marked as read"})

from rest_framework import generics
from .models import Waitlist
from .serializer import WaitlistSerializer
from rest_framework.permissions import AllowAny

class WaitlistListCreateView(generics.ListCreateAPIView):
    queryset = Waitlist.objects.all()
    serializer_class = WaitlistSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Waitlist.objects.all()

    def perform_create(self, serializer):
        email = serializer.validated_data.get('email')
        # phone_number = serializer.validated_data.get('phone_number')
        serializer.save(email=email)
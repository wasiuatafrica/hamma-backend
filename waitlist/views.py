from django.http import JsonResponse
from rest_framework import generics
from rest_framework.views import APIView
from .models import Waitlist, JoinClick
from .serializer import WaitlistSerializer, JoinClickSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger 
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Max, Q
from django.shortcuts import render, redirect,get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response

def is_user_staff(user):
    return user.is_staff

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

class JoinClickView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):
        JoinClick.objects.create(user=request.user)
        return Response('success')
        
     
@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def waitlist_users(request):
    users = Waitlist.objects.all().order_by('-created_at')

    # Handling search functionality
    query = request.GET.get('search')
    if query:
        users = users.filter(
            Q(email__icontains=query) 
        )

    # Paginate users list
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page')
    try:
        page_number = int(page_number)
    except (TypeError, ValueError):
        page_number = 1  # Default to first page if page number is not provided or invalid

    try:
        users = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        users = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        users = paginator.page(paginator.num_pages)


    return render(request, 'leaderboard/waitlist.html', {'users': users})


@login_required
@csrf_exempt
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def joinclick(request):
    
    # distinct_users = JoinClick.objects.values('user').distinct().order_by('-created')

    # # If you want to fetch the actual User objects, you can perform a separate query
    # users = User.objects.filter(id__in=distinct_users)
    
    users = JoinClick.objects.all().order_by('-created')

    # Handling search functionality
    query = request.GET.get('search')
    if query:
        users = users.filter(
            Q(email__icontains=query) 
        )

    # Paginate users list
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page')
    try:
        page_number = int(page_number)
    except (TypeError, ValueError):
        page_number = 1  # Default to first page if page number is not provided or invalid

    try:
        users = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        users = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        users = paginator.page(paginator.num_pages)


    return render(request, 'leaderboard/joinclick.html', {'users': users})
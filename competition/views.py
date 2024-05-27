from datetime import date as dt
from datetime import datetime,time, date, timedelta
from functools import partial
from multiprocessing import context
import pytz

from django.shortcuts import render, redirect,get_object_or_404
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger 
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Max, Q
from django.http import JsonResponse, HttpResponseRedirect,HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
import pandas as pd
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from . import serializers
from .tasks import create_returns
from .models import (
    Clan,
    CompetitionDailyReturns,
    CompetitionPosition,
JoinClanRequest,
TopClanPayout,
TopTraderPayout,
Notification,
Competition,
CompetitionPortfolio,
CompetitionSummary,
TopTraderPayoutButtonShows,
TopTraderPayoutImg,
TopClanPayoutButtonShows,
TopClanPayoutImg,
ClanCompetitionSummary,
CreateClanRequest,
TopClanMembersPayout,
TopClanMembersPayoutImg,
    get_price
)
from notifications.utils import save_and_send_notification,get_notifications,update_notification
from accounts.models import Profile
from .utils import count_business_days
import competition

# competion
from competition import models as competion_models, serializers as competion_serializers
from django.utils import timezone

# Send mails
from .managers.utils import sendMail 


User = get_user_model()
# Create your views here.


def is_user_staff(user):
    return user.is_staff

class CompetitionView(APIView):
    def get(self, request, *args, **kwargs):
        competitions = Competition.objects.all()
        serializer = serializers.CompetitionSerializer(competitions, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = serializers.CompetitionSerializer(data=request.data)
        if serializer.is_valid():
            start_date = serializer.validated_data.get('start_date')
            end_date = serializer.validated_data.get('end_date')
            
            if start_date >= end_date:
                return Response({"error": "End date must be greater than start date."}, status=status.HTTP_400_BAD_REQUEST)

            current_competition = Competition.objects.filter(status='current').first()
            if current_competition:
                current_competition.status = 'closed'
                current_competition.save()
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CompetitionCheck(APIView):
     def get(self, request, *args, **kwargs):
        portfolio = CompetitionPortfolio.objects.filter(user=request.user, competition__status='current').first()
        if portfolio and portfolio.active:
            return Response({"competition": "True", "status":"active"})
        elif portfolio and not portfolio.active:
            return Response({"competition": "True", "status":"inactive"})
        else:
            return Response({"competition": "False", "status":"inactive"})

class InCompetition(APIView):
    def get(self, request, *args, **kwargs):
        
        portfolio = CompetitionPortfolio.objects.filter(user=request.user, competition__status='current', active=True).first()
        if portfolio:
            in_competition=True
        else:
            in_competition=False
        return Response({'in_competition':in_competition})
            
class CurrentCompetition(APIView):
    permission_classes= [AllowAny]
    def get(self, request, *args, **kwargs):
        try:
            current = Competition.objects.get(status='current')
            # print('exists')
            # print(current)
        except Competition.DoesNotExist:
            # print('not exist')
            current = Competition.objects.all().order_by('id').last()
        
        serializer=serializers.CompetitionSerializer(current)
        
        return Response(serializer.data)

class JoinLeaveCompetetion(APIView):
    
    def post(self, request, *args, **kwargs):
        # competition_id=kwargs.get('competition_id')
        action=kwargs.get('action')
        
        actions = ['join', 'leave']
        if action not in actions:
            return Response({"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            competition = Competition.objects.get(status='current')
        except Competition.DoesNotExist:
            return Response({"detail": "There is no ongoing competition"}, status=status.HTTP_404_NOT_FOUND)
        
        clan_query= Clan.objects.filter(clan_admin=request.user)
        
        # more_than_one_member=False
                
        # # print('exists',clan_query.exists())
        # if clan_query.exists():
        #     clan = clan_query.first()
        #     clan_members=clan.member.all().count()
        #     if clan_members < 2:
        #         save_and_send_notification(request.user.id, "There should be atleast 3 people in your clan before you can join competition.")
                
        #         return Response({"detail": "You need at least two (2) member in your clan to be able to participate in this competition."}, status=status.HTTP_400_BAD_REQUEST)
        #     else:
        #         more_than_one_member=True
                
        clan_query2= Clan.objects.filter(member=request.user)
        
        
        # if clan_query2.exists() and clan_query2.first().member.all().count() < 2:
        #     save_and_send_notification(request.user.id, "There should be atleast 3 people in your clan before you can join competition.")
                
        #     return Response({"detail": "You need at least 3 people in your clan to be able to participate in this competition."}, status=status.HTTP_400_BAD_REQUEST)
            
        # if (clan_query2.exists() and clan_query2.first().member.all().count() > 1) or (clan_query.exists() and more_than_one_member) :
        if clan_query2.exists()  or clan_query.exists() :
        
            portfolio = CompetitionPortfolio.objects.filter(competition=competition,user=request.user).first()
            
            if action == "join":
                # if competition.start_date > timezone.now():
                #     return Response({"detail": "Competition has not started"}, status=status.HTTP_400_BAD_REQUEST)
                if competition.end_date - timezone.now() < timedelta(weeks=2):
                    
                    return Response({"detail": "You can only join the competition up to 2 weeks before the end"}, status=status.HTTP_400_BAD_REQUEST)
                if portfolio:
                    if portfolio.active:
                        return Response({"detail": "You are already  in this competition"}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({"detail": "You have  already exited this competition"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    portfolio = CompetitionPortfolio.objects.create(competition=competition, user=request.user, balance=1000000)
                    create_returns.delay(portfolio.id)
                    save_and_send_notification(portfolio.user.id, "You have joined the ongoing competition. Goodluck!")
                    return Response({"detail": "You have successfully joined this competition"}, status=status.HTTP_200_OK)
                
            elif action == "leave":
                if not portfolio:
                    return Response({"detail": "You are not in this competition"}, status=status.HTTP_400_BAD_REQUEST)
                if portfolio:
                    if portfolio.active:
                        portfolio.active = False
                        portfolio.save()
                        return Response({"detail": "You have successfully left this competition"}, status=status.HTTP_200_OK)
                    else:
                        return Response({"detail": "You have  already exited this competition"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            save_and_send_notification(request.user.id, "You need to be in a clan to join competition. Create or join one clan.")
            
            return Response({"detail": "You need to be in a clan to join competition. Create or join one clan."}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
def join_competition(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            competition = Competition.objects.get(status='current')
        except Competition.DoesNotExist:
            error_message = "There is no ongoing competition"
            return render(request, 'leaderboard/join.html', {'error_message': error_message})
        
        clan_query = Clan.objects.filter(clan_admin=request.user)
        more_than_one_member = False
                
        if clan_query.exists():
            clan = clan_query.first()
            clan_members = clan.member.all().count()
            if clan_members < 2:
                error_message = "You need at least two (2) members in your clan to be able to participate in this competition."
                return render(request, 'leaderboard/join.html', {'error_message': error_message})
            else:
                more_than_one_member = True
                
        clan_query2 = Clan.objects.filter(member=request.user)
        
        if clan_query2.exists() and clan_query2.first().member.all().count() < 2:
            error_message = "You need at least 3 people in your clan to be able to participate in this competition."
            return render(request, 'leaderboard/join.html', {'error_message': error_message})
            
        if (clan_query2.exists() and clan_query2.first().member.all().count() > 1) or (clan_query.exists() and more_than_one_member):
            portfolio = CompetitionPortfolio.objects.filter(competition=competition, user=request.user).first()
            
            if action == "join":
                if competition.end_date - timezone.now() < timedelta(weeks=2):
                    error_message = "You can only join the competition up to 2 weeks before the end"
                    return render(request, 'leaderboard/join.html', {'error_message': error_message})
                
                if portfolio:
                    if portfolio.active:
                        error_message = "You are already in this competition"
                        return render(request, 'leaderboard/join.html', {'error_message': error_message})
                    else:
                        error_message = "You have already exited this competition"
                        return render(request, 'leaderboard/join.html', {'error_message': error_message})
                else:
                    portfolio = CompetitionPortfolio.objects.create(competition=competition, user=request.user, balance=1000000)
                    create_returns.delay(portfolio.id)
                    save_and_send_notification(portfolio.user.id, "You have joined the ongoing competition. Good luck!")
                    success_message = "You have successfully joined this competition"
                    return render(request, 'leaderboard/join.html', {'success_message': success_message})
                
            elif action == "leave":
                if not portfolio:
                    error_message = "You are not in this competition"
                    return render(request, 'leaderboard/join.html', {'error_message': error_message})
                if portfolio.active:
                    portfolio.active = False
                    portfolio.save()
                    success_message = "You have successfully left this competition"
                    return render(request, 'leaderboard/join.html', {'success_message': success_message})
                else:
                    error_message = "You have already exited this competition"
                    return render(request, 'leaderboard/join.html', {'error_message': error_message})
        else:
            error_message = "You need to be in a clan to join the competition. Create or join a clan."
            return render(request, 'leaderboard/join.html', {'error_message': error_message}) 

    return render(request, 'leaderboard/join.html')




class ClanViewSet(viewsets.ModelViewSet):
    serializer_class =  serializers.ClanSerializer
    queryset = Clan.objects.all()
    lookup_field= 'id'
    permission_classes = (AllowAny,)
    
    @method_decorator(cache_page(60*60*2))  # Cache the response for 5 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, id=None): 
        item = get_object_or_404(self.queryset, id=id) 
        serializer = self.get_serializer(item) 
        return Response(serializer.data, status=status.HTTP_200_OK) 
    
class ClanUpdateLogoAndLInk(APIView):
    serializer_class= serializers.ClanUpdateSerializer

    def get_clan(self, id):
        clan= Clan.objects.filter(id=id).first()
        if not clan:
            return None
        return clan
    
    def put(self, request, *args, **kwargs):
        id = kwargs.get("clan_id")
        clan = self.get_clan(id)
        if clan is None:
            return Response({"detail": f"Clan with id {id} not found."}, status=status.HTTP_400_BAD_REQUEST)
        if clan.clan_admin != request.user:
            return Response({"detail": f"Permission denied. NOt  a clan admin"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(clan, data=request.data,partial=True, context={"request":request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ClanNameChangeRequestView(APIView):
    serializer_class= serializers.ClanNameChangeRequestSerializer

    def get_clan(self, id):
        clan= Clan.objects.filter(id=id).first()
        if not clan:
            return None
        return clan
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            clan= self.get_clan(serializer.validated_data["clan"].id)
            if clan is None:
                return Response({"detail": f"Clan with id {id} not found."}, status=status.HTTP_400_BAD_REQUEST)
            if clan.clan_admin != request.user:
                return Response({"detail": f"Permission denied. Not  a clan admin"}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(clan_owner=request.user)
            return Response({"detail":"Request successful."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ClanMemeberRemoverRequest(APIView):
    serializer_class= serializers.ClanMemeberRemoverRequestSerializer

    def get_clan(self, id):
        clan= Clan.objects.filter(id=id).first()
        if not clan:
            return None
        return clan
    
    def get_clan_members(self, id):
        clan_member= Clan.objects.filter(member=id).first()
        if not clan_member:
            return None
        return clan_member
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            clan= self.get_clan(serializer.validated_data["clan"].id)
            if clan is None:
                return Response({"detail": f"Clan with id {id} not found."}, status=status.HTTP_400_BAD_REQUEST)
            if clan.clan_admin != request.user:
                return Response({"detail": f"Permission denied. Not  a clan admin"}, status=status.HTTP_400_BAD_REQUEST)
            clan_member = self.get_clan_members(serializer.validated_data["clan_member_to_remove"].id)
            if clan_member is None:
                return Response({"detail": f"Member is not part of the clan."}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(clan_owner=request.user)
            return Response({"detail":"Request successful."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TradingDays(APIView):
    def get(self, request):
    
        portfolio = CompetitionPortfolio.objects.filter(competition__status='current', user=request.user,  active=True).first()
        if not portfolio:
            return Response({"trading_days": []})

        positions = portfolio.composition.all()
        valid_positions = [position for position in positions if position.updated - position.created >= timedelta(minutes=5) and position.status=='close']
        
        days = [position.updated.date() for position in valid_positions]
        
        return Response({"trading_days": days})

class SupportTradingDays(APIView):
    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"trading_days": []})
    
        portfolio = CompetitionPortfolio.objects.filter(competition__status='current', user=user,  active=True).first()
        if not portfolio:
            return Response({"trading_days": []})

        positions = portfolio.composition.all()
        valid_positions = [position for position in positions if position.updated - position.created >= timedelta(minutes=5) and position.status=='close']
        
        days = [position.updated.date() for position in valid_positions]
        
        return Response({"trading_days": days})

class SupportClandetails(APIView):
    serializer_class= serializers.ClanSerializer

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])

        try:
            clan=  Clan.objects.get(member=user)
        except Clan.DoesNotExist:
            clan=  Clan.objects.filter(clan_admin=user).first()
            if not clan:
                return Response([])
            
        serializer = self.serializer_class(clan)
        return Response(serializer.data)

class JoinClanRequestView(APIView):
    serializer_class =  serializers.JoinClanRequestSerializers
    queryset = JoinClanRequest.objects.all()

    def get(self, request):
        clan_id=request.GET.get('clan_id')
        is_admin = Clan.objects.filter(clan_admin=request.user).exists()
        if not clan_id:
            # return all join requests
            join_request=JoinClanRequest.objects.filter(clan__clan_admin=request.user,approved='pending')
            serializer = self.serializer_class(join_request, many=True)
            return Response([{'admin':is_admin}, serializer.data])
        # Filter by clan_id
        join_request=JoinClanRequest.objects.filter(clan__id=clan_id)
        serializer = self.serializer_class(join_request, many=True)
        return Response([{'admin':is_admin}, serializer.data])

    def post(self, request):
        
        id=request.data.get('clan_id')
        clan= Clan.objects.get(id=id)
        is_member = Clan.objects.filter(member=request.user).first()
        is_admin = Clan.objects.filter(clan_admin=request.user).first()
        # print(is_member)
        if is_member or is_admin:
            return Response({'message':'You belong to another clan, you can only belong to one clan at a time'},status=status.HTTP_400_BAD_REQUEST)
        join_request = JoinClanRequest.objects.create(user=request.user, clan=clan)
        data = {
            'user': join_request.user.id,
            'clan': join_request.clan.id,
        }
        # Send clan admin a membership notifcation
        # save_and_send_notification(join_request.user.id,f"Your request to join clan {clan.clan_name} has been sent and awaiting the clan admin approval")
        # save_and_send_notification(join_request.clan.clan_admin.id,f"{request.user.firstname} {request.user.lastname} wants to join your clan.")
        # mail=sendMail("competition/joinClanRequest.html","Join a Clan (Request)",[request.user.email],{"first_name":request.user.firstname, "clan_name":clan.clan_name})

        # # send mail to clan admin to review request
        # mail=sendMail("competition/notifyClanAdminJoinClanRequest.html","Review and Approve 'Request to Join clan'",[clan.clan_admin.email],{"first_name":join_request.user.firstname})
        serializer = self.serializer_class(data=data)
        if serializer.is_valid():
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def put(self, request):
        request_id = request.data.get('request_id')
        action = request.data.get('action')
        valid_actions = ['pending', 'approved', 'rejected', 'leave', 'remove', "withdraw"]

        if not all([request_id, action]) or action not in valid_actions:
            return Response({"detail": f"Invalid request parameters or action value {valid_actions}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            join_request = JoinClanRequest.objects.get(id=request_id)
        except JoinClanRequest.DoesNotExist:
            return Response({"detail": "Request instance not found"}, status=status.HTTP_404_NOT_FOUND)
        join_request.approved = action
        join_request.save()
        # account = CompetitionPortfolio.objects.filter(competition__status='current', user_account__user=join_request.user).first()
        account= join_request.user
        if join_request.approved == 'approved':
            join_request.clan.member.add(account)
            # Send the clan member a notfication
            save_and_send_notification(join_request.user.id, f"Your membership request has been approved by the admin of {join_request.clan.clan_name}")
            mail=sendMail("competition/joinClanApproved.html","Join a Clan (Approved)",[join_request.user.email],{"first_name":join_request.user.firstname, "clan_name":join_request.clan.clan_name})
        elif join_request.approved in ['leave', 'remove']:
            join_request.clan.member.remove(account)
            # Send the clan member a notfication
            save_and_send_notification(join_request.user.id, f"You have been removed from {join_request.clan.clan_name} clan by the clan admin.")
        elif join_request.approved == "rejected":
            # Send the clan member a notfication
            save_and_send_notification(join_request.user.id, f"Your clan join request to {join_request.clan.clan_name.title()} has been rejected.")
            mail=sendMail("competition/joinClanRejected.html","Join a Clan (Rejected)",[join_request.user.email],{"first_name":join_request.user.firstname, "clan_name":join_request.clan.clan_name})
        elif action == "withdraw":
            # Trader wants to withdraw his request
            admin=join_request.clan.clan_admin.id #save admin id before delete
            join_request.delete()
            save_and_send_notification(admin,f"{request.user.firstname} {request.user.lastname} has just withdrawn his join request.")# notify the admin
            save_and_send_notification(request.user.id,f"You have successfully withdrawn your request to join {join_request.clan.clan_name.title()}")# notify the admin
            return Response({"detail":"Join request withdrawn successfully."})
        serializer = self.serializer_class(join_request)
        clan_serializer = serializers.ClanSerializer(join_request.clan, many=False)
        return Response({'join_request':serializer.data, 'clan':clan_serializer.data}, status=status.HTTP_200_OK)

class SupportJoinClanRequestView(APIView):
    serializer_class =  serializers.JoinClanRequestSerializers
    queryset = JoinClanRequest.objects.all()

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        is_admin = Clan.objects.filter(clan_admin=user)
        if not is_admin.exists():
            return Response([])
        # Filter by clan_id
        join_request=JoinClanRequest.objects.filter(clan=is_admin.first())
        print(join_request)
        serializer = self.serializer_class(join_request, many=True)
        return Response([{'admin':is_admin.exists()}, serializer.data])

class CanJoin(APIView):
    def get(self, request):
    
        pending_create = CreateClanRequest.objects.filter(clan_admin=request.user, approved='pending').first()
        three_days_ago = timezone.now() - timezone.timedelta(days=3)

        pending_join = JoinClanRequest.objects.filter(user=request.user, approved='pending').first()
        is_admin = Clan.objects.filter(clan_admin=request.user)
        is_member = Clan.objects.filter(member=request.user)
        
        if pending_join:
            if pending_join.date_request < three_days_ago:
                pending_join.approved = 'rejected'
                pending_join.save()
                save_and_send_notification(request.user.id, f"Your request to join {pending_join.clan.clan_name.title()} has been autodenied as it is more than 72 hours without action from clan admin.")
                save_and_send_notification(pending_join.clan.clan_admin.id, f"Join request for {pending_join.user_name} has been autodenied as it is more than 72 hours without action from your end.")
        
        pending_join1 = JoinClanRequest.objects.filter(user=request.user, approved='pending').first()
        if pending_create:
            serializerr2= serializers.CreateClanSerializer(pending_create)
            return Response({'status':False, 
                             'reason':'has a pending clan creation request',
                             'request_info':serializerr2.data,
                              'clan_id':""
                              })
                            
        elif pending_join1:
            serializerr= serializers.ClanSerializer(pending_join1.clan)
            return Response({'status':False, 
                             'reason':'has a pending clan join request',
                             'join_id':pending_join1.id,
                             'request_info':serializerr.data,
                             'clan_id':""
                             })
        elif is_admin or is_member:
            return Response({'status':False, 
                             'reason':'is an admin or member of a clan already',
                             'join_id':"",
                             'request_info':{},
                             'clan_id':is_admin.first().id if is_admin else is_member.first().id
                             })
        else:
            return Response({'status':True, 'reason':'no request'})
            

class CreateClanRequestView(APIView):
    queryset = CreateClanRequest.objects.all()
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        admin=request.user
        logo=request.data.get('clan_logo')
        link=request.data.get('community_link')
        name=request.data.get('clan_name').title()
        description = request.data.get('description')
        is_member = Clan.objects.filter(member=request.user).first()
        is_admin = Clan.objects.filter(clan_admin=request.user).first()
        # print(is_member)
        if is_member or is_admin:
            return Response({'message':'You belong to another clan, you can only belong to one clan at a time'},status=status.HTTP_400_BAD_REQUEST)
        
        existing_clan = Clan.objects.filter(Q(clan_name__iexact=name) | Q(clan_name__icontains=name))
        if existing_clan:
            return Response({'message':'There is an existing clan with this name'},status=status.HTTP_400_BAD_REQUEST)
        
        join_request = CreateClanRequest.objects.create(clan_admin=admin,clan_logo=logo, clan_name=name,community_link=link, description=description)
        save_and_send_notification(admin.id, f"Your request to create a new clan {name} is pending. It will be attended to by Hamma Admin.")
        data = {
            'user': join_request.clan_admin.id,
            'clan': join_request.clan_name,
        }
        # send clan creaeRequest mail
        mail=sendMail("competition/createClanRequest.html","Create a Clan (Request)",[request.user.email],{"first_name":request.user.firstname, "clan_name":name})
       
        return Response(data)
    
    

class LeaveAClan(APIView):
    serializer_class =  serializers.ClanSerializer
    queryset = Clan.objects.all()

    def put(self, request, *args, **kwargs):
        clan_id=kwargs.get('clan_id')
        action = request.data.get('action')
        valid_actions = ['leave']
        try:
            clan = Clan.objects.get(id=clan_id)
        except Clan.DoesNotExist:
            return Response({"detail": "Instance not found"}, status=status.HTTP_404_NOT_FOUND)
        
        if action not in valid_actions:
            return Response({"detail": f"Invalid request parameters for leaving a clan use {valid_actions} instead."}, status=status.HTTP_400_BAD_REQUEST)

        if request.user == clan.clan_admin:
            return Response({"detail": 'Invalid operation for admin user'}, status=status.HTTP_400_BAD_REQUEST)
        # account = CompetitionPortfolio.objects.filter(competition__status='current', user_account__user=request.user).first()
        clan.member.remove(request.user)
        save_and_send_notification(clan.clan_admin.id, f"Clan member {request.user.firstname.title()} {request.user.lastname.title()} has just left your clan.")
        save_and_send_notification(request.user.id, f"You left {clan.clan_name} clan.")
        return Response({"detail": 'You have successfull left this clan'}, status=status.HTTP_200_OK)

class TransferAdmin(APIView):
    def put(self, request, *args, **kwargs):
        clan_id=kwargs.get('clan_id')
        new_admin_id=kwargs.get('new_admin_id')
        user= User.objects.get(id=new_admin_id)
        try:
            clan = Clan.objects.get(id=clan_id)
        except Clan.DoesNotExist:
            return Response({"detail": "Instance not found"}, status=status.HTTP_404_NOT_FOUND)
        
       
        if request.user != clan.clan_admin:
            return Response({"detail": 'Invalid operation for Non Admin'}, status=status.HTTP_400_BAD_REQUEST)
        if user not in clan.member.all():
            return Response({"detail": 'proposed new admin not a member of this clan'}, status=status.HTTP_400_BAD_REQUEST)
        clan.clan_admin = user
        clan.save()
        clan.member.add(request.user)
        clan.member.remove(user)
        save_and_send_notification(user.id, f"The Clan Admin post for clan {clan.clan_name.title()} has been transferred to you by {request.user.email}.")
        save_and_send_notification(request.user.id, f"You have transferred Clan Admin for clan {clan.clan_name.title()} to {user}")
        return Response({"detail": 'Admin transferred'}, status=status.HTTP_200_OK)


class ClanPayout(APIView):
    def post(self, request,*args, **kwargs):
        clan_id= request.query_params.get('clan_id')
        clan=Clan.objects.get(id=clan_id)
        payout=TopClanPayout.objects.create(clan=clan,paytype='Clan Payout',status='pending')
        return Response({'message':'Payout request made'})


class ClanMembers(APIView):
    serializer_class =  serializers.ClanSerializer
    queryset = Clan.objects.all()
    
    def get(self, request,*args, **kwargs):
        clan_id=kwargs.get('clan_id')
        try:
            clan = Clan.objects.get(id=clan_id)
        except Clan.DoesNotExist:
            return Response({"detail": f"Clan with id {clan_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        clan_members = clan.member.all()

        clan_member_data = []   
        if clan.clan_admin == request.user:
            clan_member_data.append({'admin':True})
            
        else:
            clan_member_data.append({'admin':False})
        clan_member_data.append({'members':[]})
        portfolio = CompetitionPortfolio.objects.filter(competition__status='current', user=clan.clan_admin).first()
        profile=Profile.objects.get(user=clan.clan_admin)
        if portfolio:
            profit,status = getProfit(portfolio)
            percent= round((profit/1000000) *100,2)
            
            
            data= {
                'name':portfolio.user.fullname,
                
                'profit':percent,
                'country':profile.country,
            }
        
        else:
            data={
                'name':f"{clan.clan_admin.firstname} {clan.clan_admin.lastname}" ,
                'profit':"",
                'country':profile.country,
            }
            
        clan_member_data[1]['members'].append(data)
        if clan_members:
            for member in clan_members:
                portfolio = CompetitionPortfolio.objects.filter(competition__status='current',user=member).first()
                profile1=Profile.objects.get(user=member)
                if portfolio:
                    profit,status = getProfit(portfolio)
                    percent= round(profit/1000000 *100,2)
                    
                    data= {
                        'member_id':member.id,
                        'name':portfolio.user.fullname,
                        'profit':percent,
                        'country':profile1.country,
                    }
                
                else:
                    data={
                        'member_id':member.id,
                        'name':f"{member.firstname} {member.lastname}" ,
                        'profit':"",
                        'country':profile1.country,
                    }
                    
                clan_member_data[1]['members'].append(data)

        return Response(clan_member_data)


    def put(self, request, *args, **kwargs):
        clan_id = kwargs.get('clan_id')
        member_id = request.data.get('member_id')
        action = request.data.get('action')
        print(action, member_id)
        
        valid_actions = ['remove']
        if action not in valid_actions or member_id is None:
            return Response({"detail": f"Invalid request parameters or action value {valid_actions} or missing member_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            clan = Clan.objects.get(id=clan_id)
        except Clan.DoesNotExist:
            return Response({"detail": "Clan not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user making the request is the clan admin
        if request.user != clan.clan_admin:
            return Response({"detail": 'Invalid operation for member'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the member to be removed exists
        # account = CompetitionPortfolio.objects.filter(id=member_id).first()
        account = User.objects.filter(id=member_id).first()
        if account:
            clan.member.remove(account)
            # Send the clan member a notfication
            save_and_send_notification(member_id, f"You have been removed from {clan.clan_name} clan by the clan admin.")
            return Response({"detail": 'Member has been successfully removed from the clan'}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": 'Member not found'}, status=status.HTTP_404_NOT_FOUND)


def getProfit(portfolio):
    positions = CompetitionPosition.objects.filter(portfolio=portfolio, status='close')
    # print(len(positions))
    if positions:
        profit = sum([position.profit_loss for position in positions])
        # print(profit)
        return profit, True
    else:
        return 0, False


# def calc_profit_days(number,days, acc_size):
#     from datetime import datetime, timedelta
    
#     max_time= datetime.utcnow() - timedelta(days=days)
#     updated=None
#     user_first_login = None
#     account = TradeAccount.objects.filter(number=number).last()
#     user_first_login = account.trader.first_login.login_time
#     updated = account.created
        
#     if user_first_login  and updated:
#         timestamp1 = max(user_first_login.timestamp(), updated.timestamp())
#     else:
#         timestamp1 = None 
#     records = get_records2(number,timestamp1,max_time.timestamp())
#     if records:
#         equ_list = []
#         for data in records:
#             equ_list.append(float(data["balance"]))
#         starting = float(acc_size)
#         profit = round((equ_list[-1] - starting) , 0)
#         return profit
# def cal_profit_percent(number,days,size,profit):
#     profit_days = calc_profit_days(number,days,size)
#     percent = round(((profit - profit_days)*100/profit_days),0)
#     return percent  
class LeaderBoardView(APIView):
    permission_classes = (AllowAny,)
    
    def get(self, request,*args, **kwargs):
        competition = Competition.objects.filter(status='current').first()
        if competition:
            if timezone.now() > competition.start_date:
                portfolio = CompetitionPortfolio.objects.filter(competition=competition, active=True)
                
                leaderboard_list=[]
                for account in portfolio:
                    profit,status = getProfit(account)
                    if status:
                        percent= round((profit/1000000)*100,2)
                        if percent >= -5:
                            profile= Profile.objects.get(user=account.user)
                            data= {
                                'name':account.user.firstname,
                                'profit':percent,
                                'profit_naira':profit,
                                'country':profile.country,
                                'clan':account.user.clans
                            }
                            leaderboard_list.append(data)
                sorted_data = sorted(leaderboard_list, key=lambda x: x['profit'], reverse=True)

                return Response(sorted_data)
            else:
                return Response([])
        else:
            return Response([])

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
@api_view(['GET',"POST"])
@permission_classes([AllowAny]) 
def testhtml(request):
    return render(request, 'leaderboard/clan-detail.html')



from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def leaderboard_view(request):
    # Filter by competition
    competitions=Competition.objects.filter(status='closed').order_by("-id")
    country = request.GET.get("country", None)
    old_competition_id = request.GET.get("filter", None)
    email = request.GET.get("email", None)
    clan_name = request.GET.get('clan_name', None)
    base_query = CompetitionPortfolio.objects.filter(competition__status='current',active=True)
    if clan_name:
        clan=Clan.objects.filter(clan_name__icontains=clan_name).first()
        if clan:
            base_query = base_query.filter(Q(user__in=clan.member.all()) | Q(user=clan.clan_admin) )
            # print(base_query)
    if country:
        base_query = base_query.filter(user__profile__country__icontains=country)
    if email:
        base_query = base_query.filter(user__email__icontains=email)
        
    if old_competition_id:
        base_query = CompetitionPortfolio.objects.filter(competition__id = old_competition_id)

    accounts = base_query
    # print(len(accounts))
    leaderboard_list=[]
    zero_profit_list = []
    for account in base_query:
        try:
            # print(account.id)
            clan=Clan.objects.filter(member=account.user)
            if not clan:
                raise Clan.DoesNotExist
        except Clan.DoesNotExist:
            clan=Clan.objects.filter(clan_admin=account.user)
        if clan:
            clan=clan.first()
            user_portfolio = base_query.filter(user=account.user).first()
            # print(user_portfolio.competition.title)
            profit,status = getProfit(user_portfolio)
            if status:
                
                percent= round((profit/1000000)*100,2)
                profile= Profile.objects.get(user=account.user)
                data= {
                    'id':user_portfolio.id,
                    'active':user_portfolio.active,
                    'name':user_portfolio.user.fullname,
                    'profit':percent,
                    'country':profile.country,
                    'clan':clan.clan_name
                }
            
                leaderboard_list.append(data)
                
    sorted_data = sorted(leaderboard_list, key=lambda x: x['profit'], reverse=True)
    print(sorted_data)
    leaderboard="show"
    pastLeaderboard="hide"
    q=request.GET.get("filter")
    past_data=[]
    if q :
        leaderboard="hide"
        pastLeaderboard="show"
        sorted_data=[]
        past_data=CompetitionSummary.objects.filter(competition__id=q).order_by("position")
    # print(sorted_data)
    current_comp =  Competition.objects.filter(status='current')
    if current_comp.exists() and timezone.now() > current_comp.first().start_date:
        return render(request, 'leaderboard/leaderboard.html', {'data':sorted_data, "competitions":competitions, "leaderboard":leaderboard, "pastLeaderboard":pastLeaderboard, "past_data":past_data})
    else:
        return render(request, 'leaderboard/leaderboard.html', {'data':[], "competitions":competitions, "leaderboard":leaderboard, "pastLeaderboard":pastLeaderboard, "past_data":past_data})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def edit_user(request, user_id):
    user = User.objects.get(id=user_id)
    if request.method == 'POST':
        user.firstname = request.POST.get('firstname')
        user.lastname = request.POST.get('lastname')
        user.save()
        return redirect('list-users')  # Redirect to appropriate page after editing
    return render(request, 'leaderboard/edit_user.html', {'user': user})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def list_users(request):
    users = User.objects.all().order_by('-date_joined')

    # Handling search functionality
    query = request.GET.get('search')
    if query:
        users = users.filter(
            Q(email__icontains=query) |
            Q(firstname__icontains=query) |
            Q(lastname__icontains=query)
        )

    # Paginate users list
    paginator = Paginator(users, 100)
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


    return render(request, 'leaderboard/list_users.html', {'users': users})


@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def current_competition_users(request,id):
    competition = Competition.objects.get(id=id)
    users = CompetitionPortfolio.objects.filter(competition=competition).order_by('-created')
    # users = [port.user for port in portfolio]

    # Handling search functionality
    query = request.GET.get('search')
    
    if query:
        users = CompetitionPortfolio.objects.filter(competition__status='current', user__email__icontains=query)
        # users = [port.user for port in portfolio]

        
    paginator = Paginator(users, 100)
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


    return render(request, 'leaderboard/current_competition_users.html', {'users': users, 'title':competition.title})


@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def clan_requests(request):
    if request.method == 'POST':
        request_id = request.POST.get('id')
        action = request.POST.get('action')

        try:
            request1 = CreateClanRequest.objects.get(pk=request_id)
            
        except CreateClanRequest.DoesNotExist:
            request1=None
        if request1:
            is_member = Clan.objects.filter(member=request1.clan_admin).first()
            is_admin = Clan.objects.filter(clan_admin=request1.clan_admin).first()
            if action=='approved' and not is_member and not is_admin:
                Clan.objects.create(clan_admin=request1.clan_admin,clan_logo=request1.clan_logo,clan_name=request1.clan_name,
                                    community_link=request1.community_link,description=request1.description)
                request1.approved='approved'
                request1.save()
                save_and_send_notification(request1.clan_admin.id, f"Your clan {request1.clan_name.title()} creation request has been approved, You are the clan admin")
                mail=sendMail("competition/CreateClanApproved.html","Create a Clan (Approved)",[request1.clan_admin.email],{"first_name":request1.clan_admin.firstname, "clan_name":request1.clan_name})
        
            elif action=='rejected':
                reason=request.POST.get("reason")

                request1.approved='rejected'
                request1.reason=reason
                request1.save()
                save_and_send_notification(request1.clan_admin.id, f"Your clan {request1.clan_name.title()} creation request has been rejected. Reason: {reason}")
                mail=sendMail("competition/CreateClanRejected.html","Create a Clan (Rejected)",[request1.clan_admin.email],{"first_name":request1.clan_admin.firstname, "clan_name":request1.clan_name, "reasons":reason})
                
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return HttpResponseRedirect(referer)
    q=request.GET.get("filter")
    if q:
        clans = CreateClanRequest.objects.filter(clan_admin__email=q).order_by('-id')
        return render(request,'leaderboard/requests.html',{'clans':clans})
    clans = CreateClanRequest.objects.filter(approved='pending').order_by('-id')
    return render(request,'leaderboard/requests.html',{'clans':clans})


class ClanRequestsAPIView(APIView):
    def post(self, request, *args, **kwargs):
        request_id = request.data.get('id')
        action = request.data.get('action')

        try:
            request1 = CreateClanRequest.objects.get(pk=request_id)
        except CreateClanRequest.DoesNotExist:
            return Response({"error": "Request does not exist"}, status=status.HTTP_404_NOT_FOUND)

        if action == 'approved':
            is_member = Clan.objects.filter(member=request1.clan_admin).first()
            is_admin = Clan.objects.filter(clan_admin=request1.clan_admin).first()
            if not is_member and not is_admin:
                Clan.objects.create(clan_admin=request1.clan_admin, clan_logo=request1.clan_logo,
                                    clan_name=request1.clan_name, community_link=request1.community_link,
                                    description=request1.description)
                request1.approved = 'approved'
                request1.save()
                save_and_send_notification(request1.clan_admin.id,
                                           f"Your clan {request1.clan_name.title()} creation request has been approved, You are the clan admin.")
                return Response({"message": "Clan creation request approved"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "User is already a member or admin of another clan"}, status=status.HTTP_400_BAD_REQUEST)

        elif action == 'rejected':
            reason = request.data.get("reason")
            request1.approved = 'rejected'
            request1.reason = reason
            request1.save()
            save_and_send_notification(request1.clan_admin.id,
                                       f"Your clan {request1.clan_name.title()} creation request has been rejected. Reason: {reason}")
            return Response({"message": "Clan creation request rejected"}, status=status.HTTP_200_OK)

        return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        q = request.query_params.get("filter")
        if q:
            clans = CreateClanRequest.objects.filter(clan_admin__email=q).order_by('-id')
            serializer = serializers.CreateClanRequestSerializer(clans, many=True)
            return Response(serializer.data, safe=False)
        else:
            clans = CreateClanRequest.objects.filter(approved='pending').order_by('-id')
            serializer = serializers.CreateClanRequestSerializer(clans, many=True)
            return Response(serializer.data, safe=False)


@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def clan_list(request):

    q=request.GET.get("filter")
    if q:
        clans = Clan.objects.filter(clan_name__icontains=q)
        return render(request,'leaderboard/clan_list.html',{'clans':clans})

    clans = Clan.objects.all()
    return render(request,'leaderboard/clan_list.html',{'clans':clans})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def clan_detail(request,pk):
    clan = Clan.objects.get(id=pk)
    memebers= clan.member.all() 
    q=request.GET.get("filter")
    
    if q:
        memeber= memebers.filter(email=q)
        # print(memeber, "Heloo")
        if memeber:
            member_list = []
            for mem in memeber:
                member_list.append(mem)
            
            return render(request,'leaderboard/clan-detail.html',{'count':memebers.count()+1,'accounts':member_list,'clan':clan})
    member_list = []
    member_list.append(clan.clan_admin)
    for mem in memebers:
        member_list.append(mem)
    
    return render(request,'leaderboard/clan-detail.html',{'count':memebers.count()+1,'accounts':member_list,'clan':clan})
    
    # competition = Competition
    # if q:
    #     memeber= clan.member.filter(email=q)
    #     # print(memeber, "Heloo")
    #     if memeber:
    #         accounts = CompetitionPortfolio.objects.filter(user__in=memeber, competition__status='current')
    #         total_profits = sum(account.profit for account in accounts )
    #         account_list = [{'user':account.portfolio.user, 'profit':account.profit } for account in accounts]
    #         return render(request,'leaderboard/clan-detail.html',{'count':memebers.count()+1,'accounts':account_list,'clan':clan, 'total_profits':total_profits})
    # if memebers:
    #     accounts1 = CompetitionPortfolio.objects.filter(user__in=memebers, competition__status='current') 
    #     accounts2 = CompetitionPortfolio.objects.filter(user=clan.clan_admin, competition__status='current')
        
    #     # accounts = (accounts1 | accounts2).distinct('user').annotate(last_portfolio=Max('created'))
    #     accounts = (accounts1 | accounts2)
    #     if accounts:
    #         total_profits = sum(account.profit for account in accounts )/len(accounts)
    #         account_list = [{'user':account.portfolio.user, 'profit':account.profit } for account in accounts]
            
    #         return render(request,'leaderboard/clan-detail.html',{'count':memebers.count() +1,'accounts':account_list,'clan':clan, 'total_profits':total_profits})
            
    #     else:
    #         total_profits = 0
        
    # else:
        
    #     accounts= CompetitionPortfolio.objects.filter(user=clan.clan_admin, competition__status='current')
    #     total_profits = sum(account.profit for account in accounts )
    #     account_list = [{'user':account.portfolio.user, 'profit':account.profit } for account in accounts]
        
    #     return render(request,'leaderboard/clan-detail.html',{'count':1,'accounts':account_list,'clan':clan, 'total_profits':total_profits})


@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def edit_clan(request, pk):
    clan = get_object_or_404(Clan, id=pk)
    if request.method == 'POST':
        if request.POST.get('clan_name'):
            clan.clan_name = request.POST.get('clan_name')
        if request.POST.get('description'):
            clan.description = request.POST.get('description')
        if request.POST.get('community_link'):
            clan.community_link = request.POST.get('community_link')
        if request.FILES.get('clan_logo'):
            clan.clan_logo = request.FILES.get('clan_logo')
        clan.save()
        return redirect('clan-details', pk=clan.id)
    return render(request, 'leaderboard/edit_clan.html', {'clan': clan})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def delete_clan(request, pk):
    clan = get_object_or_404(Clan, id=pk)
    if request.method == 'POST':
        clan.delete()
        return redirect('leaderboard')
    return render(request, 'leaderboard/delete_clan.html', {'clan': clan})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def clan_payout(request):
    q=request.GET.get("filter")
    if q:
        payouts= TopClanPayout.objects.filter(status__icontains=q)
        return render(request, 'leaderboard/clanpayout.html',{'payouts':payouts})
    payouts= TopClanPayout.objects.all().order_by('-id')
    return render(request, 'leaderboard/clanpayout.html',{'payouts':payouts})


@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def all_trader(request):
    accounts = CompetitionPortfolio.objects.filter(competition__status='current')
    return render(request, 'leaderboard/traders.html', {'accounts':accounts})

@login_required
def clan_payout_detail(request,payout_id):
    if request.method =="POST":
        status=request.POST.get("status",None)
        amount=request.POST.get("amount",None)
        comment=request.POST.get("comment",None)
        id=request.POST.get("id")
        print(status, amount, id, "HELJSDJFHSKJ")
        payout=TopClanMembersPayout.objects.get(id=id)
        payout.status=status
        payout.amount=amount
        payout.comment=comment
        payout.save()
        # print(payout.status)
        if comment:
            save_and_send_notification(payout.user.id,f"Top Clan Payout: {comment}")
    top_clan_payout=TopClanPayout.objects.get(id=payout_id)
    payouts=TopClanMembersPayout.objects.filter(top_clan_payout=top_clan_payout)
    q=request.GET.get("filter")
    if q:
        competition_details = TopClanMembersPayout.objects.filter(user__email=q,top_clan_payout=top_clan_payout)
        return render(request, 'leaderboard/clan-payout-detail.html',{'payouts':competition_details,'clan_name':top_clan_payout.clan.clan_name, 'competition':top_clan_payout.competition.title.title()})

    # competition_details = CompetitionSummary.objects.filter(clan=clan, competition=competition)
    return render(request, 'leaderboard/clan-payout-detail.html',{'payouts':payouts,'clan_name':top_clan_payout.clan.clan_name, 'competition':top_clan_payout.competition.title.title()})
    

@login_required
def trader_payout(request):
    payouts=TopTraderPayout.objects.all().order_by('-id')
    if request.method =="POST":
        status=request.POST.get("status",None)
        amount=request.POST.get("amount",None)
        comment=request.POST.get("comment",None)
        id=request.POST.get("id")
        print(status, amount, id, "HELJSDJFHSKJ")
        payout=TopTraderPayout.objects.get(id=id)
        payout.status=status
        payout.amount=amount
        payout.comment=comment
        payout.save()
        # print(payout.status)
        if comment:
            save_and_send_notification(payout.useracc.user.id,f"Top Trader Payout: {comment}")
    q=request.GET.get("filter")
    if q:
        payouts=TopTraderPayout.objects.filter(status__icontains=q).order_by('-id')
        return render(request,'leaderboard/trader-payout.html',{'payouts':payouts})
    return render(request,'leaderboard/trader-payout.html',{'payouts':payouts})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def create_competition(request):
    # import timezone
    # Create_competiton_summary()
    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        title = request.POST.get('title')
        first_prize = request.POST.get('first_prize')
        # second_prize = request.POST.get('second_prize')
        # third_prize = request.POST.get('third_prize')
        # status = request.POST.get('status')
        message = request.POST.get('notification')
        currents = Competition.objects.filter(status='current')
        if currents:
            for current in currents:
                current.status='closed'
                current.save()
        start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M'), timezone.get_current_timezone())
        end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M'), timezone.get_current_timezone())
        Competition.objects.create(
            start_date=start_date,
            end_date=end_date,
            title=title,
            first_prize=first_prize,
            # second_prize=second_prize,
            # third_prize=third_prize,
            status='current',
            message=message
        )
        return redirect('competition_list')
    return render(request, 'leaderboard/create.html')

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def competition_list(request):
    q=request.GET.get("filter")
    portfolio=CompetitionPortfolio.objects.filter(competition__status='current', user=request.user)
    if portfolio.exists():
        active = True
    else:
        active = False
    if q:
        competitions = Competition.objects.filter(status__icontains=q).order_by('-id')
        return render(request, 'leaderboard/competition_list.html', {'competitions':competitions, 'active':active})

    competitions = Competition.objects.all().order_by('-id')
    return render(request, 'leaderboard/competition_list.html', {'competitions':competitions, 'active':active})
# # For API
class CompetitionSummaryView(APIView):
    serializer_class =  serializers.CompetitionSummarySerializer
    queryset = CompetitionSummary.objects.all()

    def get(self, request,*args, **kwargs):
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        summary=competition_id.competitionsummary_set.all().order_by("-profit")
        serializer= self.serializer_class(summary, many=True)
        return Response(serializer.data)
# For API

class CompetitionSummaryViewForClan(APIView):
    serializer_class =  serializers.CompetitionSummarySerializer
    queryset = CompetitionSummary.objects.all()

    def get(self, request,*args, **kwargs):
        
        competition_id = Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail": "Competition with this ID not found"}, status=status.HTTP_404_NOT_FOUND)

        clan_id = request.data.get("clan_id")
        print("Heloooo")
        summary = competition_id.competitionsummary_set.filter(clan__id=clan_id).order_by("-profit")
        serializer = self.serializer_class(summary, many=True)

        return Response(serializer.data)


class TopTraderPayoutRequest(APIView):
    serializer_class =  serializers.CompetitionSummarySerializer
    queryset = CompetitionSummary.objects.all()

    def get(self, request,*args, **kwargs):
        
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        # Prevent others from making request for another trader's payout
        user_acc=CompetitionSummary.objects.filter(competition=competition_id, user=request.user).first()
        
        if not user_acc:
            return Response({"detail": "Account not found. Your account didn't make it to the end of competition."}, status=status.HTTP_404_NOT_FOUND)
        # Get all the profits and prevents duplicates using set
        trading_days = count_business_days(competition_id.start_date, competition_id.end_date)
        
        top_3= CompetitionSummary.objects.filter(competition=competition_id,trading_days__gte=trading_days).order_by('position')[:1]
        # top_3=[account.user_account for account in top_]
        
        trading_days = count_business_days(competition_id.start_date, competition_id.end_date)
        
        has_pending_request=TopTraderPayout.objects.filter( 
            portfolio=user_acc.portfolio,
            status="pending",
            competition=competition_id).first()
        if has_pending_request:
                return Response({'status':False, 'reason': 'has pending payout request' },status=status.HTTP_200_OK)
        desired_time = time(12, 0)
        wat_timezone = pytz.timezone('Africa/Lagos')
        #print(wat_timezone, "timeeeee")
        current_time_wat = datetime.now(wat_timezone)
        is_friday = current_time_wat.weekday() == 4  # 4 represents Friday
        is_after_12pm_wat = current_time_wat.time() > desired_time
        is_weekend = datetime.now().weekday() > 5
        requested_today= TopTraderPayoutButtonShows.objects.filter(portfolio=user_acc.portfolio, paydate = datetime.now().date()).exists()
        if (is_friday and is_after_12pm_wat) or is_weekend:
                return Response({'status':False, 'reason': 'Can only request mon-fri 12pm' },status=status.HTTP_200_OK)
            
        if user_acc not in top_3:
            return Response({'status':False, 'reason': 'Ineligible' },status=status.HTTP_200_OK)
        
        return Response({'status':True, 'reason': '' })
    def post(self, request,*args, **kwargs):
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        # prize = {
        #     '1':competition_id.first_prize,
        #     '2': competition_id.second_prize,
        #     '3':competition_id.third_prize
        # }
        user_acc=CompetitionSummary.objects.filter(competition=competition_id, user=request.user).first()
        top_trader_payout=TopTraderPayout.objects.create( 
            portfolio=user_acc.portfolio,
            date=datetime.now().date(),
            status="pending",
            paytype="Top Trader Payout",
            competition=competition_id,
            profit=user_acc.profit,
            amount=competition_id.first_prize,
            position=user_acc.position)
        save_and_send_notification(request.user.id, f"You have requested for Top Trader Prize payout in the '{competition_id.title.title()}' competition")
        TopTraderPayoutButtonShows.objects.create(portfolio=user_acc.portfolio)
        TopTraderPayoutImg.objects.create(payout=top_trader_payout)
        # send_top_trader_payment_processing_mail(request.user.email)
        return Response({"detail":"Request sent"})

class SupportTopTraderPayoutRequest(APIView):
    serializer_class =  serializers.CompetitionSummarySerializer
    queryset = CompetitionSummary.objects.all()

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        # Prevent others from making request for another trader's payout
        user_acc=CompetitionSummary.objects.filter(competition=competition_id, user=user).first()
        
        if not user_acc:
            return Response({"detail": "Account not found. Your account didn't make it to the end of competition."}, status=status.HTTP_404_NOT_FOUND)
        # Get all the profits and prevents duplicates using set
        trading_days = count_business_days(competition_id.start_date, competition_id.end_date)
        
        top_3= CompetitionSummary.objects.filter(competition=competition_id,trading_days__gte=trading_days).order_by('position')[:1]
        # top_3=[account.user_account for account in top_]
        
        trading_days = count_business_days(competition_id.start_date, competition_id.end_date)
        
        has_pending_request=TopTraderPayout.objects.filter( 
            portfolio=user_acc.portfolio,
            status="pending",
            competition=competition_id).first()
        if has_pending_request:
                return Response({'status':False, 'reason': 'has pending payout request' },status=status.HTTP_200_OK)
        desired_time = time(12, 0)
        wat_timezone = pytz.timezone('Africa/Lagos')
        #print(wat_timezone, "timeeeee")
        current_time_wat = datetime.now(wat_timezone)
        is_friday = current_time_wat.weekday() == 4  # 4 represents Friday
        is_after_12pm_wat = current_time_wat.time() > desired_time
        is_weekend = datetime.now().weekday() > 5
        requested_today= TopTraderPayoutButtonShows.objects.filter(portfolio=user_acc.portfolio, paydate = datetime.now().date()).exists()
        if (is_friday and is_after_12pm_wat) or is_weekend:
                return Response({'status':False, 'reason': 'Can only request mon-fri 12pm' },status=status.HTTP_200_OK)
            
        if user_acc not in top_3:
            return Response({'status':False, 'reason': 'Ineligible' },status=status.HTTP_200_OK)
        
        return Response({'status':True, 'reason': '' })

    
class TopClanPayoutRequest(APIView):
    serializer_class =  serializers.CompetitionSummarySerializer
    queryset = ClanCompetitionSummary.objects.all()

    def get(self, request,*args, **kwargs):
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        # Prevent others from making request for another trader's payout
        try:
            clan=Clan.objects.get(clan_admin=request.user)
        except Clan.DoesNotExist:
            clan=None
            return Response({'status':False, 'reason': 'Ineligible' }, status=status.HTTP_200_OK)
        if clan:
            top_3 = [summary.clan for summary in ClanCompetitionSummary.objects.filter(competition=competition_id).order_by('position')[:3]]
        
            has_pending_request=TopClanPayout.objects.filter( 
                clan__clan_admin=request.user,
                status="pending",
                competition=competition_id).first()
            if has_pending_request:
                return Response({'status':False, 'reason': 'has pending payout request' },status=status.HTTP_200_OK)
            desired_time = time(12, 0)
            wat_timezone = pytz.timezone('Africa/Lagos')
            #print(wat_timezone, "timeeeee")
            current_time_wat = datetime.now(wat_timezone)
            is_friday = current_time_wat.weekday() == 4  # 4 represents Friday
            is_after_12pm_wat = current_time_wat.time() > desired_time
            is_weekend = datetime.now().weekday() > 5
            requested_today= TopClanPayoutButtonShows.objects.filter(clan=clan, paydate = datetime.now().date()).exists()

            if (is_friday and is_after_12pm_wat) or is_weekend:
                return Response({'status':False, 'reason': 'Can only request mon-fri 12pm' },status=status.HTTP_200_OK)
            
            if clan not in top_3:
                return Response({'status':False, 'reason': 'Ineligible' },status=status.HTTP_200_OK)
        
            return Response({'status':True, 'reason': '' })
        
    def post(self, request,*args, **kwargs):
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        # user_acc=CompetitionPortfolio.objects.filter(competition=competition_id, user=request.user).first()
        clan=Clan.objects.filter(clan_admin=request.user).first()
        summary = ClanCompetitionSummary.objects.filter(competition=competition_id,clan=clan).first()
        top_clan_payout=TopClanPayout.objects.create( 
            clan=clan,
            date=datetime.now().date(),
            status="pending",
            paytype="Clan Payout",
            profit=summary.profit,
            competition=competition_id,
            position=summary.position)
        TopClanPayoutButtonShows.objects.create(clan=clan)
        TopClanPayoutImg.objects.create(payout=top_clan_payout)
        
        comp_summary = CompetitionSummary.objects.filter(competition=competition_id,clan=clan)
        for summary in comp_summary:
            tcmp=TopClanMembersPayout.objects.create(top_clan_payout=top_clan_payout,user=summary.user,portfolio=summary.portfolio)
            TopClanMembersPayoutImg.objects.create(payout=tcmp)
            
            save_and_send_notification(summary.user.id, f"Clan admin has requested for Top Clan Prize Payout in '{competition_id.title.title()}' competition.")

        # send_top_clan_payment_processing_mail(request.user.email)
        return Response({"detail":"Request sent"})
        
class SupportTopClanPayoutRequest(APIView):
    serializer_class =  serializers.CompetitionSummarySerializer
    queryset = ClanCompetitionSummary.objects.all()

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        competition_id=Competition.objects.filter(id=kwargs.get("competition_id")).first()
        if not competition_id:
            return Response({"detail":"competiton with this ID not found"}, status=status.HTTP_404_NOT_FOUND)
        # Prevent others from making request for another trader's payout
        try:
            clan=Clan.objects.get(clan_admin=user)
        except Clan.DoesNotExist:
            clan=None
            return Response({'status':False, 'reason': 'Ineligible' }, status=status.HTTP_200_OK)
        if clan:
            top_3 = [summary.clan for summary in ClanCompetitionSummary.objects.filter(competition=competition_id).order_by('position')[:3]]
        
            has_pending_request=TopClanPayout.objects.filter( 
                clan__clan_admin=user,
                status="pending",
                competition=competition_id).first()
            if has_pending_request:
                return Response({'status':False, 'reason': 'has pending payout request' },status=status.HTTP_200_OK)
            desired_time = time(12, 0)
            wat_timezone = pytz.timezone('Africa/Lagos')
            #print(wat_timezone, "timeeeee")
            current_time_wat = datetime.now(wat_timezone)
            is_friday = current_time_wat.weekday() == 4  # 4 represents Friday
            is_after_12pm_wat = current_time_wat.time() > desired_time
            is_weekend = datetime.now().weekday() > 5
            requested_today= TopClanPayoutButtonShows.objects.filter(clan=clan, paydate = datetime.now().date()).exists()

            if (is_friday and is_after_12pm_wat) or is_weekend:
                return Response({'status':False, 'reason': 'Can only request mon-fri 12pm' },status=status.HTTP_200_OK)
            
            if clan not in top_3:
                return Response({'status':False, 'reason': 'Ineligible' },status=status.HTTP_200_OK)
        
            return Response({'status':True, 'reason': '' })


def Create_competiton_summary(competition):
    portfolios = CompetitionPortfolio.objects.filter(competition=competition, active=True)
    
    for portfolio in portfolios:
        try:
            clan = Clan.objects.filter(member=portfolio.user).first()
            if not clan:
                raise Clan.DoesNotExist
        except Clan.DoesNotExist:
            clan = Clan.objects.filter(clan_admin=portfolio.user).first()
        
        profit,status = getProfit(portfolio)
        if status:
            percent = round(profit / 1000000 * 100, 2)
            
            # Use the single `portfolio` instance here
            CompetitionSummary.objects.create(portfolio=portfolio, clan=clan, user=portfolio.user, profit=percent, competition=competition)
    
    # close the competition after the loop is completed
    competition.status = "closed"
    competition.save()


from django.db.models import Sum, Avg
from django.db.models.expressions import Window,F 
from django.db.models.functions import Rank

def rank_clans(competition):
    # Group by clans and annotate the total profit for each clan
    competition_summary= CompetitionSummary.objects.filter(competition=competition).exclude(profit=0)
    clan_profit_summary = (competition_summary.values('clan')
        # .annotate(total_profit=Sum('profit'))
        # .order_by('-total_profit')  # Order by total profit in descending order
        .annotate(average_profit=Avg('profit'))
        .order_by('-average_profit')  # Ord
    )
    # print(clan_profit_summary)
    # Add rank to each clan based on total profit
    clan_summary = clan_profit_summary.annotate(
        rank=Window(expression=Rank(), order_by=F('average_profit').desc())
    )
    # print(clan_summary)
    for summary in clan_summary:
        ClanCompetitionSummary.objects.create(
            competition=competition,
            clan_id=summary['clan'],
            profit=summary['average_profit'],
            position=summary['rank']
        )
    return clan_summary

 
def rank_traders(competition): 
    from django.db.models import F, Window 
    from django.db.models.functions import Rank
    summary = CompetitionSummary.objects.filter(competition=competition).exclude(profit=0)
    # Use the Window expression to rank the objects by profit 
    summary = summary.annotate( rank=Window( expression=Rank(), order_by=F('profit').desc() ) ) 
    # Update the position field with the rank value 
    for obj in summary: 
        obj.position = obj.rank 
        obj.save() 
    return summary

class PayoutHistory(APIView):
    def get(self, request,*args, **kwargs):
        history = TopTraderPayout.objects.filter(portfolio__user=request.user)
        serializer=serializers.TraderPayoutSerializer(history, many=True)
        return Response(serializer.data)
    
class SupportPayoutHistory(APIView):
    
    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response([])
        
        history = TopTraderPayout.objects.filter(portfolio__user=user)
        serializer=serializers.TraderPayoutSerializer(history, many=True)
        return Response(serializer.data)
    
@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def competition_list_for_top_trader_payout(request):
    competitions = Competition.objects.all().order_by('-id')
    return render(request, 'leaderboard/competition_list_for_top_trader_payout.html', {'competitions':competitions})

class GetAndUpdateUserNotifications(APIView):
    def get(self, request):
        user_id=request.user.id
        notifications=get_notifications(user_id)
        return Response(notifications)

    def put(self, request):
        user_id=request.user.id
        notifications_ids=request.data.get('id')
        for id in notifications_ids:
            update=update_notification(user_id,id)
            # print(id["id"], "Helooooo",user_id,update)
        return Response({"detail":"Success"})
        # update_notification

# from collections import defaultdict
# class TopClans(APIView):
#     permission_classes = (AllowAny,)
#     def get(self, request):
#         competition =  Competition.objects.filter(status='current')
#         if competition.exists() and  timezone.now() > competition.first().start_date:
#                 portfolio = CompetitionPortfolio.objects.filter(competition=competition.first(), active=True)
                
#                 leaderboard_list=[]
                
#                 clan_profits = defaultdict(float)
#                 clan_member_counts = defaultdict(int)
                
#                 for account in portfolio:
                    
#                     profit,status = getProfit(account)
#                     if status:
#                         percent= round((profit/1000000)*100,2)
#                         profile= Profile.objects.get(user=account.user)
#                         clan=account.user.clans
#                         data= {
#                             'name':account.user.firstname,
#                             'profit':percent,
#                             'profit_naira':profit,
#                             'country':profile.country,
#                             'clan':clan
#                         }
#                         leaderboard_list.append(data)
#                         clan_profits[clan] += percent
#                         clan_member_counts[clan] += 1
                        
#                 ranked_clans = [
#                     {
#                         'clan_name': clan,
#                         'profit': round(clan_profits[clan] / clan_member_counts[clan], 2) # Average profit
#                     }
#                     for clan in sorted(clan_profits.keys(), key=lambda c: clan_profits[c] / clan_member_counts[c], reverse=True)
#                 ]
#                 for data in ranked_clans:
#                     clan_name = data['clan_name']
#                     clan = Clan.objects.get(clan_name=clan_name)
#                     data['clan_logo'] = clan.clan_logo.url
#                     data['clan_id'] = clan.id
#                     data['community_link'] = clan.community_link
#                     data['description'] = clan.description
#                     data['members_count'] = clan.member.count() + 1
#                     data['profit_comparison'] = clan.profit_comparison
#                 # Return the ranked list of clans
#                 return Response(ranked_clans[:3])

#         else:
#             competition = Competition.objects.filter(status='closed').order_by('id').last()
#             clans= ClanCompetitionSummary.objects.filter(competition=competition).order_by('position')[:3]
#             data=[{'clan_id':comp.clan.id,'clan_name':comp.clan.clan_name,'community_link':comp.clan.community_link,'clan_logo':comp.clan.clan_logo.url,'description':comp.clan.description, 'profit':comp.profit, 'position':comp.position, 'top_3_count':comp.clan.top_3_count,'profit_comparison':comp.clan.profit_comparison,'members_count':comp.clan.members_count} for comp in clans ]
#             return Response(data)

from collections import defaultdict
class TopClans(APIView):
    permission_classes = (AllowAny,)
    def get(self, request):
        competition =  Competition.objects.filter(status='current')
        if competition.exists() and  timezone.now() > competition.first().start_date:
                portfolio = CompetitionPortfolio.objects.filter(competition=competition.first(), active=True)
                
                clan_returns = defaultdict(list)
                
                for account in portfolio:
                    
                    profit, status = getProfit(account)

                    if status:
                        clan = account.user.clans
                        clan_returns[clan].append(profit/1000000)  

                # print(clan_returns)
                ranked_clans = []
                for clan, returns in clan_returns.items():
                    cumulative_return = (1 + pd.Series(returns)).cumprod() - 1
                    # print(cumulative_return)
                    ranked_clans.append({
                        'clan_name': clan,
                        'profit': round(cumulative_return.iloc[-1] * 100, 2)
                    })

                ranked_clans = sorted(ranked_clans, key=lambda x: x['profit'], reverse=True)
                for data in ranked_clans:
                    clan_name = data['clan_name']
                    clan = Clan.objects.get(clan_name=clan_name)
                    data['clan_logo'] = clan.clan_logo.url
                    data['clan_id'] = clan.id
                    data['community_link'] = clan.community_link
                    data['description'] = clan.description
                    data['members_count'] = clan.member.count() + 1
                    data['profit_comparison'] = clan.profit_comparison
                # Return the ranked list of clans
                return Response(ranked_clans[:3])

        else:
            competition = Competition.objects.filter(status='closed').order_by('id').last()
            clans= ClanCompetitionSummary.objects.filter(competition=competition).order_by('position')[:3]
            data=[{'clan_id':comp.clan.id,'clan_name':comp.clan.clan_name,'community_link':comp.clan.community_link,'clan_logo':comp.clan.clan_logo.url,'description':comp.clan.description, 'profit':comp.profit, 'position':comp.position, 'top_3_count':comp.clan.top_3_count,'profit_comparison':comp.clan.profit_comparison,'members_count':comp.clan.members_count} for comp in clans ]
            return Response(data)
       
     

class TopTraders(APIView):
    permission_classes = (AllowAny,)
    def get(self, request):
        competition = Competition.objects.filter(status='closed').order_by('id').last()
        accounts= CompetitionSummary.objects.filter(competition=competition).order_by('position')[:1]
        data = [{'name':f"{account.user.fullname}", 'profit':account.profit, 'position':account.position} for account in accounts]
        return Response(data)



# Emails templates
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def send_top_clan_payment_processing_mail(user):
     # render email text
    subject="Hamma Top Clan PAYMENT PROCESSING"
    html_content = render_to_string('custom/PaymentProcessing.html')

    # Create the EmailMultiAlternatives object
    email_message = EmailMultiAlternatives(subject=subject,
        from_email="hello@gohamma.com",
        to=[user],
    )
    # Attach the HTML content to the email message
    email_message.attach_alternative(html_content, "text/html")
    # Send the email
    email_message.send()
def send_top_trader_payment_processing_mail(user):
     # render email text
    subject="Hamma Top Trader PAYMENT PROCESSING"
    html_content = render_to_string('custom/PaymentProcessing.html')

    # Create the EmailMultiAlternatives object
    email_message = EmailMultiAlternatives(subject=subject,
        from_email="hello@gohamma.com",
        to=[user],
    )
    # Attach the HTML content to the email message
    email_message.attach_alternative(html_content, "text/html")
    # Send the email
    email_message.send()
        

@api_view(['GET'])
@permission_classes([AllowAny])
def payout_details(request,pk):
    # print('pk:',pk)
    payout = TopTraderPayout.objects.get(id=pk)
    try:
        if payout.amount != 'Processing' and payout.amount != '':
            amount = int(payout.amount)
        else:
            amount = None
    except ValueError:
        amount = None  

    profile= Profile.objects.get(user=payout.useracc.user)
    data = {'email':f"{payout.useracc.user.email}-{payout.useracc.acc.number}-{payout.useracc.acc.typeofaccount}",
            'amount':amount,
            'bank_name':profile.bank_name,
            'account_number':profile.account_number
    }
    return JsonResponse(data=data)

@api_view(['GET'])
@permission_classes([AllowAny])
def remove_trader(request,pk):
    account=CompetitionPortfolio.objects.get(id=pk)
    print(account.id)
    account.active=False
    account.save()
    return JsonResponse({'active':False})

@api_view(['GET'])
@permission_classes([AllowAny])
def clan_payout_details(request,pk):
    # print('pk:',pk)
    payout = TopClanMembersPayout.objects.get(id=pk)
    try:
        if payout.amount != 'Processing' and payout.amount != '':
            amount = int(payout.amount)
        else:
            amount = None
    except ValueError:
        amount = None  

    profile= Profile.objects.get(user=payout.user)
    data = {'email':f"{payout.user.email}",
            'amount':amount,
            'bank_name':profile.bank_name,
            'account_number':profile.account_number,
            
    }
    return JsonResponse(data=data)

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def update_toptrader_payout(request):
    from datetime import date
    id=request.data.get('id')
    print(id)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    payout = TopTraderPayout.objects.get(id=id)
    payout.status = 'Paid'
    payout.payment_date = today_str
    payout.save()
        
    return JsonResponse({'message':'Paid and Updated','pay_date': payout.payment_date,})

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def update_topclan_payout(request):
    from datetime import date
    id=request.data.get('id')
    print(id)
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    payout = TopClanMembersPayout.objects.get(id=id)
    payout.status = 'Paid'
    payout.payment_date = today_str
    payout.save()
        
    return JsonResponse({'message':'Paid and Updated','pay_date': payout.payment_date,})



from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect



def login_view(request):
    if request.method == "POST":
    
        email = request.POST.get("email")
        password = request.POST.get("password")
        print(email, password,"sdbsvds")
        user = authenticate(email=email, password=password)
        if user is not None and (user.is_staff):
            login(request, user)
            if user.is_staff:
                return redirect("leaderboard")
                # next_url = reverse("user_list")  # Get next URL from query parameter or default to "home"
           
        else:
            return JsonResponse({"error": "Please log in with your staff account."}, status=400)
    return render(request, "leaderboard/dash_login.html", {})

def logout_view(request):
    logout(request)
    return redirect('leaderboard_admin')

# new clan admin actions
@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def admin_clan_update_name_link(request):
    clan_name_requests = competion_models.ClanNameChangeRequest.objects.all()
    return render(request,"leaderboard/clan-name-change.html", {"clan_name_requests":clan_name_requests})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def admin_clan_update_name_detailed(request, req_id):
    clan_name_request = competion_models.ClanNameChangeRequest.objects.filter(id=req_id).first()
    if request.method == "POST":
        clan_name_request.reason = request.POST.get("reason",clan_name_request.reason)
        clan_name_request.approved = request.POST.get("approved",clan_name_request.approved)
        clan_name_request.save()
        if clan_name_request.approved == "approved":
            clan =Clan.objects.filter(id= clan_name_request.clan.id).first()
            clan.clan_name = clan_name_request.new_clan_name
            clan.save()
        save_and_send_notification(clan_name_request.clan_owner.id, f"Your request to remove a member has been {clan_name_request.approved}")
        return redirect("admin_name_change_req")

    return render(request,"leaderboard/clan-name-change-approval.html", {"clan_name_request":clan_name_request})

@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def admin_clan_remove_member(request):
    clan_member_removal_requests = competion_models.ClanMemeberRemoverRequest.objects.all()
    return render(request,"leaderboard/clan-remove-member.html", {"clan_member_removal_requests":clan_member_removal_requests})


@login_required
@user_passes_test(is_user_staff, login_url='/leaderboard/login/', redirect_field_name='403')
def admin_clan_remove_member_detailed(request, req_id):
    clan_remove_member_request = competion_models.ClanMemeberRemoverRequest.objects.filter(id=req_id).first()

    if request.method == "POST":
        clan_remove_member_request.reason = request.POST.get("reason",clan_remove_member_request.reason)
        clan_remove_member_request.approved = request.POST.get("approved",clan_remove_member_request.approved)
        clan_remove_member_request.save()
        if clan_remove_member_request.approved == "approved":
            clan_remove_member_request.clan.member.remove(clan_remove_member_request.clan_member_to_remove)
        save_and_send_notification(clan_remove_member_request.clan_owner.id, f"Your request to remove a member has been {clan_remove_member_request.approved}")
        return redirect("admin_member_req")

    return render(request,"leaderboard/clan-name-change-approval.html", {"clan_remove_member_request":clan_remove_member_request})


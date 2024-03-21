
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from datetime import timedelta, datetime
from django.db.models import Sum

import competition
from notifications.utils import save_and_send_notification

from .models import Competition, CompetitionPortfolio, CompetitionPosition, CompetitionTransaction
import pytz
from django.utils import timezone

from .serializers import CompetitionSerializer


class CompetitionView(APIView):
    def get(self, request, *args, **kwargs):
        competitions = Competition.objects.all()
        serializer = CompetitionSerializer(competitions, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = CompetitionSerializer(data=request.data)
        if serializer.is_valid():
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
         

class JoinLeaveCompetetion(APIView):
    
    def post(self, request, *args, **kwargs):
        competition_id=kwargs.get('competition_id')
        action=kwargs.get('action')
        
        try:
            competition = Competition.objects.get(id=competition_id, status='current')
        except Competition.DoesNotExist:
            return Response({"detail": "There is no ongoing competition"}, status=status.HTTP_404_NOT_FOUND)
        
        portfolio = CompetitionPortfolio.objects.filter(competition=competition,user=request.user).first()
        
        if action == "join":
            if competition.start_date > timezone.now():
                return Response({"detail": "Competition has not started"}, status=status.HTTP_400_BAD_REQUEST)
            if portfolio:
                if portfolio.active:
                    return Response({"detail": "You already  in this competition"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"detail": "You have  already exited this competition"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                portfolio = CompetitionPortfolio.objects.create(competition=competition, user=request.user, balance=1000000)
                save_and_send_notification(portfolio.user.id, "You have joined ongoing competition and been given 1,000,000 naira to compete. Goodluck!")
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
            
        
class WalletBalance(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        portfolio = CompetitionPortfolio.objects.filter(user=request.user,competition__status='current', active=True).first()
        if  portfolio:
            transactions = CompetitionTransaction.objects.filter(user=request.user)
            positions= portfolio.composition.all()
            
            deposited = 1000000
            invested= sum([post.amount_invested for post in positions]) 
            balance = portfolio.balance
            uninvested = deposited - invested
            
            data = {
                "deposited":deposited,
                "invested":invested,
                # "uninvested":uninvested ,
                "uninvested":balance ,
                "balance":balance,
                "reserve": balance,
                # "reserve": uninvested + balance
                
            }
            
            return Response(data)
        else:
            return Response({'detail':"Not in competition"},status=status.HTTP_400_BAD_REQUEST)

class TradingDays(APIView):
    def get(self, request):
    
        portfolio = CompetitionPortfolio.objects.filter(competition__status='current', user=request.user,  active=True).first()
        if not portfolio:
            return Response({"trading_days": []})

        positions = portfolio.composition.all()
        valid_positions = [position for position in positions if position.updated - position.created >= timedelta(minutes=5) and position.status=='close']
        
        days = [position.updated.date() for position in valid_positions]
        
        return Response({"trading_days": days})
    
class Leaderboard(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        user_profits = []
        portfolios=CompetitionPortfolio.objects.filter(competition__status='current', active=True)
        
        for portfolio in portfolios:
            
            # Calculate total profit for the user
            total_profit = CompetitionPosition.objects.filter(portfolio=portfolio,status='close').aggregate(total_profit=Sum('profit_loss'))['total_profit'] 
            if total_profit:
                
                # Calculate percentage profit in the last 24 hours
                last_24_hours_positions = CompetitionPosition.objects.filter(portfolio=portfolio, updated__gte=datetime.now() - timedelta(hours=24), status='close')
                total_profit_last_24_hours = last_24_hours_positions.aggregate(total_profit=Sum('profit_loss'))['total_profit'] or 0
                percentage_profit_24_hours = (total_profit_last_24_hours / total_profit) * 100 if total_profit else 0

                # Calculate percentage profit in the last 1 week
                last_1_week_positions = CompetitionPosition.objects.filter(portfolio=portfolio, updated__gte=datetime.now() - timedelta(weeks=1), status='close')
                total_profit_last_1_week = last_1_week_positions.aggregate(total_profit=Sum('profit_loss'))['total_profit'] or 0
                percentage_profit_1_week = (total_profit_last_1_week / total_profit) * 100 if total_profit else 0

                user_profits.append({
                    "user": portfolio.user.fullname,
                    "total_profit": total_profit,
                    "percentage_profit_24_hours": percentage_profit_24_hours,
                    "percentage_profit_1_week": percentage_profit_1_week
                })
            
                

        # Sort users based on total profit from biggest to smallest
        sorted_user_profits = sorted(user_profits, key=lambda x: x["total_profit"], reverse=True)

        return Response(sorted_user_profits)

from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from notifications.utils import save_and_send_notification
from decimal import Decimal
from .models import (Competition, CompetitionPortfolio, get_price, CompetitionDailyReturns, ClanCompetitionSummary, CompetitionSummary, Clan, 
                     CompetitionPosition, CompetitionTransaction)

from django.db.models import Sum, Avg
from django.db.models.expressions import Window,F 
from django.db.models.functions import Rank
from accounts.models import UserActivityLog
from datetime import datetime, timedelta


logger = get_task_logger(__name__)

def close_competition_trades(competition):
    positions = CompetitionPosition.objects.filter(portfolio__competition=competition, status='open')
    for position in positions:
        pl, cur_val,price = position.calculate_profit_loss()
        
        position.status = 'close'
        position.close_price = Decimal(price)
        position.profit_loss =pl
        position.save()
        
        CompetitionTransaction.objects.create(
                user=position.portfolio.user,
                transaction_type='close trade',
                amount=position.amount_invested + position.profit_loss,
                status='completed'
            )
        activity=UserActivityLog.objects.create(user=position.portfolio.user, action_type="competition_closed_trade",description=f"Open competition trade with symbol {position.stock.symbol} is closed.")
        position.portfolio.balance += position.amount_invested + position.profit_loss
        position.portfolio.save()

def getProfit(portfolio):
    positions = CompetitionPosition.objects.filter(portfolio=portfolio, status='close')
    # print(len(positions))
    
    profit_list = []
    trading_days = []
    for position in positions:
        profit_list.append(position.profit_loss)
        if position.updated - position.created >= timedelta(minutes=5):
            trading_days.append(position.updated)
    profit = sum(profit_list)
    days = len(trading_days)
    # print(profit)
    return profit,days

def Create_competiton_summary(competition):
    close_competition_trades(competition)
    
    portfolios = CompetitionPortfolio.objects.filter(competition=competition, active=True)
    
    for portfolio in portfolios:
        try:
            clan = Clan.objects.filter(member=portfolio.user).first()
            if not clan:
                raise Clan.DoesNotExist
        except Clan.DoesNotExist:
            clan = Clan.objects.filter(clan_admin=portfolio.user).first()
        
        profit,trading_days = getProfit(portfolio)
        percent = round(profit / 1000000 * 100, 2)
        
        # Use the single `portfolio` instance here
        CompetitionSummary.objects.create(portfolio=portfolio, clan=clan, user=portfolio.user, profit=percent, competition=competition, trading_days=trading_days)
    
    # close the competition after the loop is completed
    competition.status = "closed"
    competition.save()


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


@shared_task
def create_competition(id,datestart):
    competition = Competition.objects.get(id=id)
    user_ids = [id for id in get_user_model().objects.values_list('id', flat=True)]
    formatted_start_date = datestart.strftime("%B %d, %Y at %I:%M %p")
    message= f"New Competition {competition.title.title()} will commence on {formatted_start_date}.\n {competition.message}"
    for id in user_ids:
        save_and_send_notification(id,message)

@shared_task
def start_competition(id):
    competition = Competition.objects.get(id=id)
    user_ids = [id for id in get_user_model().objects.values_list('id', flat=True)]
        
    for id in user_ids:
        save_and_send_notification(id,f"Competition {competition.title.title()} has started. Goodluck!")

@shared_task
def end_competition(id):
    competition = Competition.objects.get(id=id)
    
    competition.status='closed'
    competition.save()
    
    if competition.status=='closed':
        Create_competiton_summary(competition)
        rank_traders(competition)
        rank_clans(competition)
    
    
    
        
    user_ids = [id for id in get_user_model().objects.values_list('id', flat=True)]
    for id in user_ids:
        save_and_send_notification(id,f"Competition {competition.title.title()} has ended.")
        
@shared_task
def create_returns(portfolio_id):
    portfolio=CompetitionPortfolio.objects.get(id=portfolio_id)
    data = get_price ('ASI')
    pr = data['current_price']
    CompetitionDailyReturns.objects.create(user=portfolio.user, ngx_price = pr,portfolio=portfolio)
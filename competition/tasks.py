import time
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from numpy import half
from notifications.utils import save_and_send_notification
from decimal import Decimal
from .models import (Competition, CompetitionPortfolio, get_price, CompetitionDailyReturns, ClanCompetitionSummary, CompetitionSummary, Clan, 
                     CompetitionPosition, CompetitionTransaction)

from django.db.models import Sum, Avg
from django.db.models.expressions import Window,F 
from django.db.models.functions import Rank
from accounts.models import UserActivityLog
from datetime import datetime, timedelta
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.db.models import F, Window 
from django.db.models.functions import Rank
from django.utils import timezone

User=get_user_model()

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
    
@shared_task
def two_days_before_start(): #2
    users = User.objects.all()
    for user in users:
        context={
        "firstname":user.firstname
    }
        html_message = render_to_string('competition/two_days_before_start.html', context)
        plain_message = ""
        subject = 'BEFORE STEPPING ON HAMMA STAGE!'
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

@shared_task
def saturday_evening(): #3
    competition = Competition.objects.filter(status='current')
    if competition.exists():
        users = User.objects.all()
        
        for user in users:
            context={
            "firstname":user.firstname,
            'clan':user.clan.clan_name,
        }
            html_message = render_to_string('competition/saturday_evening.html', context)
            plain_message = ""
            subject = f' {user.firstname.title()}, WHERE DO YOU STAND?'
            from_email = "teamgohamma@gmail.com"
            recipient_list = [user.email]
            send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

@shared_task
def four_days_before_end(): #4
    users = User.objects.all()
    for user in users:
        context={
        "firstname":user.firstname,
    }
        html_message = render_to_string('competition/four_days_before_end.html', context)
        plain_message = ""
        subject = "Keep Pushing Forward - You're Doing Great!"
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
       
@shared_task
def friday_evening(): #5
    competition = Competition.objects.filter(status='current')
    if competition.exists():
        users = User.objects.all()
        for user in users:
            context={
            "firstname":user.firstname,
            'clan':user.clan.clan_name,
        }
            html_message = render_to_string('competition/friday_evening.html', context)
            plain_message = ""
            subject = 'GUESS WHO MADE TOP TRADER FOR THE WEEK?'
            from_email = "teamgohamma@gmail.com"
            recipient_list = [user.email]
            send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
            

    
@shared_task
def mid_competition(): #7
    users = User.objects.all()
    for user in users:
        context={
        "firstname":user.firstname,
    }
        html_message = render_to_string('competition/mid_competition.html', context)
        plain_message = ""
        subject = "DO THIS IF YOU DON'T WANT TO WIN"
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
        
@shared_task
def last_day(): #8
    users = User.objects.all()
    for user in users:
        context={
        "firstname":user.firstname,
    }
        html_message = render_to_string('competition/last_day.html', context)
        plain_message = ""
        subject = "Congratulations - You're a Hamma Trading Competition Champion!"
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
        
@shared_task
def two_days_before_end(): #9
    users = User.objects.all()
    for user in users:
        context={
        "firstname":user.firstname,
    }
        html_message = render_to_string('competition/two_days_before_end.html', context)
        plain_message = ""
        subject = " Finish Strong in the Hamma Trading Competition!"
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
        
@shared_task
def three_days_after_end(): #10
    users = User.objects.all()
    for user in users:
        context={
        "firstname":user.firstname,
    }
        html_message = render_to_string('competition/three_days_after_end.html', context)
        plain_message = ""
        subject = "Reflecting on the Hamma Trading Competition Journey"
        from_email = "teamgohamma@gmail.com"
        recipient_list = [user.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
        
def create_crontab(target_time):
    start_schedule, created1 = CrontabSchedule.objects.get_or_create(
            minute=target_time.minute,
            hour=target_time.hour,
            day_of_month=target_time.day,
            month_of_year=target_time.month
            )
    return start_schedule


def get_halfway_date(instance):
    if instance.start_date and instance.end_date:
        duration = instance.end_date - instance.start_date
        halfway_duration = duration / 2
        halfway_date = instance.start_date + halfway_duration
        return halfway_date
    return None
    
@shared_task
def setup_competition_emails(competition_id):
    competition = Competition.objects.get(id=competition_id)
    start_date = competition.start_date
    end_date = competition.end_date
    
    #1 done
    #2 2days before competition
    
    two_days_before_start = start_date - timedelta(days=2)
    if timezone.now() < two_days_before_start:
        two_days_before_start_schedule = create_crontab(two_days_before_start)
    else:
        if timezone.now() < start_date - timedelta(days=1):
            two_days_before_start_schedule = create_crontab(start_date - timedelta(days=1))
        else:
            two_days_before_start_schedule = create_crontab(timezone.now() + timedelta(minutes=5))
            
    PeriodicTask.objects.create(
        name=f"competition {competition.id} 2 days before start schedule",
        task='competition.tasks.two_days_before_start',
        one_off=True,
        crontab = two_days_before_start_schedule
    )
    
    #3 done
    #4 4days before end of competition
    
    four_days_before_end = end_date - timedelta(days=4)
    
    if timezone.now() < four_days_before_end:
        four_days_before_end_schedule = create_crontab(four_days_before_end)
    else:
        four_days_before_end_schedule = create_crontab(timezone.now() + timedelta(minutes=5))
        
    
    PeriodicTask.objects.create(
        name=f"competition {competition.id} 4 days before end schedule",
        task='competition.tasks.four_days_before_end',
        one_off=True,
        crontab = four_days_before_end_schedule
    )
    
    #5 done
    
    #7 - mid competition
    
    halfway_date = get_halfway_date(competition)
    
    halfway_schedule = create_crontab(halfway_date)
    PeriodicTask.objects.create(
        name=f"competition {competition.id} mid competition schedule",
        task='competition.tasks.mid_competition',
        one_off=True,  
        crontab = halfway_schedule
    )
    
    #8
    last_day = end_date.replace(hour=8)
    if timezone.now() < last_day:
        last_day_schedule = create_crontab(last_day)
    else:
        last_day_schedule = create_crontab(timezone.now() + timedelta(minutes=5))
        
    PeriodicTask.objects.create(
        name=f"competition {competition.id} last day schedule",
        task='competition.tasks.last_day',
        one_off=True,
        crontab = last_day_schedule
    )
    
    #9 2days before end
    
    two_days_before_end_date = end_date - timedelta(days=2)  
    if timezone.now() < two_days_before_end_date:
        two_days_before_end_schedule = create_crontab(two_days_before_end_date)
    else:
        two_days_before_end_schedule = create_crontab(timezone.now() + timedelta(minutes=5))
        
    PeriodicTask.objects.create(
        name=f"competition {competition.id} 2 days before end schedule",
        task='competition.tasks.two_days_before_end',
        one_off=True,
        crontab = two_days_before_end_schedule
    )
    
    #10 3days after end
    three_days_after_end_date = end_date + timedelta(days=3)
    three_days_after_end_schedule = create_crontab(three_days_after_end_date)
    PeriodicTask.objects.create(
        name=f"competition {competition.id} 3 days after end schedule",
        task='competition.tasks.three_days_after_end',
        one_off=True,
        crontab = three_days_after_end_schedule
    )
    
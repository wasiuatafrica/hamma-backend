from celery import shared_task
from celery.utils.log import get_task_logger

from django.core.management import call_command
from django.contrib.auth import get_user_model
from notifications.utils import save_and_send_notification
from .views import Create_competiton_summary, rank_traders, rank_clans
from .models import Competition
import boto3
import json
import concurrent.futures
from functools import partial
from django.db import transaction

logger = get_task_logger(__name__)

@shared_task
def create_competition(id,datestart):
    competition = Competition.objects.get(id=id)
    user_ids = [id for id in get_user_model().objects.values_list('id', flat=True)]
    formatted_start_date = datestart.strftime("%B %d, %Y at %I:%M %p")
    message= f"New Competition {competition.title.title()} will commence on {formatted_start_date}."
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
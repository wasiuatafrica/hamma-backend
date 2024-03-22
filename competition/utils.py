from .models import Competition, CompetitionSummary, CompetitionPosition, CompetitionPortfolio
from django.db.models import Sum, Avg
from django.db.models.expressions import Window,F 
from django.db.models.functions import Rank


# This function will be called in the function closing the competition after the count down.
def Create_competiton_summary(competition):
    pass


def rank_traders(competition): 
   
    summary = CompetitionSummary.objects.filter(competition=competition).exclude(profit=0)
    
    summary = summary.annotate( rank=Window( expression=Rank(), order_by=F('profit').desc() ) ) 
    # Update the position field with the rank value 
    for obj in summary: 
        obj.position = obj.rank 
        obj.save() 
    return summary

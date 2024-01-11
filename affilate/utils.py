from datetime import datetime, timedelta
from .models import RewardActivities, BrokageCommission
from django.db.models import Sum

def get_quarter_dates():
    today = datetime.now()
    quarter_start_month = (today.month - 1) // 3 * 3 + 1
    first_day_of_quarter = datetime(today.year, quarter_start_month, 1)

    last_day_of_quarter = first_day_of_quarter + timedelta(days=89)  
    year, month = last_day_of_quarter.year, last_day_of_quarter.month

    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            last_day = 29  
        else:
            last_day = 28  
    elif month in (4, 6, 9, 11):
        last_day = 30
    else:
        last_day = 31

    last_day_of_quarter_end = datetime(year, month, last_day, 23, 59, 59)

    return (first_day_of_quarter, last_day_of_quarter_end)

def get_rank_details(user, first_day):
    brokerage_commission = BrokageCommission.objects.filter(user=user,created__gte=first_day)
    if brokerage_commission:
        min_commission = brokerage_commission.aggregate(total_commission=Sum('commission'))['total_commission']
    else:
        min_commission = 0
    reward_activities = RewardActivities.objects.filter(user=user, created__gte=first_day)
    if reward_activities:
        active_referees = reward_activities.values('trader').distinct().count()
    else:
        active_referees = 0
        
    return {
        'brokerage_commission':min_commission,
        'active_referees':active_referees,
        'username':user.fullname,
        'user_id':user.id
    }
    
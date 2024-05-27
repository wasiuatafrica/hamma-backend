import datetime
from typing import Any
from django.utils import timezone
import datetime
from calendar import weekday, day_name, monthcalendar
from typing import Optional, Any
from . import models
from accounts import models as acc_models

def get_public_holidays(year):
    """
    Returns a list of public holidays for the given year.
    """
    holidays = []
    
    # New Year's Day
    holidays.append(datetime.date(year, 1, 1))
    
    # Good Friday
    for month, week in enumerate(monthcalendar(year, 3), start=3):
        if week[6] != 0:
            holidays.append(datetime.date(year, month, week[6]))
            break
    
    # Easter Monday
    for month, week in enumerate(monthcalendar(year, 3), start=3):
        if week[0] != 0:
            holidays.append(datetime.date(year, month, week[0] + 1))
            break
    
    # Other public holidays (assuming fixed dates)
    holidays.extend([
        datetime.date(year, 4, 10),  # Id el Fitr (Tentative Date)
        datetime.date(year, 4, 11),  # Id el Fitr holiday (Tentative Date)
        datetime.date(year, 5, 1),   # Workers' Day
        datetime.date(year, 6, 12),  # Democracy Day
        datetime.date(year, 6, 17),  # Id el Kabir (Tentative Date)
        datetime.date(year, 6, 18),  # Id el Kabir additional holiday (Tentative Date)
        datetime.date(year, 9, 16),  # Id el Maulud (Tentative Date)
        datetime.date(year, 10, 1),  # National Day
        datetime.date(year, 12, 25), # Christmas Day
        datetime.date(year, 12, 26)  # Boxing Day
    ])
    
    return holidays

def count_business_days(start_date, end_date):
    business_days = 0
    current_date = start_date.date()
    end_date = end_date.date()
    
    public_holidays = get_public_holidays(current_date.year)
    
    while current_date <= end_date:
        day_of_week = weekday(current_date.year, current_date.month, current_date.day)
        if day_of_week < 5 and current_date not in public_holidays:  # Monday to Friday, excluding public holidays
            business_days += 1
        current_date += datetime.timedelta(days=1)
    
    return business_days



# start_date = timezone.now()
# end_date = timezone.now() + timezone.timedelta(days=10)

# business_days = count_business_days(start_date, end_date)
# print(f"There are {business_days} business days between {start_date} and {end_date}.")

def has_atleat_3_clan_members(clan_id: int)->bool:
    clan = models.Clan.objects.filter(id=clan_id).first()
    if not clan:
        return False
    return True if clan.members_count >=3 else False
    
def trader_has_completed_kyc(user:Any)->bool:
    profile = acc_models.Profile.objects.filter(user=user).first()
    return True if (profile.proof_of_address and profile.proof_of_id and profile.profile_img ) else False

def user_has_atleat_10_min_trading_days(user:any)->bool:
    competion_summary = models.CompetitionSummary.objects.filter(user=user).first()
    if not competion_summary:
        return False
    return True if competion_summary.trading_days >=10 else False

def clan_has_at_least_10_min_trading_days(clan_id: int) -> bool:
    try:
        clan = models.Clan.objects.get(id=clan_id)
    except models.Clan.DoesNotExist:
        return False
    
    members = list(clan.member.all())
    if clan.clan_admin:
        members.append(clan.clan_admin)
    
    for member in members:
        competition_summary = models.CompetitionSummary.objects.filter(clan=clan, user=member).first()
        if not competition_summary or competition_summary.trading_days is None or competition_summary.trading_days < 10:
            return False
    
    return True

def clan_has_at_completed_kyc(clan_id: int) -> bool:
    try:
        clan = models.Clan.objects.get(id=clan_id)
    except models.Clan.DoesNotExist:
        return False
    
    members = list(clan.member.all())
    if clan.clan_admin:
        members.append(clan.clan_admin)
    
    for member in members:
        
        profile = acc_models.Profile.objects.filter(user=member).first()
        if not (profile.proof_of_address and profile.proof_of_id and profile.profile_img ):
            return False
    
    return True
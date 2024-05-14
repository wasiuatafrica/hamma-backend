import datetime
from django.utils import timezone
import datetime
from calendar import weekday, day_name, monthcalendar

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
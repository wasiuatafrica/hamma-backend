from django.utils import timezone
from datetime import datetime


def days_since_date(date_str):
    """
    Calculates the number of days that have passed since the given date.
    
    Args:
        date_str (str): The date in the format 'YYYY-MM-DD'.
        
    Returns:
        int: The number of days that have passed since the given date.
    """
    today = datetime.now().date()
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    days_passed = (today - date).days
    return days_passed


print(type((days_since_date('2024-04-16'))))
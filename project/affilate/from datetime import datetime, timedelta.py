from datetime import datetime, timedelta

def get_quarter_dates():
    today = datetime.now()
    quarter_start_month = (today.month - 1) // 3 * 3 + 1
    first_day_of_quarter = datetime(today.year, quarter_start_month, 1)

    last_day_of_quarter = first_day_of_quarter + timedelta(days=89)  
    year, month = last_day_of_quarter.year, last_day_of_quarter.month

    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            last_day = 29  # Leap year
        else:
            last_day = 28  # Not a leap year
    elif month in (4, 6, 9, 11):
        last_day = 30
    else:
        last_day = 31

    # Set the time to 23:59:59 for the last day
    last_day_of_quarter_end = datetime(year, month, last_day, 23, 59, 59)

    return (first_day_of_quarter, last_day_of_quarter_end)

# Example usage
first_day, last_day = get_quarter_dates()
print(f"First day of quarter: {first_day}")
print(f"Last day of quarter: {last_day}")

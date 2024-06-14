import datetime


def get_timedelta_in_weeks(date1, date2):
    # Calculate the difference between the two dates
    date_difference = date1 - date2
    
    # Convert the difference to weeks
    timedelta_in_weeks = date_difference / datetime.timedelta(weeks=1)
    
    return timedelta_in_weeks

# Define June 30th of the current year
current_year = datetime.datetime.now().year
june_30 = datetime.datetime(current_year, 6, 30, 3,15)
june_31 = datetime.datetime(current_year, 6, 16, 3,15)

# Get the day name 2 weeks before June 30th
day_name = get_timedelta_in_weeks(june_30,june_31)
print(f"The day 2 weeks before June 30th is a {day_name}.")

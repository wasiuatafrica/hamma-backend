import datetime
from django.template.loader import render_to_string
from django.core.mail import send_mail


def get_timedelta_in_weeks(date1, date2):
    # Calculate the difference between the two dates
    date_difference = date1 - date2

    # Convert the difference to weeks
    timedelta_in_weeks = date_difference / datetime.timedelta(weeks=1)

    return timedelta_in_weeks


# # Define June 30th of the current year
# current_year = datetime.datetime.now().year
# june_30 = datetime.datetime(current_year, 6, 30, 3,15)
# june_31 = datetime.datetime(current_year, 6, 17, 3,15)

# # Get the day name 2 weeks before June 30th
# day_name = get_timedelta_in_weeks(june_30,june_31)
# print(f"The day 2 weeks before June 30th is a {day_name}.")


def sendTemplateMail(
    template: str,
    recipient_list: list,
    subject: str,
    context: dict,
    from_email: str = "Hamma <hello@gohamma.com>",
):
    """_summary_ send a template email by calling this function and passing the
    param, to save duplivate functions.

    Args:
        template (str): Address of email template to be sent.
        recipient_list (list): Alist of emails
        subject (str): The email subject
        context (dict): Extra inof needed to be passed into the template.
        from_email (str, optional): _description_. Defaults to "hello@gohamma.com".
    """
    html_message = render_to_string(template, context)
    plain_message = ""
    subject = subject
    from_email = from_email
    recipient_list = recipient_list
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )

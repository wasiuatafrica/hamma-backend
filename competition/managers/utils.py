from django.template.loader import render_to_string
from django.core.mail import send_mail


def sendMail(
    template: str,
    subject: str,
    to: list,
    context: object = None,
    sender: str = None,
    **kwargs
) -> bool:
    """
    A wrapper for send_mail
    Compile a template to html and string and send email

    Arguments:
        template {str} -- The template location
        subject {str} -- Mail Subject
        to {object} -- Mail recipients, can be string or list

    Keyword Arguments:
        context {object} -- The data to pass to the template (default: {None})
        sender {str} -- Opeional Sender (default: {None})

    Returns:
        bool -- send_mail 1 = sent and 0 not sent
    """
    html = render_to_string(template, context)
    try:
        send_mail(
            subject,
            "",
            "teamgohamma@gmail.com",
            to,
            html_message=html,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(str(e))
        return False

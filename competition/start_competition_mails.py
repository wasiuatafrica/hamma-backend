from helpers import sendTemplateMail


def send_trading_rules(user):
    send= sendTemplateMail(
        subject="Rules of Engagement",
        recipient_list=[user.email],
        context={"first_name":user.firstname.title()},
        template="competition/trading_rules.html",
    )
    return

def send_trade_reminder(user):
    send= sendTemplateMail(
        subject="Get Gingered",
        recipient_list=[user.email],
        context={"first_name":user.firstname.title()},
        template="competition/trade_reminder.html",
    )
    return

def send_daily_trade_confirmation(user, context:dict):
    send= sendTemplateMail(
        subject="A New Day with a New Trade",
        recipient_list=[user.email],
        context=context,
        template="competition/daily_trade_confirmation.html",
    )
    return

def send_trading_idea(user, context:dict={}):
    send= sendTemplateMail(
        subject="New Trading Idea",
        recipient_list=[user.email],
        context=context,
        template="competition/trading_idea.html",
    )
    return
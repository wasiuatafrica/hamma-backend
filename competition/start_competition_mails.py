from helpers import sendTemplateMail
from accounts.models import CustomUser



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


# simulate mails to test changes of healines

from accounts import tasks as mail_tasks
from competition import tasks as com_task_mails 
from portfolio import tasks as port_task_mails

def simulate__mail(payload: any = None, id:int=1):
    from competition import views
    # mail_tasks.after_signup_36h(id=1)
    # mail_tasks.welcome_1c(id=1)
    # mail_tasks.welcome_1b(id)
    # mail_tasks.send_welcome_email(id)

    # auto reject mail
    # com_task_mails.check_pending_join_clan_requests()
    # auto approve
    # com_task_mails.auto_approve_join_clan_requests(id)

    # 11
    # com_task_mails.two_days_before_start()
    # 12
    # com_task_mails.saturday_evening()
    # 13
    # com_task_mails.four_days_before_end()
    # 14:
    # com_task_mails.friday_evening()
    # 15
    # com_task_mails.mid_competition()
    # 16
    # com_task_mails.last_day()
    # 17
    # com_task_mails.two_days_before_end()
    # 18
    # com_task_mails.three_days_after_end()
    # 19
    views.send_top_trader_payment_processing_mail("nwaforglory6@gmail.com")
# send_top_trader_payment_processing_mail

    # 21
    # user= CustomUser.objects.get(id=1)
    # port_task_mails.send_alert_email(user=user, symbol="UBA",alert_type="Test",action="Test_Action",to_price="2000")
    print("sent")
from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from numpy import half
from websocket import send
import competition
from notifications.utils import save_and_send_notification
from decimal import Decimal

from .models import (
    Competition,
    CompetitionCumulativeReturns2,
    CompetitionDailyReturns2,
    CompetitionPortfolio,
    JoinClanRequest,
    get_price,
    CompetitionDailyReturns,
    ClanCompetitionSummary,
    CompetitionSummary,
    Clan,
    CompetitionPosition,
    CompetitionTransaction,
    CompetitionCumulativeReturns,
)
from .start_competition_mails import (
    send_trade_reminder,
    send_trading_idea,
    send_trading_rules,
    send_daily_trade_confirmation,
)
from django.db.models import Sum, Avg
from django.db.models.expressions import Window, F
from django.db.models.functions import Rank
from accounts.models import UserActivityLog
from datetime import datetime, timedelta
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.db.models import F, Window
from django.db.models.functions import Rank
from django.utils import timezone
from .managers.utils import sendMail
from portfolio.models import DashboardFeed
from django.urls import reverse


from collections import defaultdict
import pandas as pd
import json

User = get_user_model()

logger = get_task_logger(__name__)


def close_competition_trades(competition):
    positions = CompetitionPosition.objects.filter(
        portfolio__competition=competition, status="open"
    )
    for position in positions:
        pl, cur_val, price = position.calculate_profit_loss()

        position.status = "close"
        position.close_price = Decimal(price)
        position.profit_loss = pl
        position.save()

        CompetitionTransaction.objects.create(
            user=position.portfolio.user,
            transaction_type="close trade",
            amount=position.amount_invested + position.profit_loss,
            status="completed",
        )
        # activity=UserActivityLog.objects.create(user=position.portfolio.user, action_type="competition_closed_trade",description=f"Open competition trade with symbol {position.stock.symbol} is closed.")
        position.portfolio.balance += position.amount_invested + position.profit_loss
        position.portfolio.save()


def getProfit(portfolio):
    positions = CompetitionPosition.objects.filter(portfolio=portfolio, status="close")
    # print(len(positions))

    profit_list = []
    trading_days = set()
    for position in positions:
        profit_list.append(position.profit_loss)
        if position.updated != position.created:
            trading_days.add(position.updated.date())
    profit = sum(profit_list)
    days = len(trading_days)
    # print(profit)
    return profit, days


def Create_competiton_summary(competition):
    print("closing open positions")
    close_competition_trades(competition)
    print("positions closed")
    portfolios = CompetitionPortfolio.objects.filter(
        competition=competition, active=True
    )

    print("creating summary")
    for portfolio in portfolios:
        try:
            clan = Clan.objects.filter(member=portfolio.user).first()
            if not clan:
                raise Clan.DoesNotExist
        except Clan.DoesNotExist:
            clan = Clan.objects.filter(clan_admin=portfolio.user).first()

        profit, trading_days = getProfit(portfolio)
        percent = round(profit / 1000000 * 100, 2)

        # Use the single `portfolio` instance here
        CompetitionSummary.objects.create(
            portfolio=portfolio,
            clan=clan,
            user=portfolio.user,
            profit=profit,
            percent=percent,
            competition=competition,
            trading_days=trading_days,
        )

        print(f"created summary for {portfolio.user}")
    # close the competition after the loop is completed
    # competition.status = "closed"
    # competition.save()


def rank_clans(competition):
    # Group by clans and annotate the total profit for each clan
    competition_summary = CompetitionSummary.objects.filter(competition=competition)
    clan_returns = defaultdict(list)

    for account in competition_summary:
        profit = account.profit
        clan = account.user.clans
        clan_returns[clan].append(profit / 1000000)

    ranked_clans = []
    for clan, returns in clan_returns.items():
        cumulative_return = (1 + pd.Series(returns)).cumprod() - 1
        # print(cumulative_return)
        clan_instance = Clan.objects.get(clan_name=clan)
        ranked_clans.append(
            {
                "clan_name": clan,
                "clan_id": clan_instance.id,
                "profit": round(cumulative_return.iloc[-1] * 100, 2),
            }
        )

    ranked_clans = sorted(ranked_clans, key=lambda x: x["profit"], reverse=True)

    for i, summary in enumerate(ranked_clans, start=1):
        ClanCompetitionSummary.objects.create(
            competition=competition,
            clan_id=summary["clan_id"],
            profit=summary["profit"],
            position=i,
        )
    return ranked_clans


# def rank_clans(competition):
#     # Group by clans and annotate the total profit for each clan
#     competition_summary= CompetitionSummary.objects.filter(competition=competition)
#     clan_profit_summary = (competition_summary.values('clan')
#         # .annotate(total_profit=Sum('profit'))
#         # .order_by('-total_profit')  # Order by total profit in descending order
#         .annotate(average_profit=Avg('profit'))
#         .order_by('-average_profit')  # Ord
#     )
#     # print(clan_profit_summary)
#     # Add rank to each clan based on total profit
#     clan_summary = clan_profit_summary.annotate(
#         rank=Window(expression=Rank(), order_by=F('average_profit').desc())
#     )
#     # print(clan_summary)
#     for summary in clan_summary:
#         ClanCompetitionSummary.objects.create(
#             competition=competition,
#             clan_id=summary['clan'],
#             profit=summary['average_profit'],
#             position=summary['rank']
#         )
#     return clan_summary


def rank_traders(competition):

    summary = CompetitionSummary.objects.filter(competition=competition).exclude(
        profit=0
    )
    # Use the Window expression to rank the objects by profit
    summary = summary.annotate(
        rank=Window(expression=Rank(), order_by=F("profit").desc())
    )
    # Update the position field with the rank value
    for obj in summary:
        obj.position = obj.rank
        obj.save()
    return summary


@shared_task
def create_competition(id, datestart):
    competition = Competition.objects.get(id=id)
    user_ids = [id for id in get_user_model().objects.values_list("id", flat=True)]
    formatted_start_date = datestart.strftime("%B %d, %Y at %I:%M %p")
    message = f"{competition.title.title()} will commence on {formatted_start_date}.\n {competition.message}"
    for id in user_ids:
        save_and_send_notification(id, message)


@shared_task
def start_competition(id):
    competition = Competition.objects.get(id=id)
    user_ids = [id for id in get_user_model().objects.values_list("id", flat=True)]

    for id in user_ids:
        save_and_send_notification(
            id, f"Competition {competition.title.title()} has started. Goodluck!"
        )


@shared_task
def end_competition(id):
    competition = Competition.objects.get(id=id)

    competition.status = "closed"
    competition.save()

    print("competition closed")
    if competition.status == "closed":
        print("creating competition summary")
        Create_competiton_summary(competition)
        print("ranking traders")
        rank_traders(competition)
        print("ranking clans")
        rank_clans(competition)

    # user_ids = [id for id in get_user_model().objects.values_list('id', flat=True)]
    # for id in user_ids:
    #     save_and_send_notification(id,f"Competition {competition.title.title()} has ended.")


def create_crontab(target_time):
    start_schedule, created1 = CrontabSchedule.objects.get_or_create(
        minute=target_time.minute,
        hour=target_time.hour,
        day_of_month=target_time.day,
        month_of_year=target_time.month,
    )
    return start_schedule


@shared_task
def trading_rule_task(user_id):
    user = User.objects.get(id=user_id)
    print(user.id)
    send_trading_rules(user)
    print("sent trading rule")


@shared_task
def create_returns(portfolio_id):
    portfolio = CompetitionPortfolio.objects.get(id=portfolio_id)
    CompetitionDailyReturns2.objects.create(
        portfolio=portfolio, user=portfolio.user, created=timezone.now()
    )
    CompetitionCumulativeReturns2.objects.create(
        portfolio=portfolio, user=portfolio.user, created=timezone.now()
    )

    schedule1 = create_crontab(timezone.now() + timedelta(days=14))

    PeriodicTask.objects.create(
        name=f"Send trading rules to  {portfolio.user.email} email",
        task="competition.tasks.trading_rule_task",
        one_off=True,
        crontab=schedule1,
        args=json.dumps([portfolio.user.id]),
    )


@shared_task
def two_days_before_start():  # 2
    users = User.objects.all()
    # print(f"sending for {user.email}")
    for user in users:
        context = {"firstname": user.firstname.title(), "email": user.email}
        html_message = render_to_string(
            "competition/two_days_before_start.html", context
        )
        plain_message = ""
        subject = "Before Stepping on Hamma Stage!"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )


@shared_task
def saturday_evening():  # 3
    competition = Competition.objects.filter(status="current")
    if competition.exists() and timezone.now() > competition.first().start_date:
        portfolios = CompetitionPortfolio.objects.filter(
            competition=competition.first(), active=True
        )
        users = [portfolio.user for portfolio in portfolios]
        # users = User.objects.all()

        for user in users:
            context = {"firstname": user.firstname.title(), "email": user.email}
            html_message = render_to_string(
                "competition/saturday_evening.html", context
            )
            plain_message = ""

            subject = "Get to the Top of the Leaderboard with these Pro Tips"
            from_email = "Hamma Team <teamgohamma@gmail.com>"
            recipient_list = [user.email]
            send_mail(
                subject,
                plain_message,
                from_email,
                recipient_list,
                html_message=html_message,
            )


@shared_task
def four_days_before_end():  # 4
    users = User.objects.all()

    for user in users:
        context = {"firstname": user.firstname.title(), "email": user.email}
        html_message = render_to_string(
            "competition/four_days_before_end.html", context
        )
        plain_message = ""
        # subject = "Keep Pushing Forward - You're Doing Great!"
        subject = "Finish Strong in the Hamma Trading Competition!"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )


# def get_top():
#     from collections import defaultdict
#     base_query = CompetitionPortfolio.objects.filter(competition__status='current',active=True)

#     leaderboard_list=[]
#     zero_profit_list = []

#     for account in base_query:
#         try:
#             clan=Clan.objects.filter(member=account.user)
#         except Clan.DoesNotExist:
#             clan=Clan.objects.filter(clan_admin=account.user)
#         if clan:
#             clan=clan.first()
#             user_portfolio = base_query.filter(user=account.user).first()
#             # print(user_portfolio.competition.title)
#             profit,status = getProfit(user_portfolio)
#             if status:
#                 percent= round((profit/1000000)*100,2)
#                 profile= Profile.objects.get(user=account.user)
#                 data= {
#                     'id':user_portfolio.id,
#                     'active':user_portfolio.active,
#                     'name':user_portfolio.user.firstname.title(),
#                     'profit':percent,
#                     'country':profile.country,
#                     'clan':clan.clan_name.title(),
#                 }

#                 leaderboard_list.append(data)

#     sorted_data = sorted(leaderboard_list, key=lambda x: x['profit'], reverse=True)

#     first = sorted_data[0]
#     trader = first['name']

#     clan_profits = defaultdict(float)
#     for entry in sorted_data:
#         clan_profits[entry['clan']] += entry['profit']

#     ranked_clans = [
#         {'clan_name': clan, 'profit': total_profit}
#         for clan, total_profit in sorted(clan_profits.items(), key=lambda x: x[1], reverse=True)
#     ][:3]
#     clan = ranked_clans[0]['clan_name']
#     return trader,clan


def get_top():
    from collections import defaultdict
    import pandas as pd

    base_query = CompetitionPortfolio.objects.filter(
        competition__status="current", active=True
    )

    leaderboard_list = []
    clan_returns = defaultdict(list)

    for account in base_query:
        try:
            clan = Clan.objects.filter(member=account.user)
        except Clan.DoesNotExist:
            clan = Clan.objects.filter(clan_admin=account.user)
        if clan:
            clan = clan.first()
            user_portfolio = base_query.filter(user=account.user).first()
            # print(user_portfolio.competition.title)
            profit, status = getProfit(user_portfolio)
            if status:
                percent = round((profit / 1000000) * 100, 2)
                data = {
                    "id": user_portfolio.id,
                    "active": user_portfolio.active,
                    "name": user_portfolio.user.firstname.title(),
                    "profit": percent,
                }

                leaderboard_list.append(data)

                clan = account.user.clans
                clan_returns[clan].append(profit / 1000000)

    sorted_data = sorted(leaderboard_list, key=lambda x: x["profit"], reverse=True)

    first = sorted_data[0]
    trader = first["name"]

    ranked_clans = []
    for clan, returns in clan_returns.items():
        cumulative_return = (1 + pd.Series(returns)).cumprod() - 1
        # print(cumulative_return)
        ranked_clans.append(
            {
                "clan_name": clan,
                "cumulative_return": round(cumulative_return.iloc[-1] * 100, 2),
            }
        )

    ranked_clans = sorted(
        ranked_clans, key=lambda x: x["cumulative_return"], reverse=True
    )

    clan = ranked_clans[0]["clan_name"]
    return trader, clan


@shared_task
def friday_evening():  # 5
    competition = Competition.objects.filter(status="current")
    if competition.exists() and timezone.now() > competition.first().start_date:
        users = User.objects.filter(is_active=True)
        trader, clan = get_top()
        for user in users:
            context = {
                # "firstname":user.firstname.title(),
                "email": user.email,
                "top_trader": trader,
                "top_clan": clan,
            }
            html_message = render_to_string("competition/friday_evening.html", context)
            plain_message = ""
            subject = "Guess Who Made Top Trader for the Week?"
            from_email = "Hamma Team <teamgohamma@gmail.com>"
            recipient_list = [user.email]
            send_mail(
                subject,
                plain_message,
                from_email,
                recipient_list,
                html_message=html_message,
            )


@shared_task
def mid_competition():  # 7
    competition = Competition.objects.filter(status="current")

    portfolios = CompetitionPortfolio.objects.filter(
        competition=competition.first(), active=True
    )
    users = [portfolio.user for portfolio in portfolios]
    for user in users:
        context = {"firstname": user.firstname.title(), "email": user.email}
        html_message = render_to_string("competition/mid_competition.html", context)
        plain_message = ""
        subject = f" {user.firstname.title()}, Where Do You Stand?"
        # subject = "DO THIS IF YOU DON'T WANT TO WIN"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )


@shared_task
def last_day():  # 8
    competition = Competition.objects.filter(status="current")

    portfolios = CompetitionPortfolio.objects.filter(
        competition=competition.first(), active=True
    )
    users = [portfolio.user for portfolio in portfolios]

    for user in users:
        context = {"firstname": user.firstname.title(), "email": user.email}
        html_message = render_to_string("competition/last_day.html", context)
        plain_message = ""
        subject = "Congratulations - You're a Hamma Trading Competition Champion!"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )


@shared_task
def two_days_before_end():  # 9
    competition = Competition.objects.filter(status="current")

    portfolios = CompetitionPortfolio.objects.filter(
        competition=competition.first(), active=True
    )
    users = [portfolio.user for portfolio in portfolios]

    for user in users:
        context = {
            "fullname": f"{user.firstname.title()} {user.lastname.title()}",
            "email": user.email,
        }
        html_message = render_to_string("competition/two_days_before_end.html", context)
        plain_message = ""

        subject = "Keep Pushing Forward - You're Doing Great!"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )


@shared_task
def three_days_after_end():  # 10
    users = User.objects.all()
    for user in users:
        context = {"firstname": user.firstname.title(), "email": user.email}
        html_message = render_to_string(
            "competition/three_days_after_end.html", context
        )
        plain_message = ""
        subject = "A Peak into the Past"
        from_email = "Hamma Team <teamgohamma@gmail.com>"
        recipient_list = [user.email]
        send_mail(
            subject,
            plain_message,
            from_email,
            recipient_list,
            html_message=html_message,
        )


def create_crontab(target_time):
    start_schedule, created1 = CrontabSchedule.objects.get_or_create(
        minute=target_time.minute,
        hour=target_time.hour,
        day_of_month=target_time.day,
        month_of_year=target_time.month,
    )
    return start_schedule


def get_halfway_date(instance):
    if instance.start_date and instance.end_date:
        duration = instance.end_date - instance.start_date
        halfway_duration = duration / 2
        halfway_date = instance.start_date + halfway_duration
        return halfway_date
    return None


@shared_task
def setup_competition_emails(competition_id):
    competition = Competition.objects.get(id=competition_id)
    start_date = competition.start_date
    end_date = competition.end_date

    # 1 done
    # 2 2days before competition

    two_days_before_start = start_date - timedelta(days=2)
    if timezone.now() < two_days_before_start:
        two_days_before_start_schedule = create_crontab(two_days_before_start)
    else:
        if timezone.now() < start_date - timedelta(days=1):
            two_days_before_start_schedule = create_crontab(
                start_date - timedelta(days=1)
            )
        else:
            two_days_before_start_schedule = create_crontab(
                timezone.now() + timedelta(minutes=5)
            )

    PeriodicTask.objects.create(
        name=f"competition {competition.id} 2 days before start schedule",
        task="competition.tasks.two_days_before_start",
        one_off=True,
        crontab=two_days_before_start_schedule,
    )

    # 3 done
    # 4 4days before end of competition

    four_days_before_end = end_date - timedelta(days=4)

    if timezone.now() < four_days_before_end:
        four_days_before_end_schedule = create_crontab(four_days_before_end)
    else:
        four_days_before_end_schedule = create_crontab(
            timezone.now() + timedelta(minutes=5)
        )

    PeriodicTask.objects.create(
        name=f"competition {competition.id} 4 days before end schedule",
        task="competition.tasks.four_days_before_end",
        one_off=True,
        crontab=four_days_before_end_schedule,
    )

    # 5 done

    # 7 - mid competition

    halfway_date = get_halfway_date(competition)

    halfway_schedule = create_crontab(halfway_date)
    PeriodicTask.objects.create(
        name=f"competition {competition.id} mid competition schedule",
        task="competition.tasks.mid_competition",
        one_off=True,
        crontab=halfway_schedule,
    )

    # 8
    last_day = end_date.replace(hour=8)
    if timezone.now() < last_day:
        last_day_schedule = create_crontab(last_day)
    else:
        last_day_schedule = create_crontab(timezone.now() + timedelta(minutes=5))

    PeriodicTask.objects.create(
        name=f"competition {competition.id} last day schedule",
        task="competition.tasks.last_day",
        one_off=True,
        crontab=last_day_schedule,
    )

    # 9 2days before end

    two_days_before_end_date = end_date - timedelta(days=2)
    if timezone.now() < two_days_before_end_date:
        two_days_before_end_schedule = create_crontab(two_days_before_end_date)
    else:
        two_days_before_end_schedule = create_crontab(
            timezone.now() + timedelta(minutes=5)
        )

    PeriodicTask.objects.create(
        name=f"competition {competition.id} 2 days before end schedule",
        task="competition.tasks.two_days_before_end",
        one_off=True,
        crontab=two_days_before_end_schedule,
    )

    # 10 3days after end
    three_days_after_end_date = end_date + timedelta(days=3)
    three_days_after_end_schedule = create_crontab(three_days_after_end_date)
    PeriodicTask.objects.create(
        name=f"competition {competition.id} 3 days after end schedule",
        task="competition.tasks.three_days_after_end",
        one_off=True,
        crontab=three_days_after_end_schedule,
    )


@shared_task
def check_pending_join_clan_requests():
    join_requests = JoinClanRequest.objects.filter(approved="pending")

    for req in join_requests:
        diff = timezone.now() - req.date_request
        if diff.days > 2:
            req.status = "rejected"
            req.save()
            save_and_send_notification(
                req.user.id, "Your clan join request has been rejected"
            )
            mail = sendMail(
                "competition/joinClanRejected.html",
                "Request to Join a Clan - Rejected",
                [req.user.email],
                {
                    "first_name": req.user.firstname.title(),
                    "clan_name": req.clan.clan_name.title(),
                },
            )
    print("check pending join clan requests done for today")


@shared_task
def auto_approve_join_clan_requests(id):
    join_request = JoinClanRequest.objects.get(id=id)

    account = join_request.user
    join_request.approved = "approved"
    join_request.save()
    join_request.clan.member.add(account)
    save_and_send_notification(
        join_request.user.id,
        f"Your request to join  {join_request.clan.clan_name.title()}  has been approved",
    )
    mail = sendMail(
        "competition/joinClanApproved.html",
        "Request to Join a Clan - Approved",
        [join_request.user.email],
        {
            "first_name": join_request.user.firstname,
            "clan_name": join_request.clan.clan_name,
        },
    )
    print("request approved")


@shared_task
def trade_reminder():
    portfolios = CompetitionPortfolio.objects.filter(
        active=True, competition__status="current"
    )
    for portfolio in portfolios:
        positions = portfolio.composition.all()
        if not positions:
            send_trade_reminder(portfolio.user)


@shared_task
def trading_ideas_task(feed_id):
    feed = DashboardFeed.objects.get(id=feed_id)
    context = {
        "id": feed.id,
        "topic": feed.topic,
        "symbol_url": feed.stock.email_logo_url,
        "posted_date": feed.published_date,
        "title": feed.title,
        "image_url": feed.image.url,
        "image_caption": feed.image_caption,
        "point1": feed.bullet_1,
        "point2": feed.bullet_2,
        "point3": feed.bullet_3,
    }
    users = User.objects.filter(is_active=True)
    for user in users:
        # context["image_url"]= f"https://api-hamma-f0bcaabf77ea.herokuapp.com/portfolio/{user.id}/{feed.id}"
        send_trading_idea(user, context)
    feed.sent = users.count()
    feed.save()


@shared_task
def first_daily_trade(portfolio_id):
    portfolio = CompetitionPortfolio.objects.get(id=portfolio_id)
    positions = portfolio.composition.filter(
        status="open", created__date=timezone.now().date()
    )

    if len(positions) == 1:
        position = positions.first()
        context = {
            "first_name": portfolio.user.firstname.title(),
            "date": position.created,
            "stock": position.stock.symbol,
            "type": position.action.title(),
            "price": position.open_price,
            "quantity": position.quantity,
            "id": position.order_id,
        }
        send_daily_trade_confirmation(portfolio.user, context)
    else:
        print("No trades to confirm today or this is not first trade")

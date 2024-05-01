from django.db import models
from django.db.models import Sum
from django.contrib.auth import get_user_model
from datetime import date
from accounts.models import Profile
from django.utils import timezone
import auto_prefetch
# import models

User = get_user_model()

from decimal import Decimal
import portfolio
from portfolio.models import  Stock




def get_price(symbol):
    from portfolio.utils import connect_to_mongodb
    db = connect_to_mongodb("stock_prices")
    collection = db["price_combined"]
    last_item = collection.find_one(sort=[('_id', -1)])

    return last_item[symbol]
  
class Competition(auto_prefetch.Model):
    start_date=models.DateTimeField(blank=True)
    end_date=models.DateTimeField(blank=True)
    title=models.CharField(max_length=200, unique=True,blank=True,db_index=True)
    created_at=models.DateTimeField(blank=True,null=True, auto_now_add=True)
    updated=models.DateTimeField(blank=True,null=True, auto_now_add=True)
    status=models.CharField(max_length=200,default='current', choices=(('current','current'),('closed','closed')),blank=True)
    first_prize=models.CharField(max_length=200,null=True, blank=True)
    second_prize=models.CharField(max_length=200,null=True, blank=True)
    third_prize=models.CharField(max_length=200,null=True, blank=True)
    message=models.TextField(null=True, blank=True)

    
    def __str__(self):
        return f'{self.title} | {self.status}'
    
  


class CompetitionPortfolio(auto_prefetch.Model):
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE, related_name='competition')
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comportfolio')
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.competition.title} {self.user}"
    
    @property
    def profit(self):
        closed_positions = self.composition.filter(status=CompetitionPosition.CLOSED)
        profit = closed_positions.aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
        percent= round((profit/1000000)*100,2)
        return percent



 
class CompetitionPosition(auto_prefetch.Model):
    OPEN = 'open'
    CLOSED = 'close'
    PENDING = 'pending'
    CANCELLED = 'cancelled'
    
    STATE_CHOICES = [
        (OPEN, 'Open'),
        (CLOSED, 'Closed'),
        (PENDING,'Pending'),
        (CANCELLED, 'Cancel')
    ]
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, related_name='composition')
    stock = auto_prefetch.ForeignKey(Stock, on_delete=models.CASCADE, related_name='composition')
    quantity = models.PositiveIntegerField(default=0)
    open_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    close_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    limit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATE_CHOICES, default=OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    amount_invested = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    action = models.CharField(max_length=20, default='buy')
    alert_name = models.CharField(max_length=50, blank=True, null=True)
    time_in_force = models.CharField(max_length=20, default='day')
    order_type = models.CharField(max_length=20, default='market')
    order_id = models.CharField(max_length=40,  blank=True, null=True)
    profit_loss = models.IntegerField(blank=True, null=True)
    
    
    def __str__(self):
        return f"{self.portfolio.user} - {self.stock.symbol} - {self.action} - {self.status}"
    
    def calculate_profit_loss(self):
        price = self.current_price
        current_value = round(self.quantity * price,2)
        # print(self.status)
        if self.status=='open':
            if self.action == 'buy':
                profit_loss = Decimal(current_value) - self.amount_invested
            elif self.action == 'sell':
                profit_loss = self.amount_invested - Decimal(current_value)
        elif self.status=='close':
            profit_loss =  self.profit_loss
            current_value = self.quantity * self.close_price
        else:
            current_value = 0
            profit_loss = 0
        # print(profit_loss)
        return profit_loss, current_value,price


    @property
    def current_price(self):
        return get_price(self.stock.symbol)['current_price']

class CompetitionProfitLoss(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comprofitloss')
    profit_loss = models.IntegerField(default=0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

class CompetitionDailyReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comreturns')
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, related_name='returns', blank=True, null=True )

    

    def __str__(self):
        return f"{self.user} - {self.created}"


    def __str__(self):
        return f"{self.user} - {self.created}"

class CompetitionCumulativeReturns(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='compcumureturns')
    portfolio_returns = models.FloatField(default=0.0)
    market_returns = models.FloatField(default=0.0)
    ngx_price = models.FloatField(default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, related_name='cumureturns', blank=True, null=True )

    

    def __str__(self):
        return f"{self.user} - {self.created}"


    def __str__(self):
        return f"{self.user} - {self.created}"


class CompetitionTransaction(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='comtransactions')
    transaction_type = models.CharField(max_length=50, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'),('buy', 'Buy'), ('sell', 'Sell')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status= models.CharField(max_length=20, default='unprocessed', blank=True,null=True)
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, related_name='transactions', blank=True, null=True)

  

class Clan(auto_prefetch.Model):
    
    clan_admin=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='clan_admin', blank=True, null=True)
    clan_name=models.CharField(max_length=200, unique=True,blank=True)
    community_link=models.URLField(blank=True)
    member=models.ManyToManyField(User, blank=True)
    description = models.TextField(blank=True, null=True)
    clan_logo=models.ImageField(upload_to='clan_logos', null=True, blank=True)
    date_request=models.DateTimeField(auto_now_add=True)
    created=models.DateTimeField(auto_now_add=True,null=True, blank=True)
    position=models.PositiveIntegerField(blank=True, null=True)
    position_index=models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f'{self.clan_name} '
    
    def save(self, *args, **kwargs):
        # Set default position to instance id if position is not provided
        if not self.position:
            self.position = self.id
        super().save(*args, **kwargs)
        
    @property
    def top_3_count(self):
        return ClanCompetitionSummary.objects.filter(clan=self).filter(position__in=[1, 2, 3]).count()

    @property
    def clan_total_profit(self):
        summary=CompetitionSummary.objects.filter(clan=self).aggregate(total_profit=Sum('profit'))['total_profit']
        # summary=self.competitionsummary_set.all().aggregate(total_profit=Sum('profits'))['total_profit']
        # print(summary,"Heloo")
        if summary:
            return summary
        return 0
    

    @property
    def members_count(self):
        count = self.member.all().count() + 1
        return count
    
    @property
    def profit_comparison(self):
        profit_records = ClanCompetitionSummary.objects.filter(clan=self).order_by('id')
        num_records = profit_records.count()

        if num_records == 1:
            last_profit_value = round(profit_records[0].profit,2)
            return (last_profit_value, 'equal')

        if num_records >= 2:
            last_profit_value = round(profit_records.last().profit,2)
            second_last_profit_value = round(profit_records[num_records - 2].profit,2)

            if last_profit_value > second_last_profit_value:
                return (last_profit_value, 'up')
            elif last_profit_value < second_last_profit_value:
                return (last_profit_value, 'down')

        # Handle the case where there are no profit records or other exceptional cases
        return (0, 'no_data')

class ClanNameChangeRequest(auto_prefetch.Model):
    clan_owner=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='clan_owner_name',null=True, blank=True)
    clan=auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE, related_name='clan_to_change_name')
    new_clan_name=models.CharField(max_length=200, unique=True,blank=True)
    date_request=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    reason=models.CharField(max_length=200, null=True, blank=True)
    approved=models.CharField(max_length=200,default='pending',choices=(('pending','pending'),('approved','approved'),('rejected','rejected')))

class ClanMemeberRemoverRequest(auto_prefetch.Model):
    clan_owner=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='clan_admin_name',null=True, blank=True)
    clan=auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE, related_name='clan_to_remove_member')
    clan_member_to_remove=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='clan_member',null=True, blank=True)
    reason_for_removal=models.CharField(max_length=200, null=True, blank=True)
    date_request=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    reason=models.CharField(max_length=200, null=True, blank=True)
    approved=models.CharField(max_length=200,default='pending',choices=(('pending','pending'),('approved','approved'),('rejected','rejected')))


class JoinClanRequest(auto_prefetch.Model):
    user=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='join_clan_user',null=True, blank=True)
    clan=auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE, related_name='clan_to_join')
    approved=models.CharField(max_length=200,default='pending',choices=(('pending','pending'),('approved','approved'),('rejected','rejected')))
    date_request=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} | {self.clan} | {self.approved}| {self.date_request}'

    @property
    def user_name(self):
        return f"{self.user.firstname.title()} {self.user.lastname.title()}"

class CreateClanRequest(auto_prefetch.Model):
    clan_admin=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='clan_create_admin', blank=True, null=True)
    clan_name=models.CharField(max_length=200, unique=True,blank=True)
    description = models.TextField(blank=True, null=True)
    community_link=models.URLField(blank=True)
    clan_logo=models.ImageField(upload_to='clan_logos', null=True, blank=True)
    date_request=models.DateTimeField(auto_now_add=True)
    reason=models.CharField(max_length=200, null=True, blank=True)
    approved=models.CharField(max_length=200,default='pending',choices=(('pending','pending'),('approved','approved'),('rejected','rejected')))
    
    
    def __str__(self):
        return f'{self.clan_admin} | {self.clan_name} |{self.approved} '

    @property
    def user_name(self):
        return self.user.email

class TopClanPayout(auto_prefetch.Model):
    choices = (
        ("pending", "Pending"),
        ("declined", "Declined"),
        ("approved", "Approved"),
    )
    payoutchoices = (
        ("Clan Payout", "Clan Payout"),
        
    )
    clan = auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE,null=True, blank=True )
    date = models.DateTimeField(auto_now_add=True, blank=True)
    paytype = models.CharField(max_length=255,choices=payoutchoices, blank=True, null=True)
    status = models.CharField(max_length=255, choices=choices, blank=True)
    profit=models.IntegerField(null=True, blank=True)
    amount = models.CharField(max_length=255, blank=True, default="Processing")
    reason = models.CharField(max_length=255, blank=True, default="")
    comment=models.CharField(max_length=255, default="")
    payment_date = models.DateField(blank=True, null=True)
    position=models.PositiveIntegerField(blank=True, null=True)
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE,null=True, blank=True)
    

    def __str__(self):

        return 'Payout' + '-' + str(self.clan)
class TopClanMembersPayout(auto_prefetch.Model):
    choices = (
        ("pending", "Pending"),
        ("declined", "Declined"),
        ("approved", "Approved"),
    )
    payoutchoices = (
        ("Clan  Payout", "Clan Payout"),
        
    )
    top_clan_payout = auto_prefetch.ForeignKey(TopClanPayout, on_delete=models.CASCADE,null=True, blank=True )
    user = auto_prefetch.ForeignKey(User,on_delete=models.CASCADE,null=True, blank=True)
    paytype = models.CharField(max_length=255,default='Clan Payout',choices=payoutchoices, blank=True, null=True)
    status = models.CharField(max_length=255, choices=choices, blank=True, default='Unprocessed')
    amount = models.CharField(max_length=255, blank=True, default="Processing")
    reason = models.CharField(max_length=255, blank=True, default="")
    comment=models.CharField(max_length=255, default="")
    payment_date = models.DateField(blank=True, null=True)
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio,on_delete=models.CASCADE,null=True, blank=True)


class TopClanPayoutButtonShows(auto_prefetch.Model):
    clan = auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE,blank=True, null=True)
    paydate = models.DateField(auto_now_add=True)

class TopClanPayoutImg(auto_prefetch.Model):
    payout = auto_prefetch.ForeignKey(TopClanPayout, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="PaymentsImgs/", max_length=355, blank=True)
    
class TopClanMembersPayoutImg(auto_prefetch.Model):
    payout = auto_prefetch.ForeignKey(TopClanMembersPayout, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="PaymentsImgs/", max_length=355, blank=True)

class TopTraderPayout(auto_prefetch.Model):
    choices = (
        ("pending", "Pending"),
        ("declined", "Declined"),
        ("approved", "Approved"),
    )
    payoutchoices = (
        ("Top Trader Payout", "Top Trader Payout"),
        
    )
    portfolio = auto_prefetch.ForeignKey(
        CompetitionPortfolio, on_delete=models.CASCADE, related_name="_leaderboard_accuser",null=True, blank=True
    )

    date = models.DateTimeField(auto_now_add=True,blank=True, null=True)
    paytype = models.CharField(max_length=255,choices=payoutchoices,default="Top Trader Payout", blank=True, null=True)
    status = models.CharField(max_length=255, choices=choices,default="pending",blank=True)
    amount = models.CharField(max_length=255, blank=True, default="Processing")
    comment = models.CharField(max_length=255, blank=True, default="")
    payment_date = models.DateField(blank=True, null=True)
    position=models.PositiveIntegerField(blank=True, null=True)
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE,null=True, blank=True)
    profit=models.IntegerField(null=True, blank=True)
    

    def __str__(self):
        return 'Payout' + '-' + str(self.portfolio.user.email)

class TopTraderPayoutButtonShows(auto_prefetch.Model):
    portfolio = auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE)
    paydate = models.DateField(auto_now_add=True)

class TopTraderPayoutImg(auto_prefetch.Model):
    payout = auto_prefetch.ForeignKey(TopTraderPayout, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="PaymentsImgs/", max_length=355, blank=True)

class Notification(auto_prefetch.Model):
    message=models.CharField(max_length=200)
    clan_admin=auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE)

    def __str__(self):
        return self.clan_admin


class CompetitionSummary(auto_prefetch.Model):
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE,null=True, blank=True)
    user=auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='summary_clan_user',null=True, blank=True)
    portfolio=auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, blank=True, null=True)
    clan=auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE, related_name='summary_clan', blank=True, null=True)
    profit=models.FloatField(blank=True,null=True)
    created_at=models.DateTimeField(blank=True,null=True, auto_now_add=True)
    updated_at=models.DateTimeField(blank=True,null=True, auto_now=True)
    position=models.PositiveIntegerField(blank=True, null=True)
    trading_days=models.PositiveIntegerField(blank=True, null=True)
    

    def __str__(self):
        return f"{self.user.email} | {self.clan} | {self.competition.title} | {self.position}"

    @property
    def clan_name(self):
        return self.clan.clan_name
    @property
    def competition_title(self):
        return self.competition.title
    @property
    def country(self):
        user=self.user
        profile=Profile.objects.get(user=user)
        return profile.country
    @property
    def email(self):
        return self.user.email
    @property
    def fullname(self):
        return f'{self.user.firstname} {self.user.lastname}'
    
class ClanCompetitionSummary(auto_prefetch.Model):
    competition=auto_prefetch.ForeignKey(Competition, on_delete=models.CASCADE,null=True, blank=True)
    clan=auto_prefetch.ForeignKey(Clan, on_delete=models.CASCADE)
    profit=models.FloatField(blank=True,null=True)
    created_at=models.DateTimeField(blank=True,null=True, auto_now_add=True)
    updated_at=models.DateTimeField(blank=True,null=True, auto_now=True)
    position=models.PositiveIntegerField(blank=True, null=True)
    
    def __str__(self) -> str:
        return f"{self.competition.title} - {self.clan} - {self.position}"
    
class CompetitionDailyReturns2(auto_prefetch.Model):
    # user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='compreturns2')
    portfolio_returns = models.FloatField(default=0.0)
    portfolio=auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, blank=True, null=True)
    created =models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.created:
            return f"{self.portfolio.user} {self.portfolio_returns} - {self.created.date()}"
        else:
            return f"{self.portfolio_returns}"
    
class CompetitionCumulativeReturns2(auto_prefetch.Model):
    # user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, related_name='compcumureturns2')
    portfolio=auto_prefetch.ForeignKey(CompetitionPortfolio, on_delete=models.CASCADE, blank=True, null=True)
    portfolio_returns = models.FloatField(default=0.0)
    created =models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.created:
            return f"{self.portfolio.user} {self.portfolio_returns} - {self.created.date()}"
        else:
            return f"{self.portfolio_returns}"
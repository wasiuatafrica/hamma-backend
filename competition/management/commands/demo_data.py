import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from competition.models import  Clan, Competition, CompetitionPortfolio, CompetitionPosition
from django.contrib.auth.hashers import make_password
from faker import Faker
from datetime import datetime
from django.contrib.auth import get_user_model

User =get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Create demo data including users, clans, competitions, portfolios, and positions'

    def handle(self, *args, **kwargs):
        # self.create_users(100)
        # clans = self.create_clans(10)
        # self.assign_clan_members_and_admins(clans)
        competition = self.create_competition()
        self.create_competition_portfolios(competition)
        self.stdout.write(self.style.SUCCESS('Demo data created successfully.'))

    def create_users(self, number):
        for i in range(number):
            User.objects.create(
                email=fake.email(),
                firstname=fake.first_name(),
                lastname=fake.last_name(),
                is_active=True,
                password=make_password(f'paloword123{i}')
            )
        self.stdout.write(self.style.SUCCESS(f'{number} users created successfully.'))

    def create_clans(self, number):
        clans = []
        for i in range(number):
            clan = Clan.objects.create(
                clan_name=fake.company(),
                community_link=fake.url(),
                description=fake.text()
            )
            clans.append(clan)
        self.stdout.write(self.style.SUCCESS(f'{number} clans created successfully.'))
        return clans

    def assign_clan_members_and_admins(self, clans):
        users = list(User.objects.all())
        random.shuffle(users)
        
        for clan in clans:
            admin = users.pop()
            clan.clan_admin = admin
            clan.save()
            members = users[:9]
            clan.member.set(members)
            users = users[9:]
        
        self.stdout.write(self.style.SUCCESS('Users assigned as clan admins and members.'))

    def create_competition(self):
        current_competition = Competition.objects.filter(status='current')
        if current_competition.exists():
            current_competition.first().status = 'closed'
            current_competition.first().save()
            
        competition = Competition.objects.create(
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            title='Sample Competition' + str(datetime.now()),
            status='current'
        )
        self.stdout.write(self.style.SUCCESS('Competition created successfully.'))
        return competition

    def create_competition_portfolios(self, competition):
        users = User.objects.all()
        for user in users:
            portfolio = CompetitionPortfolio.objects.create(
                competition=competition,
                user=user,
                balance=random.uniform(1000, 100000)
            )
            self.create_competition_positions(portfolio)
        self.stdout.write(self.style.SUCCESS('Competition portfolios and positions created successfully.'))

    def create_competition_positions(self, portfolio):
        for _ in range(10):
            open_price = round(random.uniform(10, 500), 2)
            close_price = open_price + round(random.uniform(-5, 5), 2)
            quantity = random.randint(100, 10000)
            status = random.choice(['open', 'close'])

            # Calculate profit_loss if the position is closed
            profit_loss = None
            if status == 'close':
                profit_loss = (close_price - open_price) * quantity

            CompetitionPosition.objects.create(
                portfolio=portfolio,
                stock_id=random.randint(1, 130),  # Assuming you have stocks with IDs 1-100
                quantity=quantity,
                open_price=open_price,
                close_price=close_price if status == 'close' else None,
                status=status,
                amount_invested=round(open_price * quantity, 2),
                action=random.choice(['buy', 'sell']),
                profit_loss=profit_loss
            )


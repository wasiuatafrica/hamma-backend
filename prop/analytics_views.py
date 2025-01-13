from datetime import date as dt
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    DateField,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Trunc
from django.utils import timezone
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Referral
from execution.models import DemoPortfolio, DemoPosition, PropReceipt, Receipts

from .models import Payout

User = get_user_model()


class DemoAnalyticsView(APIView):
    permission_classes = [AllowAny]

    def get_timeframes(self):
        """Get time ranges for the different periods."""
        now = timezone.now()
        return {
            "24hrs": now - timedelta(days=1),
            "prev_24hrs_start": now - timedelta(days=2),
            "prev_24hrs_end": now - timedelta(days=1),
            "1week": now - timedelta(weeks=1),
            "prev_1week_start": now - timedelta(weeks=2),
            "prev_1week_end": now - timedelta(weeks=1),
            "1month": now - timedelta(days=30),
            "prev_1month_start": now - timedelta(days=60),
            "prev_1month_end": now - timedelta(days=30),
            "6months": now - timedelta(days=180),
            "prev_6months_start": now - timedelta(days=360),
            "prev_6months_end": now - timedelta(days=180),
            "1year": now - timedelta(days=365),
            "prev_1year_start": now - timedelta(days=730),
            "prev_1year_end": now - timedelta(days=365),
        }

    def get_percentage(self, current, previous):
        """Calculate percentage change from previous to current."""
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 2)

    def get_metrics(self, time_range=None, end_time=None):
        """Fetch data based on time range."""
        if end_time:
            demo_accounts = DemoPortfolio.objects.filter(
                is_prop=True,
                created__gte=time_range,
                created__lt=end_time,
            )
            blown_accounts = DemoPortfolio.objects.filter(
                is_prop=True, updated__gte=time_range, updated__lt=end_time, blown=True
            )
            discounted_accounts = DemoPortfolio.objects.filter(
                is_prop=True,
                discount_code__isnull=False,
                created__gte=time_range,
                created__lt=end_time,
            )
            prop_receipts = PropReceipt.objects.filter(
                receipt__date__gte=time_range,
                receipt__date__lt=end_time,
                receipt__receipt_status="Confirmed",
            )
            payouts = Payout.objects.filter(
                process_date__gte=time_range, process_date__lt=end_time, status="paid"
            )
            passed_accounts = DemoPortfolio.objects.filter(
                is_prop=True,
                passed_date__gte=time_range,
                passed_date__lt=end_time,
                target_met=True,
            )
        else:
            demo_accounts = (
                DemoPortfolio.objects.filter(is_prop=True, created__gte=time_range)
                if time_range
                else DemoPortfolio.objects.filter(is_prop=True)
            )
            blown_accounts = (
                DemoPortfolio.objects.filter(
                    is_prop=True, updated__gte=time_range, blown=True
                )
                if time_range
                else DemoPortfolio.objects.filter(is_prop=True, blown=True)
            )
            discounted_accounts = (
                DemoPortfolio.objects.filter(
                    is_prop=True, discount_code__isnull=False, created__gte=time_range
                )
                if time_range
                else DemoPortfolio.objects.filter(
                    is_prop=True, discount_code__isnull=False
                )
            )
            prop_receipts = (
                PropReceipt.objects.filter(
                    receipt__receipt_status="approved", receipt__date__gte=time_range
                )
                if time_range
                else PropReceipt.objects.filter(receipt__receipt_status="approved")
            )
            payouts = (
                Payout.objects.filter(process_date__gte=time_range, status="paid")
                if time_range
                else Payout.objects.filter(status="paid")
            )
            passed_accounts = (
                DemoPortfolio.objects.filter(
                    is_prop=True, passed_date__gte=time_range, target_met=True
                )
                if time_range
                else DemoPortfolio.objects.filter(is_prop=True, target_met=True)
            )

        total_accounts = demo_accounts.count()
        total_blown = blown_accounts.count()
        total_discounted = discounted_accounts.count()
        total_receipts = prop_receipts.count()
        total_payouts = payouts.count()
        total_passed = passed_accounts.count()

        # Calculate total payout amount
        total_payout_amount = payouts.aggregate(total=Sum("amount"))["total"] or 0

        return {
            "total_accounts": total_accounts,
            "total_blown": total_blown,
            "total_discounted": total_discounted,
            "total_receipts": total_receipts,
            "total_payouts": total_payouts,
            "total_passed": total_passed,
            "total_payout_amount": float(total_payout_amount),
            "blown_rate": (
                round((total_blown / total_accounts * 100), 2)
                if total_accounts > 0
                else 0
            ),
            "pass_rate": (
                round((total_passed / total_accounts * 100), 2)
                if total_accounts > 0
                else 0
            ),
        }

    def calculate_percentage_changes(self, current_metrics, previous_metrics):
        """Calculate percentage changes for each metric."""
        percentage_changes = {}
        for key in current_metrics:
            current_value = current_metrics[key]
            previous_value = previous_metrics[key]
            percentage_changes[key] = self.get_percentage(current_value, previous_value)
        return percentage_changes

    def combine_metrics_and_changes(self, current_metrics, percentage_changes):
        """Combine metrics with their corresponding percentage change."""
        combined_data = {}
        for key, value in current_metrics.items():
            combined_data[key] = value
            combined_data[f"{key}_change"] = percentage_changes.get(key, 0)
        return combined_data

    def get(self, request):
        timeframes = self.get_timeframes()

        current_data = {
            "last_1week": self.get_metrics(timeframes["1week"]),
            "last_1month": self.get_metrics(timeframes["1month"]),
            "last_6months": self.get_metrics(timeframes["6months"]),
            "last_1year": self.get_metrics(timeframes["1year"]),
            "total": self.get_metrics(),
        }

        previous_data = {
            "prev_1week": self.get_metrics(
                timeframes["prev_1week_start"], timeframes["prev_1week_end"]
            ),
            "prev_1month": self.get_metrics(
                timeframes["prev_1month_start"], timeframes["prev_1month_end"]
            ),
            "prev_6months": self.get_metrics(
                timeframes["prev_6months_start"], timeframes["prev_6months_end"]
            ),
            "prev_1year": self.get_metrics(
                timeframes["prev_1year_start"], timeframes["prev_1year_end"]
            ),
        }

        percentage_changes = {
            "1week_change": self.calculate_percentage_changes(
                current_data["last_1week"], previous_data["prev_1week"]
            ),
            "1month_change": self.calculate_percentage_changes(
                current_data["last_1month"], previous_data["prev_1month"]
            ),
            "6months_change": self.calculate_percentage_changes(
                current_data["last_6months"], previous_data["prev_6months"]
            ),
            "1year_change": self.calculate_percentage_changes(
                current_data["last_1year"], previous_data["prev_1year"]
            ),
        }

        combined_data = {
            "last_1week": self.combine_metrics_and_changes(
                current_data["last_1week"], percentage_changes["1week_change"]
            ),
            "last_1month": self.combine_metrics_and_changes(
                current_data["last_1month"], percentage_changes["1month_change"]
            ),
            "last_6months": self.combine_metrics_and_changes(
                current_data["last_6months"], percentage_changes["6months_change"]
            ),
            "last_1year": self.combine_metrics_and_changes(
                current_data["last_1year"], percentage_changes["1year_change"]
            ),
            "total": current_data["total"],
        }

        return Response(combined_data)


class DemoPortfolioAnalyticsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Get active users
        users = User.objects.filter(is_active=True)

        # Get demo portfolios
        demo_portfolios = DemoPortfolio.objects.filter(is_prop=True)

        ### User Registrations Analytics ###
        last_week_user_data = (
            users.filter(
                date_joined__gte=(timezone.now() - timedelta(days=7)).replace(hour=0)
            )
            .annotate(date=Trunc("date_joined", "day", output_field=DateField()))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_month_user_data = (
            users.filter(
                date_joined__gte=(timezone.now() - timedelta(days=30)).replace(hour=0)
            )
            .annotate(date=Trunc("date_joined", "day", output_field=DateField()))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_3_months_user_data = (
            users.filter(
                date_joined__gte=(timezone.now() - timedelta(days=90)).replace(hour=0)
            )
            .annotate(date=Trunc("date_joined", "week", output_field=DateField()))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_6_months_user_data = (
            users.filter(
                date_joined__gte=(timezone.now() - timedelta(days=180)).replace(hour=0)
            )
            .annotate(date=Trunc("date_joined", "week", output_field=DateField()))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_year_user_data = (
            users.filter(
                date_joined__gte=(timezone.now() - timedelta(days=365)).replace(hour=0)
            )
            .annotate(date=Trunc("date_joined", "month", output_field=DateField()))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        total_user_data = (
            users.annotate(date=Trunc("date_joined", "month", output_field=DateField()))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        ### Demo Portfolio Analytics ###
        # Define model types and account labels
        portfolio_labels = [
            "model_1_10M",
            "model_1_5M",
            "model_1_1M",
            "model_2_10M",
            "model_2_5M",
            "model_2_1M",
        ]

        demo_portfolios = demo_portfolios.annotate(
            portfolio_label=Case(
                # Model 1 combinations
                When(
                    model_type="model_1",
                    initial_balance=10000000,
                    then=Value("model_1_10M"),
                ),
                When(
                    model_type="model_1",
                    initial_balance=5000000,
                    then=Value("model_1_5M"),
                ),
                When(
                    model_type="model_1",
                    initial_balance=1000000,
                    then=Value("model_1_1M"),
                ),
                # Model 2 combinations
                When(
                    model_type="model_2",
                    initial_balance=10000000,
                    then=Value("model_2_10M"),
                ),
                When(
                    model_type="model_2",
                    initial_balance=5000000,
                    then=Value("model_2_5M"),
                ),
                When(
                    model_type="model_2",
                    initial_balance=1000000,
                    then=Value("model_2_1M"),
                ),
                default=None,
                output_field=CharField(),
            )
        ).filter(portfolio_label__isnull=False)

        # Get data for different time periods
        last_week_portfolio_data = (
            demo_portfolios.filter(
                created__gte=(timezone.now() - timedelta(days=7)).replace(hour=0)
            )
            .annotate(date=Trunc("created", "day", output_field=DateField()))
            .values("date", "portfolio_label")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_month_portfolio_data = (
            demo_portfolios.filter(
                created__gte=(timezone.now() - timedelta(days=30)).replace(hour=0)
            )
            .annotate(date=Trunc("created", "day", output_field=DateField()))
            .values("date", "portfolio_label")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_3_months_portfolio_data = (
            demo_portfolios.filter(
                created__gte=(timezone.now() - timedelta(days=90)).replace(hour=0)
            )
            .annotate(date=Trunc("created", "week", output_field=DateField()))
            .values("date", "portfolio_label")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_6_months_portfolio_data = (
            demo_portfolios.filter(
                created__gte=(timezone.now() - timedelta(days=180)).replace(hour=0)
            )
            .annotate(date=Trunc("created", "week", output_field=DateField()))
            .values("date", "portfolio_label")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        last_year_portfolio_data = (
            demo_portfolios.filter(
                created__gte=(timezone.now() - timedelta(days=365)).replace(hour=0)
            )
            .annotate(date=Trunc("created", "month", output_field=DateField()))
            .values("date", "portfolio_label")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        total_portfolio_data = (
            demo_portfolios.annotate(
                date=Trunc("created", "month", output_field=DateField())
            )
            .values("date", "portfolio_label")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        ### Merging Data ###
        last_week_data = self.merge_data(
            last_week_user_data, last_week_portfolio_data, portfolio_labels
        )
        last_month_data = self.merge_data(
            last_month_user_data, last_month_portfolio_data, portfolio_labels
        )
        last_3_months_data = self.merge_data(
            last_3_months_user_data, last_3_months_portfolio_data, portfolio_labels
        )
        last_6_months_data = self.merge_data(
            last_6_months_user_data, last_6_months_portfolio_data, portfolio_labels
        )
        last_year_data = self.merge_data(
            last_year_user_data, last_year_portfolio_data, portfolio_labels
        )
        total_data = self.merge_data(
            total_user_data, total_portfolio_data, portfolio_labels
        )

        grouped_data = {
            "last_week_data": last_week_data,
            "last_month_data": last_month_data,
            "last_3_months_data": last_3_months_data,
            "last_6_months_data": last_6_months_data,
            "last_year_data": last_year_data,
            "total_data": total_data,
        }

        return Response(grouped_data)

    def merge_data(self, data_list1, data_list2, portfolio_labels):
        organized_data = {}

        # Process user data
        for data_point in data_list1:
            date = data_point["date"]
            if date not in organized_data:
                organized_data[date] = {
                    "date": date,
                    "registered_users": 0,
                    "demo_portfolios": 0,
                }
                # Initialize all portfolio labels with 0
                for label in portfolio_labels:
                    organized_data[date][label] = 0

            organized_data[date]["registered_users"] = data_point.get("count", 0)

        # Process portfolio data
        for data_point2 in data_list2:
            date = data_point2["date"]
            portfolio_label = data_point2.get("portfolio_label")

            if portfolio_label in portfolio_labels:
                if date not in organized_data:
                    organized_data[date] = {
                        "date": date,
                        "registered_users": 0,
                        "demo_portfolios": 0,
                    }
                    # Initialize all portfolio labels with 0
                    for label in portfolio_labels:
                        organized_data[date][label] = 0

                organized_data[date]["demo_portfolios"] += data_point2.get("count", 0)
                organized_data[date][portfolio_label] += data_point2.get("count", 0)

        # Convert to sorted list
        result = list(organized_data.values())
        result.sort(key=lambda x: x["date"])

        return result


class DemoStatsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        time_ranges = {
            "last_month": (now - timedelta(weeks=4), now),
            "last_6_months": (now - timedelta(days=182), now),
            "last_year": (now - timedelta(days=365), now),
        }

        previous_time_ranges = {
            "last_month": (now - timedelta(weeks=8), now - timedelta(weeks=4)),
            "last_6_months": (now - timedelta(days=365), now - timedelta(days=182)),
            "last_year": (now - timedelta(days=730), now - timedelta(days=365)),
        }

        total_users = User.objects.all()

        def calculate_metrics(total_users, start_date, end_date):
            if start_date and end_date:
                users_in_period = total_users.filter(
                    date_joined__gte=start_date, date_joined__lt=end_date
                )
                blown_accounts = DemoPortfolio.objects.filter(
                    is_prop=True,
                    updated__gte=start_date,
                    updated__lt=end_date,
                    blown=True,
                )
            else:
                users_in_period = total_users
                blown_accounts = DemoPortfolio.objects.filter(is_prop=True, blown=True)

            # Users with demo portfolios
            users_with_portfolios = users_in_period.filter(
                demoportfolio2__is_prop=True,
                demoportfolio2__created__gt=F("date_joined") + timedelta(weeks=4),
                demoportfolio2__is_active=True,
            ).distinct()

            percentage_with_portfolios = (
                users_with_portfolios.count() / users_in_period.count() * 100
                if users_in_period.count() > 0
                else 0
            )

            # Users with portfolios within 4 weeks
            users_with_portfolios_within_4weeks = users_in_period.filter(
                demoportfolio2__is_prop=True,
                demoportfolio2__created__lte=F("date_joined") + timedelta(weeks=4),
                demoportfolio2__is_active=True,
            ).distinct()

            percentage_with_portfolios_within_4weeks = (
                users_with_portfolios_within_4weeks.count()
                / users_in_period.count()
                * 100
                if users_in_period.count() > 0
                else 0
            )

            # Users with referrals within 4 weeks
            users_with_referrals = users_in_period.annotate(
                weeks_since_registration=F("date_joined") + timedelta(weeks=4)
            ).filter(
                referral__person_referred__date_joined__lte=F(
                    "weeks_since_registration"
                )
            )

            percentage_with_referrals = (
                users_with_referrals.count() / users_in_period.count() * 100
                if users_in_period.count() > 0
                else 0
            )

            # Users with multiple referrals within 4 weeks
            users_with_multiple_referrals = (
                users_in_period.annotate(
                    weeks_since_registration=F("date_joined") + timedelta(weeks=4)
                )
                .annotate(num_referrals=Count("referral"))
                .filter(
                    num_referrals__gte=2,
                    referral__person_referred__date_joined__lte=F(
                        "weeks_since_registration"
                    ),
                    referral__person_referred__demoportfolio2__isnull=False,
                )
            )

            percentage_with_multiple_referrals = (
                users_with_multiple_referrals.count() / users_in_period.count() * 100
                if users_in_period.count() > 0
                else 0
            )

            # Users with first portfolio date
            users_with_first_portfolio_date = users_in_period.annotate(
                first_portfolio_date=Subquery(
                    User.objects.filter(
                        pk=OuterRef("pk"),
                        demoportfolio2__isnull=False,
                        demoportfolio2__is_prop=True,
                    )
                    .values("demoportfolio2__created")
                    .order_by("demoportfolio2__created")[:1]
                )
            )

            # Users with multiple referrals who became traders
            users_with_multiple_referrals_traders = (
                users_with_first_portfolio_date.annotate(
                    num_trader_referrals=Subquery(
                        Referral.objects.filter(
                            user=OuterRef("pk"),
                            person_referred__demoportfolio2__isnull=False,
                            person_referred__demoportfolio2__is_prop=True,
                            person_referred__demoportfolio2__created__lte=OuterRef(
                                "first_portfolio_date"
                            )
                            + timedelta(weeks=4),
                            person_referred__demoportfolio2__created__gt=OuterRef(
                                "first_portfolio_date"
                            ),
                        )
                        .values("user")
                        .annotate(count=Count("person_referred", distinct=True))
                        .values("count")[:1]
                    )
                ).filter(num_trader_referrals__gte=1)
            )

            percentage_with_multiple_referrals_traders = (
                users_with_multiple_referrals_traders.count()
                / users_in_period.count()
                * 100
                if users_in_period.count() > 0
                else 0
            )

            # Number of blown accounts
            num_blown = blown_accounts.count()

            # Average time to blown account
            avg_time_to_blown = blown_accounts.aggregate(
                avg_time=Avg(F("updated") - F("created"))
            )["avg_time"]

            return {
                "percentage_with_portfolios": percentage_with_portfolios,
                "percentage_with_portfolios_within_4weeks": percentage_with_portfolios_within_4weeks,
                "percentage_with_referrals": percentage_with_referrals,
                "percentage_with_multiple_referrals": percentage_with_multiple_referrals,
                "percentage_with_multiple_referrals_traders": percentage_with_multiple_referrals_traders,
                "num_blown": num_blown,
                "avg_time_to_blown": (
                    avg_time_to_blown.days if avg_time_to_blown else None
                ),
            }

        # Calculate metrics for each period
        response_data = {}
        for period_name, (start_date, end_date) in time_ranges.items():
            response_data[period_name] = calculate_metrics(
                total_users, start_date, end_date
            )

        # Calculate total metrics
        response_data["total"] = calculate_metrics(total_users, None, None)

        def calculate_change(current, previous):
            if previous == 0:
                return None if current == 0 else 100
            return ((current - previous) / previous) * 100

        def add_changes_to_metrics(current_period, previous_period):
            metrics = [
                "percentage_with_portfolios",
                "percentage_with_portfolios_within_4weeks",
                "percentage_with_referrals",
                "percentage_with_multiple_referrals",
                "percentage_with_multiple_referrals_traders",
                "num_blown",
            ]

            result = {}
            for metric in metrics:
                result[metric] = {
                    "current": round(current_period[metric], 2),
                    "change": (
                        round(
                            calculate_change(
                                current_period[metric], previous_period[metric]
                            ),
                            1,
                        )
                        if calculate_change(
                            current_period[metric], previous_period[metric]
                        )
                        is not None
                        else None
                    ),
                }

            result["avg_time_to_blown"] = current_period["avg_time_to_blown"]
            return result

        # Add comparison changes for each period
        for period_name in time_ranges.keys():
            current_period = response_data[period_name]
            previous_period = calculate_metrics(
                total_users, *previous_time_ranges[period_name]
            )
            response_data[period_name] = add_changes_to_metrics(
                current_period, previous_period
            )

        return Response(response_data)


# class DemoStatsAPIView(APIView):
#     permission_classes = [AllowAny]

#     def get(self, request, *args, **kwargs):
#         now = timezone.now()
#         time_ranges = {
#             "last_month": (now - timedelta(weeks=4), now),
#             "last_6_months": (now - timedelta(days=182), now),
#             "last_year": (now - timedelta(days=365), now),
#         }

#         previous_time_ranges = {
#             "last_month": (now - timedelta(weeks=8), now - timedelta(weeks=4)),
#             "last_6_months": (now - timedelta(days=365), now - timedelta(days=182)),
#             "last_year": (now - timedelta(days=730), now - timedelta(days=365)),
#         }

#         account_sizes = [10000000, 5000000, 1000000]
#         total_users = User.objects.all()

#         def calculate_metrics(total_users, start_date, end_date):
#             metrics_by_size = {}

#             for account_size in account_sizes:
#                 if start_date and end_date:
#                     users_in_period = total_users.filter(
#                         date_joined__gte=start_date, date_joined__lt=end_date
#                     )
#                     blown_accounts = DemoPortfolio.objects.filter(
#                         is_prop=True,
#                         updated__gte=start_date,
#                         updated__lt=end_date,
#                         blown=True,
#                         initial_balance=account_size
#                     )
#                 else:
#                     users_in_period = total_users
#                     blown_accounts = DemoPortfolio.objects.filter(
#                         is_prop=True,
#                         blown=True,
#                         initial_balance=account_size
#                     )

#                 # Users with demo portfolios for specific account size
#                 users_with_portfolios = users_in_period.filter(
#                     demoportfolio2__is_prop=True,
#                     demoportfolio2__created__gt=F("date_joined") + timedelta(weeks=4),
#                     demoportfolio2__is_active=True,
#                     demoportfolio2__initial_balance=account_size
#                 ).distinct()

#                 percentage_with_portfolios = (
#                     users_with_portfolios.count() / users_in_period.count() * 100
#                     if users_in_period.count() > 0
#                     else 0
#                 )

#                 # Users with portfolios within 4 weeks for specific account size
#                 users_with_portfolios_within_4weeks = users_in_period.filter(
#                     demoportfolio2__is_prop=True,
#                     demoportfolio2__created__lte=F("date_joined") + timedelta(weeks=4),
#                     demoportfolio2__is_active=True,
#                     demoportfolio2__initial_balance=account_size
#                 ).distinct()

#                 percentage_with_portfolios_within_4weeks = (
#                     users_with_portfolios_within_4weeks.count() / users_in_period.count() * 100
#                     if users_in_period.count() > 0
#                     else 0
#                 )

#                 # Users with referrals who got specific account size
#                 users_with_referrals = users_in_period.annotate(
#                     weeks_since_registration=F("date_joined") + timedelta(weeks=4)
#                 ).filter(
#                     referral__person_referred__date_joined__lte=F("weeks_since_registration"),
#                     referral__person_referred__demoportfolio2__initial_balance=account_size
#                 )

#                 percentage_with_referrals = (
#                     users_with_referrals.count() / users_in_period.count() * 100
#                     if users_in_period.count() > 0
#                     else 0
#                 )

#                 # Users with multiple referrals for specific account size
#                 users_with_multiple_referrals = users_in_period.annotate(
#                     weeks_since_registration=F("date_joined") + timedelta(weeks=4)
#                 ).annotate(
#                     num_referrals=Count(
#                         'referral',
#                         filter=Q(
#                             referral__person_referred__demoportfolio2__initial_balance=account_size,
#                             referral__person_referred__date_joined__lte=F("weeks_since_registration")
#                         )
#                     )
#                 ).filter(num_referrals__gte=2)

#                 percentage_with_multiple_referrals = (
#                     users_with_multiple_referrals.count() / users_in_period.count() * 100
#                     if users_in_period.count() > 0
#                     else 0
#                 )

#                 # Users with multiple referrals who became traders with specific account size
#                 users_with_multiple_referrals_traders = (
#                     users_in_period.annotate(
#                         first_portfolio_date=Subquery(
#                             DemoPortfolio.objects.filter(
#                                 user=OuterRef("pk"),
#                                 is_prop=True,
#                                 initial_balance=account_size
#                             ).values('created').order_by('created')[:1]
#                         )
#                     ).annotate(
#                         num_trader_referrals=Subquery(
#                             Referral.objects.filter(
#                                 user=OuterRef("pk"),
#                                 person_referred__demoportfolio2__initial_balance=account_size,
#                                 person_referred__demoportfolio2__created__lte=OuterRef("first_portfolio_date") + timedelta(weeks=4),
#                                 person_referred__demoportfolio2__created__gt=OuterRef("first_portfolio_date"),
#                             ).values('user')
#                             .annotate(count=Count('person_referred', distinct=True))
#                             .values('count')[:1]
#                         )
#                     ).filter(num_trader_referrals__gte=1)
#                 )

#                 percentage_with_multiple_referrals_traders = (
#                     users_with_multiple_referrals_traders.count() / users_in_period.count() * 100
#                     if users_in_period.count() > 0
#                     else 0
#                 )

#                 # Stats for specific account size
#                 metrics_by_size[f"{account_size:,}"] = {
#                     "percentage_with_portfolios": percentage_with_portfolios,
#                     "percentage_with_portfolios_within_4weeks": percentage_with_portfolios_within_4weeks,
#                     "percentage_with_referrals": percentage_with_referrals,
#                     "percentage_with_multiple_referrals": percentage_with_multiple_referrals,
#                     "percentage_with_multiple_referrals_traders": percentage_with_multiple_referrals_traders,
#                     "num_blown": blown_accounts.count(),
#                     "avg_time_to_blown": blown_accounts.aggregate(
#                         avg_time=Avg(F("updated") - F("created"))
#                     )["avg_time"],
#                 }

#             return metrics_by_size

#         # Calculate metrics for each period
#         response_data = {}
#         for period_name, (start_date, end_date) in time_ranges.items():
#             response_data[period_name] = calculate_metrics(total_users, start_date, end_date)

#         # Calculate total metrics
#         response_data["total"] = calculate_metrics(total_users, None, None)

#         def calculate_change(current, previous):
#             if previous == 0:
#                 return None if current == 0 else 100
#             return ((current - previous) / previous) * 100

#         def add_changes_to_metrics(current_period, previous_period):
#             result = {}
#             for account_size in account_sizes:
#                 size_key = f"{account_size:,}"
#                 metrics = [
#                     "percentage_with_portfolios",
#                     "percentage_with_portfolios_within_4weeks",
#                     "percentage_with_referrals",
#                     "percentage_with_multiple_referrals",
#                     "percentage_with_multiple_referrals_traders",
#                     "num_blown",
#                 ]

#                 result[size_key] = {}
#                 for metric in metrics:
#                     result[size_key][metric] = {
#                         "current": round(current_period[size_key][metric], 2),
#                         "change": (
#                             round(
#                                 calculate_change(
#                                     current_period[size_key][metric],
#                                     previous_period[size_key][metric]
#                                 ),
#                                 1,
#                             )
#                             if calculate_change(
#                                 current_period[size_key][metric],
#                                 previous_period[size_key][metric]
#                             ) is not None
#                             else None
#                         ),
#                     }

#                 result[size_key]["avg_time_to_blown"] = (
#                     current_period[size_key]["avg_time_to_blown"].days
#                     if current_period[size_key]["avg_time_to_blown"]
#                     else None
#                 )

#             return result

#         # Add comparison changes for each period
#         for period_name in time_ranges.keys():
#             current_period = response_data[period_name]
#             previous_period = calculate_metrics(total_users, *previous_time_ranges[period_name])
#             response_data[period_name] = add_changes_to_metrics(current_period, previous_period)

#         return Response(response_data)


class PortfoliosByTypeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        now = timezone.now()

        # Define time periods (unchanged)
        periods = {
            "last_24_hours": now - timedelta(hours=24),
            "last_1_week": now - timedelta(weeks=1),
            "last_1_month": now - timedelta(days=30),
            "last_6_months": now - timedelta(days=30 * 6),
            "last_1_year": now - timedelta(days=365),
        }

        # Create dictionaries to hold the result for each time period
        broker_data = {}
        balance_data = {}
        model_type_data = {}
        combined_stats_data = (
            {}
        )  # New dictionary for combined model_type and balance stats

        # For each time period, filter portfolios
        for period, start_time in periods.items():
            # Broker against count (unchanged)
            portfolios_per_broker = (
                DemoPortfolio.objects.filter(
                    created__gte=start_time, is_active=True, is_prop=True
                )
                .values("broker")
                .annotate(portfolio_count=Count("id"))
                .order_by("-portfolio_count")
            )

            broker_data[period] = [
                {
                    "broker": portfolio["broker"],
                    "portfolio_count": portfolio["portfolio_count"],
                }
                for portfolio in portfolios_per_broker
            ]

            # Initial balance against count
            portfolios_per_balance = (
                DemoPortfolio.objects.filter(
                    created__gte=start_time, is_active=True, is_prop=True
                )
                .values("initial_balance", "model_type")  # Added model_type
                .annotate(portfolio_count=Count("id"))
                .order_by("-portfolio_count")
            )

            balance_data[period] = [
                {
                    "initial_balance": portfolio["initial_balance"],
                    "model_type": portfolio["model_type"],
                    "portfolio_count": portfolio["portfolio_count"],
                }
                for portfolio in portfolios_per_balance
            ]

            # Model type against count (with initial_balance)
            portfolios_per_model_type = (
                DemoPortfolio.objects.filter(
                    created__gte=start_time, is_active=True, is_prop=True
                )
                .values("model_type", "initial_balance")
                .annotate(portfolio_count=Count("id"))
                .order_by("-portfolio_count")
            )

            model_type_data[period] = [
                {
                    "model_type": portfolio["model_type"],
                    "initial_balance": portfolio["initial_balance"],
                    "portfolio_count": portfolio["portfolio_count"],
                }
                for portfolio in portfolios_per_model_type
            ]

            # Combined statistics
            combined_stats = (
                DemoPortfolio.objects.filter(
                    created__gte=start_time, is_active=True, is_prop=True
                )
                .values("model_type", "initial_balance")
                .annotate(
                    total_count=Count("id"),
                    blown_count=Count("id", filter=Q(blown=True)),
                    passed_count=Count("id", filter=Q(target_met=True)),
                    blown_rate=ExpressionWrapper(
                        F("blown_count") * 100.0 / F("total_count"),
                        output_field=FloatField(),
                    ),
                    pass_rate=ExpressionWrapper(
                        F("passed_count") * 100.0 / F("total_count"),
                        output_field=FloatField(),
                    ),
                    avg_time_to_blown=Avg(
                        F("updated") - F("created"), filter=Q(blown=True)
                    ),
                )
                .order_by("model_type", "initial_balance")
            )

            combined_stats_data[period] = [
                {
                    "model_type": stat["model_type"],
                    "initial_balance": stat["initial_balance"],
                    "total_count": stat["total_count"],
                    "blown_count": stat["blown_count"],
                    "passed_count": stat["passed_count"],
                    "blown_rate": round(stat["blown_rate"] or 0, 2),
                    "pass_rate": round(stat["pass_rate"] or 0, 2),
                    "avg_time_to_blown": (
                        str(stat["avg_time_to_blown"])
                        if stat["avg_time_to_blown"]
                        else None
                    ),
                }
                for stat in combined_stats
            ]

        # Total (all-time) data calculations
        # Similar updates for total calculations...
        total_portfolios_per_broker = (
            DemoPortfolio.objects.filter(is_active=True, is_prop=True)
            .values("broker")
            .annotate(portfolio_count=Count("id"))
            .order_by("-portfolio_count")
        )

        total_portfolios_per_balance = (
            DemoPortfolio.objects.filter(is_active=True, is_prop=True)
            .values("initial_balance", "model_type")
            .annotate(portfolio_count=Count("id"))
            .order_by("-portfolio_count")
        )

        total_portfolios_per_model_type = (
            DemoPortfolio.objects.filter(is_active=True, is_prop=True)
            .values("model_type", "initial_balance")
            .annotate(portfolio_count=Count("id"))
            .order_by("-portfolio_count")
        )

        # Append total data
        broker_data["total"] = [
            {
                "broker": portfolio["broker"],
                "portfolio_count": portfolio["portfolio_count"],
            }
            for portfolio in total_portfolios_per_broker
        ]

        balance_data["total"] = [
            {
                "initial_balance": portfolio["initial_balance"],
                "model_type": portfolio["model_type"],
                "portfolio_count": portfolio["portfolio_count"],
            }
            for portfolio in total_portfolios_per_balance
        ]

        model_type_data["total"] = [
            {
                "model_type": portfolio["model_type"],
                "initial_balance": portfolio["initial_balance"],
                "portfolio_count": portfolio["portfolio_count"],
            }
            for portfolio in total_portfolios_per_model_type
        ]

        # Return all sets of data
        return Response(
            {
                "broker_data": broker_data,
                "balance_data": balance_data,
                "model_type_data": model_type_data,
                "combined_statistics": combined_stats_data,
            }
        )

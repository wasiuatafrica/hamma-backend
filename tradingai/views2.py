# views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from .models import Trial, Subscription

from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from .models import Trial, Subscription


class AIFeatureMixin:
    """
    Mixin to handle AI feature access checking and trial status
    """

    def check_ai_access(self, user):
        """
        Check if user has access to AI features
        Returns (has_access, message, days_remaining)
        days_remaining:
            - positive number for active trial
            - 0 for expired trial/no subscription
            - -1 for active subscription
        """
        # Check active subscription first
        active_subscription = Subscription.objects.filter(
            user=user, status="active", end_date__gt=timezone.now()
        ).exists()

        if active_subscription:
            return True, None, -1  # -1 indicates active subscription

        # Check trial status
        try:
            trial = Trial.objects.get(user=user)
            now = timezone.now()

            if trial.is_active and not trial.has_expired:
                # Active trial
                days_remaining = (trial.end_date - now).days
                if days_remaining < 0:
                    days_remaining = 0

                return True, None, days_remaining

            elif not trial.trial_ended_notification_sent:
                # Trial just expired - send notification
                NotificationService().send_notification(
                    user=user, notification_type="trial_ended"
                )
                trial.trial_ended_notification_sent = True
                trial.save()
                return (
                    False,
                    "Your trial has ended. Subscribe to continue accessing AI features.",
                    0,
                )

            else:
                # Trial expired previously
                return False, "Subscribe to continue accessing AI features.", 0

        except Trial.DoesNotExist:
            # Start new trial
            trial = Trial.objects.create(user=user)
            NotificationService().send_notification(
                user=user, notification_type="trial_welcome"
            )
            return True, None, 14  # New trial starts with 14 days


class TradeRecommendationView(APIView, AIFeatureMixin):
    def get(self, request):
        has_access, message, days_remaining = self.check_ai_access(request.user)

        if not has_access:
            return Response(
                {
                    "error": "Subscription required",
                    "message": message,
                    "days_remaining": days_remaining,
                },
                status=403,
            )

        profile = request.user.trade_profile
        if not profile:
            return Response({"error": "User has no trade profile"}, status=400)

        recommendations = process_recommendation(request.user.trade_profile)
        return Response(
            {
                "recommendations": recommendations,
                "trial_days_remaining": days_remaining if days_remaining >= 0 else None,
            }
        )


class GetSingleStock(APIView, AIFeatureMixin):
    def get(self, request, *args, **kwargs):
        symbol = self.kwargs.get("symbol")
        stock = get_object_or_404(Stock, symbol=symbol)

        # Basic data available to all users
        response_data = {
            "stock_detail": get_details3([stock]),
            "overview": get_symbol_overview(symbol),
            "fundamental": get_symbol_fundamentals(symbol),
            "news": get_stock_news(symbol),
            "calendar": get_calendar(symbol),
        }

        # Check AI feature access for signal
        has_access, message, days_remaining = self.check_ai_access(request.user)

        if has_access:
            response_data["signal"] = get_signal(symbol)
            if days_remaining >= 0:  # Trial period
                response_data["trial_days_remaining"] = days_remaining
        else:
            response_data["signal"] = {
                "error": "Subscription required",
                "message": message,
                "days_remaining": days_remaining,
            }

        return Response(response_data)

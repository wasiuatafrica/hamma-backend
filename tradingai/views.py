from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView, Response

from .models import Subscription, Trial
from .services import NotificationService
from .utils import process_recommendation

# Create your views here.


class TradeRecommendationView(APIView):
    def get(self, request):
        # try:
        #     profile = request.user.trade_profile
        #     if not profile:
        #         return Response({"error": "User has no trade profile"}, status=400)
        #     recommendations = process_recommendation(request.user.trade_profile)
        #     return Response(recommendations)
        # except Exception as e:
        #     return Response({"error": str(e)}, status=500)

        profile = request.user.trade_profile
        if not profile:
            return Response({"error": "User has no trade profile"}, status=400)
        recommendations = process_recommendation(request.user.trade_profile)
        return Response(recommendations)


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
            return True, None, -1, False, True  # -1 indicates active subscription

        # Check trial status
        try:
            trial = Trial.objects.get(user=user)
            now = timezone.now()

            if trial.is_active and not trial.has_expired:
                # Active trial
                days_remaining = (trial.end_date - now).days
                if days_remaining < 0:
                    days_remaining = 0

                return True, None, days_remaining, True, False

            elif not trial.trial_ended_notification_sent:
                # Trial just expired - send notification
                NotificationService().send_trial_ended_notification(user=user)
                trial.trial_ended_notification_sent = True
                trial.save()
                return (
                    False,
                    "Your trial has ended. Subscribe to continue accessing AI features.",
                    0,
                    True,
                    False,
                )

            else:
                # Trial expired previously
                return (
                    False,
                    "Subscribe to continue accessing AI features.",
                    0,
                    True,
                    False,
                )

        except Trial.DoesNotExist:
            # Start new trial
            trial = Trial.objects.create(user=user)
            NotificationService().send_trial_started_notification(user=user)
            return True, None, 14, True, False  # New trial starts with 14 days


class TradeRecommendationViewSub(APIView, AIFeatureMixin):
    def get(self, request):
        has_access, message, days_remaining, is_trial, is_subscribed = (
            self.check_ai_access(request.user)
        )

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
                "is_trial": is_trial,
                "is_subscribed": is_subscribed,
            }
        )

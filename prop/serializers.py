from rest_framework import serializers
from .models import Payout, PropWithdrawalRequest
from execution.models import DemoPortfolio


class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ["id", "portfolio", "amount", "request_date", "status"]
        read_only_fields = ["amount", "status", "request_date"]


class PayoutDetailSerializer(serializers.ModelSerializer):
    portfolio_account_id = serializers.CharField(
        source="portfolio.account_id", read_only=True
    )
    model_type = serializers.CharField(source="portfolio.model_type", read_only=True)
    user_email = serializers.CharField(source="portfolio.user.email", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "portfolio_account_id",
            "user_email",
            "model_type",
            "amount",
            "request_date",
            "process_date",
            "status",
            "profit_percentage",
            "week_number",
            "rejected_reason",
            "admin_notes",
        ]


class AccountlistSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = DemoPortfolio
        # fields = "__all__"
        exclude = ["code"]


# First, let's create a serializer for the withdrawal requests
class PropWithdrawalRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = PropWithdrawalRequest
        fields = [
            "id",
            "user",
            "user_email",
            "amount",
            "status",
            "created_at",
            "bank_details",
            "admin_comment",
        ]
        read_only_fields = ["id", "user_email", "user", "amount", "created_at"]

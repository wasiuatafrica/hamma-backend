from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from django.db.models import Count, Q
from stocknews.models import StockNews

UserModel = get_user_model()

from rest_framework import serializers
from .models import (
    DashboardFeed,
    FeedsCategory,
    Wallet,
    Stock,
    Receipts,
    PayStackReceipts,
    Transaction,
    Alert,
    Conversation,
    ButtonClick,
    DashboardFeed,
    FeedReaction,
)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("balance",)


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = (
            "company",
            "symbol",
            "sector",
            "current_price",
            "change",
            "percent_change",
        )


class StockNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockNews
        fields = "__all__"


class ReceiptsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipts
        fields = ["image"]


class PayStackReceiptsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayStackReceipts
        fields = "__all__"


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = fields = [
            "id",
            "stock",
            "alert_name",
            "description",
            "alert_type",
            "action",
            "to_price",
            "to_volume",
            "frequency",
            "expire",
            "trigerred",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = "__all__"


class ButtonClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = ButtonClick
        fields = ["button_name", "page"]


class DashboardFeedSerializer(serializers.ModelSerializer):
    stock_symbol = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = DashboardFeed
        fields = "__all__"

    def get_stock_symbol(self, instance):
        return instance.stock.symbol if instance.stock else None

    def get_category_name(self, instance):
        return instance.category.name if instance.category else None

    def get_logo_url(self, instance):
        return instance.stock.logo_url if instance.stock else None

    def to_representation(self, instance):
        # Get aggregated counts for each reaction type
        reaction_counts = instance.reactions.aggregate(
            num_agree=Count("id", filter=Q(agree=True)),
            num_disagree=Count("id", filter=Q(disagree=True)),
            num_like=Count("id", filter=Q(like=True)),
            num_trading=Count("id", filter=Q(trading=True)),
            num_monitoring=Count("id", filter=Q(monitoring=True)),
        )
        # Update serializer data with aggregated counts
        ret = super().to_representation(instance)
        ret.update(reaction_counts)

        # Add the stock symbol to the representation
        ret["stock_symbol"] = self.get_stock_symbol(instance)
        ret["category_name"] = self.get_category_name(instance)
        ret["logo_url"] = self.get_logo_url(instance)

        return ret


class FeedsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedsCategory
        fields = "__all__"


class FeedReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedReaction
        fields = ["like", "agree", "disagree", "trading", "monitoring"]

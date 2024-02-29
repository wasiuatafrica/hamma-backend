
from .models import DemoPosition, DemoPortfolio
from rest_framework import serializers

class DemoPositionSerializer(serializers.ModelSerializer):
    symbol = serializers.SerializerMethodField()
    class Meta:
        model = DemoPosition
        fields = [
            "id",
            "quantity",
            "open_price",
            "close_price",
            "limit_price",
            "status",
            "created",
            "updated",
            "amount_invested",
            "action",
            "time_in_force",
            "order_type",
            "profit_loss",
            "symbol"
        ]

    def get_symbol(self, obj):
        return obj.stock.symbol
    
def get_positions(user,status=None):
    portfolio = DemoPortfolio.objects.get(user=user)
    if status == 'all' or status == None:
        positions = DemoPosition.objects.filter(portfolio=portfolio)
    else:
        positions = DemoPosition.objects.filter(portfolio=portfolio, status=status)
    
    serializer = DemoPositionSerializer(positions, many=True)
    return serializer.data
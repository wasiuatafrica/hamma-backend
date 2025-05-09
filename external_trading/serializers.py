# external_trading/serializers.py
from rest_framework import serializers
from .models import ExternalConnection, ApiKey, ExternalPlatformPermission


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = [
            "key_id",
            "api_key",
            "created_at",
            "expires_at",
            "last_used",
            "is_active",
        ]
        read_only_fields = ["key_id", "api_key", "created_at", "last_used"]

    def to_representation(self, instance):
        """Only show the full API key once after creation"""
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.method != "POST":
            data["api_key"] = f"{data['api_key'][:8]}..."
        if self.context.get("show_secret"):
            data["secret_key"] = instance.secret_key
        return data


class ExternalPlatformPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalPlatformPermission
        fields = [
            "can_view_positions",
            "can_open_trades",
            "can_close_trades",
            "max_trade_size",
            "max_daily_trades",
            "allowed_symbols",
        ]


class ExternalConnectionSerializer(serializers.ModelSerializer):
    permissions = ExternalPlatformPermissionSerializer(required=False)
    api_keys = serializers.SerializerMethodField()

    class Meta:
        model = ExternalConnection
        fields = [
            "id",
            "platform_type",
            "name",
            "is_active",
            "created_at",
            "updated_at",
            "permissions",
            "api_keys",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_api_keys(self, obj):
        active_keys = obj.api_keys.filter(is_active=True)
        return ApiKeySerializer(active_keys, many=True).data

    def create(self, validated_data):
        permissions_data = validated_data.pop("permissions", {})
        connection = ExternalConnection.objects.create(**validated_data)

        # Create default permissions
        ExternalPlatformPermission.objects.create(
            connection=connection, **permissions_data
        )

        # Create default API key
        ApiKey.objects.create(connection=connection)

        return connection

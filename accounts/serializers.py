from rest_framework import serializers
from . import models
from django.contrib.auth.password_validation import validate_password


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        max_length=128, min_length=8, write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = models.CustomUser
        fields = [
            "id",
            "email",
            "firstname",
            "lastname",
            "password",
            "has_2fa",
            "twofa_type",
            "is_active",
            # "signup_type",
            "totp_url",
            "date_joined",
            "last_login",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": True},
            "has_2fa": {"read_only": True},
            "twofa_type": {"read_only": True},
            "totp_url": {"read_only": True},
            # 'signup_type': {'read_only': True},
        }

    def validate_password(self, value):
        # Validate the password against Django's password validation rules
        validate_password(value)
        return value


class UpdateCustomUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.CustomUser
        fields = [
            "firstname",
            "lastname",
        ]


class TokenSerializer(serializers.Serializer):
    user_email = serializers.EmailField()
    token = serializers.CharField(max_length=10)


class SignInWithGoogleSerilaizer(serializers.Serializer):
    email = serializers.EmailField()
    firstname = serializers.CharField(max_length=200)
    lastname = serializers.CharField(max_length=200)


class ProfileSerializer(serializers.ModelSerializer):
    # user = CustomUserSerializer()

    class Meta:
        model = models.Profile
        fields = (
            "user",
            "country",
            "address",
            "referral_code",
            "profile_img",
            "phone",
            "proof_of_id",
            "proof_of_address",
            "bank_name",
            "account_number",
            "paypal_address",
        )
        extra_kwargs = {
            "referral_code": {"read_only": True},
            "user": {"read_only": True},
        }


class Turn2FAOnOrOff(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=(
            ("email", "email"),
            ("sms", "sms"),
            ("authapps", "authapps"),
            ("none", "none"),
        )
    )


class LoginWithEmailSeriailizer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=200)
    ip_address = serializers.IPAddressField()
    location = serializers.CharField(max_length=100, allow_blank=True)
    device = serializers.CharField(max_length=1000)


class LoginTokenSeriailizer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(max_length=8)
    ip_address = serializers.IPAddressField()
    location = serializers.CharField(max_length=100, allow_blank=True)
    device = serializers.CharField(max_length=1000)


class DashBoardChangePassword(serializers.Serializer):
    current_password = serializers.CharField(max_length=200)
    new_password1 = serializers.CharField(max_length=200, required=False)
    new_password2 = serializers.CharField(max_length=200, required=False)


class ResetForgottenPassword(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(max_length=200)
    new_password1 = serializers.CharField(max_length=200, required=False)
    new_password2 = serializers.CharField(max_length=200, required=False)


class TokenEmailSeriailizer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(max_length=200)


class TokenSeriailizer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class UserActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserActivityLog
        fields = [
            "id",
            "user",
            "action_type",
            "timestamp",
            "description",
            "userfullname",
            "device_type",
        ]


class AdminUserActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AdminUserActivityLog
        fields = [
            "id",
            "admin",
            "user",
            "action_type",
            "timestamp",
            "description",
            "adminfullname",
            "userfullname",
        ]


class AdminCustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomUser
        fields = [
            "id",
            "email",
            "firstname",
            "lastname",
            "has_2fa",
            "twofa_type",
            "is_active",
            # "signup_type",
            "totp_url",
            "date_joined",
            "last_login",
            "no_of_referred_users",
            "profile_image",
            "profile_phone",
            "fullname",
            "bank_name",
            "account_number",
            "proof_of_id",
            "proof_of_address",
        ]
        extra_kwargs = {
            "has_2fa": {"read_only": True},
            "twofa_type": {"read_only": True},
            "totp_url": {"read_only": True},
            # 'signup_type': {'read_only': True},
        }


class TradingProfileSerializer(serializers.ModelSerializer):
    market_sentiment1 = serializers.CharField(required=False)
    market_sentiment2 = serializers.CharField(required=False)
    preferred_stocks = serializers.JSONField(required=False)
    preferred_asset_type = serializers.CharField(required=False)

    class Meta:
        model = models.TradingProfile
        fields = [
            "id",
            "trader",
            "trading_frequency",
            "trading_style",
            "avg_time_on_trade",
            "risk_tolerance",
            "market_sentiment1",
            "market_sentiment2",
            "preferred_stocks",
            "preferred_asset_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

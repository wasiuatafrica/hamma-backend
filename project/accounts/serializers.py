from rest_framework import serializers
from .import models

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        max_length=128,
        min_length=8,
        write_only=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model=models.CustomUser
        fields=[
            "id",
            "email",
            "firstname",
            "lastname",
            "password",
            "has_2fa",
            "twofa_type",
            # "signup_type",
            "totp_url",
            "date_joined",
            "last_login",
        ]
        extra_kwargs={
            'password': {'write_only': True, "required":True},
            'has_2fa': {'read_only': True},
            'twofa_type': {'read_only': True},
            'totp_url': {'read_only': True},
            # 'signup_type': {'read_only': True},
        }
class TokenSerializer(serializers.Serializer):
    user_email=serializers.EmailField()
    token=serializers.CharField(max_length=10)


class SignInWithGoogleSerilaizer(serializers.Serializer):
    email=serializers.EmailField()
    firstname=serializers.CharField(max_length=200)
    lastname=serializers.CharField(max_length=200)





class ProfileSerializer(serializers.ModelSerializer):
    # user = CustomUserSerializer()

    class Meta:
        model = models.Profile
        fields = (
            "user",
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
        extra_kwargs={
            'referral_code': {'read_only': True},
            'user': {'read_only': True},
        }

class Turn2FAOnOrOff(serializers.Serializer):
    action=serializers.ChoiceField(choices=(("email","email"), ("sms","sms"),("authapps","authapps"),("none","none")))

class LoginWithEmailSeriailizer(serializers.Serializer):
    email=serializers.EmailField()
    password=serializers.CharField(max_length=200)

class DashBoardChangePassword(serializers.Serializer):
    current_password=serializers.CharField(max_length=200)
    new_password1=serializers.CharField(max_length=200,required=False)
    new_password2=serializers.CharField(max_length=200,required=False)

class ResetForgottenPassword(serializers.Serializer):
    email=serializers.EmailField()
    token=serializers.CharField(max_length=200)
    new_password1=serializers.CharField(max_length=200,required=False)
    new_password2=serializers.CharField(max_length=200,required=False)

class TokenEmailSeriailizer(serializers.Serializer):
    email=serializers.EmailField()
    token=serializers.CharField(max_length=200)
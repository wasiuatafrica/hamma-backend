import uuid
from django.core.mail import send_mail
from . import models
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
import random
import string

from .models import Referral
# Authenticator functions
from django_otp import devices_for_user
from django_otp.plugins.otp_totp.models import TOTPDevice
import qrcode

User=get_user_model()

def get_ref_code():
    code = str(uuid.uuid4())[:7].replace("-", "").lower()
    return f"AYN{code}"


# Create your tests here.
def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def  verify_token(user_email,token, _type=""):
    user_=User.objects.filter(email=user_email).first()
    token=models.TwoFactorToken.objects.filter(user__email=user_email, token=token).first()
    current_time = timezone.now()
    if token and token.expiration >= current_time:
        user=user_
        user.is_active = True
        user.save()
        if not _type =="validate":
            # Delete the token
            token.delete()
        return True
    return False

def send_welcome_email(user):
    # Send token to users email
    context={
        "firstname":user.firstname.title()
    }
    html_message = render_to_string('accounts/welcome_email.html', context)
    plain_message = strip_tags(html_message)
    subject = 'Welcome to Gohamma'
    from_email = "teamgohamma@gmail.com"
    recipient_list = [user.email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)


def resendToken(instance, _type):

    token=models.TwoFactorToken.objects.filter(user=instance)
    if token:
        token.delete()
    if _type =="signup":
        token=models.TwoFactorToken.objects.create(user=instance,expiration=timezone.now() + timezone.timedelta(hours=1))
    elif _type =="password":
        token=models.TwoFactorToken.objects.create(user=instance,expiration=timezone.now() + timezone.timedelta(minutes=10))
    elif _type =="login":
        token=models.TwoFactorToken.objects.create(user=instance,expiration=timezone.now() + timezone.timedelta(minutes=10))

    elif _type =="sms":
        token=models.TwoFactorToken.objects.create(user=instance,expiration=timezone.now() + timezone.timedelta(minutes=60))
        return token.token
    # Send token to users email
    
    context={
        "token":token.token,
        "firstname":instance.firstname
    }
    if _type =="password":
        html_message = render_to_string('accounts/reset_password.html', context)
    else:
        html_message = render_to_string('accounts/token.html', context)
    plain_message = strip_tags(html_message)
    subject = 'Token'
    from_email = "teamgohamma@gmail.com"
    recipient_list = [instance.email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

def get_user_totp_device(user, confirmed=None):
    devices = devices_for_user(user, confirmed=confirmed)
    for device in devices:
        if isinstance(device, TOTPDevice):
            return device
        
import os
from django.conf import settings
def SetTOTP(user):
    device = get_user_totp_device(user)
    if not device:
        device = user.totpdevice_set.create(confirmed=False)

    url = device.config_url
    
    return url

# Use this to verify/enable a TOTP device
def verifyTOTP(user,token):
    device = get_user_totp_device(user)
    if not device == None and device.verify_token(token):
        if not device.confirmed:
            device.confirmed = True
            device.save()
        # Here 
        user.twofa_type = "email"
        user.save()
        return True
    return False


import requests

def sms_2FA(phone, token):
    print(phone)
    resp = requests.post('https://textbelt.com/text', {
    'phone': phone,
    'message': f'Hello, here is your 2fa token {token}',
    'key': 'textbelt',
    })
    print(resp.json())
    return resp.json()

def get_referrer(user):
    referrer = Referral.objects.filter(person_referred=user).first()
    return referrer.user if referrer else None

def get_referees(user):
    referees = Referral.objects.filter(user=user)
    return referees if referees else None
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from . import models
from . import utils
from .tasks import daily_returns_setup

User=get_user_model()

@receiver(user_logged_in)
def set_first_login_datetime(sender, request, user, **kwargs):
    first_login, created = models.FirstLogin.objects.get_or_create (user=user)
    if created:
        first_login.save()

@receiver(post_save, sender=User)
def create_wallet_and_send_email(sender, instance, created, **kwargs):
    if created:
        models.Profile.objects.create(user=instance,referral_code=utils.get_ref_code())
        token=models.TwoFactorToken.objects.create(user=instance, expiration=timezone.now() + timezone.timedelta(hours=1))

        # Send token to users email
        context={
            "token":token.token,
            "firstname":instance.firstname.title()
        }
        html_message = render_to_string('accounts/registration_token.html', context)
        plain_message = ""
        subject = 'Email Confirmation'
        from_email = "teamgohamma@gmail.com"
        
        recipient_list = [instance.email]
        send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

@receiver(post_save, sender=User)
def daily_returns(sender, instance, created, **kwargs):
    if created:
        daily_returns_setup.delay(instance.id)
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from Accounts.managers import CustomUserManager
import auto_prefetch
import random
import string


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email address"), unique=True)
    firstname = models.CharField(max_length=255, default="", blank=True, null=True)
    lastname = models.CharField(max_length=255, default="", blank=True, null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_ft9ja_staff=models.BooleanField(default=False, null=True, blank=True)
    is_ft9ja_staff_payouts=models.BooleanField(default=False, null=True, blank=True)
    is_ft9ja_staff_receipts=models.BooleanField(default=False, null=True, blank=True)
    signup_type=models.CharField(max_length=50, null=True, blank=True, default="none", choices=(("email","email"), ("google","google")))
    date_joined = models.DateTimeField(default=timezone.now)
    has_second_email= models.TextField(max_length=255, blank=True, null=True)
    has_2fa=models.BooleanField(default=True, null=True, blank=True)
    totp_url=models.ImageField(upload_to="qr_img", null=True, blank=True)
    twofa_type =models.CharField(max_length=50, null=True, blank=True, default="email", choices=(("email","email"), ("sms","sms"),("authapps","authapps"),("none","none")))
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["firstname", "lastname"]

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    @property
    def clan_id(self):
        clan = self.clan_set.first()  # Check if the user is a clan member
        if clan:
            return clan.id

        clan_admin = self.clan_admin.first()  # Check if the user is a clan admin
        if clan_admin:
            return clan_admin.id
        
        return None 
        
    @property
    def fullname(self):
        return f"{self.firstname} {self.lastname}"    

class Profile(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(CustomUser, on_delete=models.CASCADE,related_name='profile', null=True, blank=True)
    dob = models.DateField(
        blank=True,
        default="2001-02-25",
    )
    gender = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, default="", blank=True)
    city = models.CharField(max_length=255, default="", blank=True)
    address = models.CharField(max_length=255, default="", blank=True)
    referral_code = models.CharField(max_length=255, default="", blank=True)
    proof_of_id=models.FileField(upload_to="proof_of_id", null=True, blank=True)
    proof_of_address=models.FileField(upload_to="proof_of_id", null=True, blank=True)
    profile_img=models.FileField(upload_to="proof_of_address", null=True, blank=True)
    has_profile_img=models.BooleanField(default=False,null=True, blank=True)
    bank_name=models.CharField(max_length=255, blank=True, null=True)
    account_number=models.CharField(max_length=255, blank=True, null=True)
    paypal_address=models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user} Profile"

    @property
    def referrer(self):
        referral=Referral.objects.get(person_referred=self.user)
        return referral.user
    
class TwoFactorToken(models.Model):
    user=models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    token=models.CharField(max_length=20, null=True, blank=True)
    expiration=models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.token

    def save(self, *args, **kwargs):
        if not self.token:
            self.token=self.generate_random_token()
        super(TwoFactorToken, self).save(*args, **kwargs)

    @staticmethod
    def generate_random_token():
        token = ''.join([str(random.randint(0, 9)) for _ in range(8)])
        return token
    
class Referral(auto_prefetch.Model):
    choices = (("pending", "Pending"), ("paid", "Paid"), ("declined", "Declined"))
    user = auto_prefetch.ForeignKey(CustomUser, on_delete=models.CASCADE)
    person_referred = auto_prefetch.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="referred_by"
    )
    stage = models.CharField(max_length=255, default="", blank=True)
    typeofaccount = models.CharField(max_length=21, default="",blank=True)
    accsize = models.CharField(max_length=255, default="", blank=True)
    status = models.CharField(max_length=255, default="Pending")
    accprofit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    converted = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user} Referral"
    
    
    def save(self, *args, **kwargs):
        if not self.accprofit:
            accprofit_dict = {
                "3000": 3000,
                "5000": 4500,
                '10000':4900,
                "25000": 18000,
            }

            if self.accsize:
                accsize_key = str(self.accsize).strip()
                if accsize_key in accprofit_dict:
                    self.accprofit = int(accprofit_dict[accsize_key])

        super().save(*args, **kwargs)

    



        
class FirstLogin(auto_prefetch.Model):
    user=models.OneToOneField(CustomUser, related_name='first_login', on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time}"
    
class ReferralPayment(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(CustomUser,on_delete=models.CASCADE)
    amount = models.IntegerField()
    status = models.CharField(max_length=20, default='Unpaid')
    comment = models.TextField(blank=True, null=True)
    created=models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"{self.user}| {self.amount} | {self.status}"
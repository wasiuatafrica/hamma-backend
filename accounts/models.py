
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from accounts.managers import CustomUserManager
import auto_prefetch
import random

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email address"), unique=True)
    firstname = models.CharField(max_length=255, default="", blank=True, null=True)
    lastname = models.CharField(max_length=255, default="", blank=True, null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    has_2fa=models.BooleanField(default=True, null=True, blank=True)
    totp_url=models.ImageField(upload_to="qr_img", null=True, blank=True)
    twofa_type =models.CharField(max_length=50, null=True, blank=True, default="email", choices=(("email","email"), ("sms","sms"),("authapps","authapps"),("none","none")))
    last_ip = models.GenericIPAddressField(blank=True, null=True)
    last_location = models.CharField(max_length=100, blank=True, null=True)
    last_device = models.TextField( blank=True, null=True)
    
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["firstname", "lastname"]

    objects = CustomUserManager()

    def __str__(self):
        return self.email
    
    @property
    def clans(self):
        clan = self.clan.all()
        # print(clan)
        if clan:
            return clan[0].clan_name
        else:
            clan = self.clan_admin.all()
            if clan:
                return clan[0].clan_name
            else:
                return None
    
    @property
    def profile_phone(self):
        profile=Profile.objects.get(user__email=self.email)
        # print(profile, "jbabah")
        return profile.phone
        
    @property
    def fullname(self):
        return f"{self.firstname} {self.lastname}"    

    @property
    def no_of_referred_users(self):
        referral=Referral.objects.filter(user__id=self.id).count()
        return referral
    @property
    def profile_image(self):
        profile=Profile.objects.get(user__email=self.email)
        if not profile.profile_img:
            return ""

        return str(profile.profile_img.url)
    
    @property
    def bank_name(self):
        profile=Profile.objects.get(user__email=self.email)
        # print(profile, "jbabah")
        return profile.bank_name

    @property
    def account_number(self):
        profile=Profile.objects.get(user__email=self.email)
        # print(profile, "jbabah")
        return profile.account_number
    
    @property
    def proof_of_id(self):
        profile=Profile.objects.get(user__email=self.email)
        # print(profile, "jbabah")
        return str(profile.proof_of_id)
    @property
    def proof_of_address(self):
        profile=Profile.objects.get(user__email=self.email)
        # print(profile, "jbabah")
        return str(profile.proof_of_address)
    
    


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
    profile_img=models.ImageField(upload_to="proof_of_address", null=True, blank=True)
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
        token = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        return token
    
class Referral(auto_prefetch.Model):
    choices = (("pending", "Pending"), ("paid", "Paid"), ("declined", "Declined"))
    user = auto_prefetch.ForeignKey(CustomUser, on_delete=models.CASCADE)
    person_referred = auto_prefetch.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="referred_by"
    )
    converted = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user} Referral"
    
    @property
    def stage(self):
        return 'Converted' if self.converted else 'Registered'
    
    @property
    def amount_deposit(self):
        transactions = self.person_referred.transactions.filter(transaction_type='deposit')
        if transactions:
            amount= transactions.aggregate(total_commission=models.Sum('amount'))['total_commission']
        else:
            amount = 0
            
        return amount
    
    @property
    def commission(self):
        return '5000' if self.converted else '0'
    
    @property
    def brokage_commission(self):
        commissions = self.person_referred.brokage_commsissions.all()
        if commissions:
            amount= commissions.aggregate(total_commission=models.Sum('commission'))['total_commission']
        else:
            amount= 0
        return amount
        
    @property
    def status(self):
        return 'Paid' if self.paid else 'Unpaid'
    
    @property
    def profile_image(self):
        profile=Profile.objects.get(user__email=self.person_referred.email)
        if not profile.profile_img:
            return ""

        return str(profile.profile_img.url)
    
        
class FirstLogin(auto_prefetch.Model):
    user=models.OneToOneField(CustomUser, related_name='first_login', on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time}"
    
class UserActivityLog(models.Model):
    user=models.ForeignKey(CustomUser, related_name='user_activity', on_delete=models.CASCADE)
    action_type=models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    description=models.CharField(max_length=100)

    def __str__(self) -> str:
        return f"{self.user} - {self.action_type}"


class AdminUserActivityLog(models.Model):
    admin=models.ForeignKey(CustomUser, related_name='admin_activity', on_delete=models.CASCADE)
    user=models.ForeignKey(CustomUser, related_name='user_subject', on_delete=models.CASCADE,null=True, blank=True)
    action_type=models.CharField(max_length=40)
    timestamp = models.DateTimeField(auto_now_add=True)
    description=models.CharField(max_length=100)


    @property
    def adminfullname(self):
        return f"{self.admin.firstname} {self.admin.lastname}"   
    
    @property
    def userfullname(self):
        return f"{self.user.firstname} {self.user.lastname}" 

    def __str__(self) -> str:
        return self.action_type
    

class Unsubscribe(models.Model):
    email = models.EmailField(_("email address"), unique=True)
    created = models.DateTimeField(auto_now_add=True)
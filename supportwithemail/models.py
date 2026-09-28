import auto_prefetch
from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import CustomUser, Profile
from portfolio.s3_utils import presign_s3_url

AWS_REGION = settings.AWS_S3_REGION_NAME
AWS_BUCKET = settings.AWS_STORAGE_BUCKET_NAME


class SupportThread(auto_prefetch.Model):
    user = models.ForeignKey(
        CustomUser,
        related_name="thread_owner",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    email = models.EmailField(null=True, blank=True)
    thread_id = models.CharField(max_length=300, default="")
    switched_to_admin_support = models.BooleanField(default=False)
    is_prop = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)


class SupportAdminProfile(auto_prefetch.Model):
    name = models.CharField(max_length=300, default="")
    profile_url = models.FileField(
        upload_to="support_profile_images", null=True, blank=True
    )
    gender = models.CharField(max_length=300, default="")
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)


class SupportMessage(auto_prefetch.Model):
    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=300, default="")
    sender = models.CharField(
        max_length=100, choices=(("user", "user"), ("assistant", "assistant"))
    )
    content = models.TextField()
    thread = models.ForeignKey(
        "SupportThread", on_delete=models.CASCADE, null=True, blank=True
    )
    is_first_admin_request_message = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    # admin_profile_url = models.FileField(upload_to="support_profile_images", null=True, blank=True)
    admin_profile = models.ForeignKey(
        "SupportAdminProfile", on_delete=models.CASCADE, null=True, blank=True
    )

    @property
    def admin_profile_url(self):
        return (
            self.get_aws_img_url(self.admin_profile.profile_url)
            if self.admin_profile
            else ""
        )

    @property
    def user_id(self):
        return self.thread.user.id if self.thread else ""

    @property
    def chat_switched_to_admin(self):
        return self.thread.switched_to_admin_support if self.thread else ""

    @property
    def thread_value(self):
        return self.thread.thread_id if self.thread else ""

    @property
    def user_name(self):
        if self.thread.user:
            return (
                self.thread.user.firstname
                if self.sender == "user" or self.sender == "admin"
                else ""
            )
        return ""

    @property
    def user_pics(self):
        if self.thread.user:
            return (
                self.get_aws_img_url(self.thread.user.profile_image)
                if self.sender == "user" or self.sender == "admin"
                else ""
            )
        return ""

    def get_aws_img_url(self, key):
        if not key:
            return ""
        name = getattr(key, "name", None)
        if name:
            return key.url
        url = str(key)
        if url.startswith("http://") or url.startswith("https://"):
            return presign_s3_url(url) or ""
        return (
            presign_s3_url(
                f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/media/{url.lstrip('/')}"
            )
            or ""
        )

    def save(self, *args, **kwargs):
        if self.sender == "assistant":
            if self.thread.is_prop:
                self.name = "Mansa Musa (Hamma Prop AI Chatbot)"
            else:
                self.name = "Hamilton (Hamma Chatbot)"
        super(SupportMessage, self).save(*args, **kwargs)


class SupportMessageDisclaimer(auto_prefetch.Model):
    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=300, default="")
    vote = models.CharField(
        max_length=10, choices=(("upvote", "upvote"), ("downvote", "downvote"))
    )
    feedback = models.CharField(max_length=500, default="")
    message = models.ForeignKey(
        "SupportMessage", on_delete=models.CASCADE, null=True, blank=True
    )
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)


class ContactMessage(models.Model):
    full_name = models.CharField(max_length=150, verbose_name="Full Name")
    email = models.EmailField(verbose_name="Email Address")
    subject = models.CharField(max_length=255, verbose_name="Subject")
    message = models.TextField(verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    responded = models.BooleanField(
        default=False, verbose_name="Responded?"
    )  # Optional: Track if someone replied

    class Meta:
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"
        ordering = ["-created_at"]  # Show newest messages first by default

    def __str__(self):
        return f"Message from {self.full_name} - Subject: {self.subject}"

from django.contrib import admin
from .models import SupportMessage, SupportThread, SupportAdminProfile

# Register your models here.

admin.site.register(SupportMessage)
admin.site.register(SupportThread)
admin.site.register(SupportAdminProfile)

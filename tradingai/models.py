from django.db import models
import auto_prefetch
from portfolio.models import Stock
from django.contrib.auth import get_user_model


User = get_user_model()

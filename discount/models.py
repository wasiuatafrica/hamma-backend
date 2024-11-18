from django.db import models
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from decimal import Decimal
import auto_prefetch
from django.utils import timezone
from execution.models import DemoPortfolio

User = get_user_model()

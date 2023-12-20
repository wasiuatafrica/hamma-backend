from celery import shared_task
from celery.utils.log import get_task_logger
from .models import SavingsLock
from datetime import date
from portfolio.models import Wallet, Transaction
from decimal import Decimal
from notifications.utils import save_and_send_notification


from django.core.management import call_command

logger = get_task_logger(__name__)

@shared_task
def update_wallet(lock_id):
    lock = SavingsLock.objects.get(pk=lock_id)

    if lock.status == 'ongoing':
        # Calculate interest
        interest = lock.potential_interest
        amount_due = Decimal(lock.amount + interest)
        
        main_wallet = Wallet.objects.get(user=lock.user)
        main_wallet.balance += amount_due
        main_wallet.save()

        save_and_send_notification(lock.user.id, f"{amount_due} has been deposited into your main wallet from lock savings")
        Transaction.objects.create(user=lock.user, transaction_type='Payment from mature Savings Lock', amount=amount_due)
        
        lock.status = 'completed'
        lock.save()

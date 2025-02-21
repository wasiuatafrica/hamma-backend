# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from execution.models import DemoPosition
# from django.utils import timezone
# from .tasks import analyze_portfolio_after_close_task


# @receiver(post_save, sender=DemoPosition)
# def schedule_alert(sender, created, instance, **kwargs):
#     today = timezone.now().date()
#     if not created:
#         if (
#             instance.status == "close"
#             and instance.portfolio.is_prop
#             and instance.closed_at.date() == today
#         ):
#             analyze_portfolio_after_close_task.delay(instance.portfolio.account_id)

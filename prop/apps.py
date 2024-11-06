from django.apps import AppConfig


class PropfolioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prop"

    # def ready (self):
    #     import portfolio.signals

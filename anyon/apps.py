from django.apps import AppConfig


class AnyonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'anyon'

    def ready (self):
        import anyon.signals
from django.apps import AppConfig


class LockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lock'

    def ready(self):
        import lock.signals 
from django.apps import AppConfig


class ExecutionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'competition'

    def ready (self):
        # Import the signals module
        import competition.signals
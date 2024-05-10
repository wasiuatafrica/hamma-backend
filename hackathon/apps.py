from django.apps import AppConfig


class HackathonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hackathon'

    def ready (self):
        # Import the signals module
        import hackathon.signals

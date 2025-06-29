from django.apps import AppConfig


class ObspConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'OBSP'

    def ready(self):
        import OBSP.signals  # Import signals to connect them

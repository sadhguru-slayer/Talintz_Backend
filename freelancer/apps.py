from django.apps import AppConfig


class FreelancerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'freelancer'

    def ready(self):
        import freelancer.signals  # Import signals when app is ready

from django.apps import AppConfig

class FinanceappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'financeapp'  # Update this line
    verbose_name = 'Finance App Management'
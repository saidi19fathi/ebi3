# carriers/apps.py
from django.apps import AppConfig

class CarriersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "carriers"
    verbose_name = "Transporteurs"

    def ready(self):
        import carriers.signals  # Ajoutez cette ligne
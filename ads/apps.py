# ~/ebi3/ads/apps.py
from django.apps import AppConfig

class AdsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ads'
    verbose_name = "Annonces"

    def ready(self):
        import ads.signals  # Import des signaux
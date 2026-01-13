# ~/ebi3/carriers/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CarriersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'carriers'
    verbose_name = _("Transporteurs")

    def ready(self):
        """Importer les signaux quand l'application est prête"""
        # Ne pas importer directement les signaux ici
        # Laissez Django les découvrir automatiquement
        pass
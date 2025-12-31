# ~/ebi3/colis/apps.py
from django.apps import AppConfig

class ColisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'colis'
    verbose_name = "Colis"

    def ready(self):
        """Connecte les signaux lors du chargement de l'application"""
        # TODO: Décommenter lorsque les signaux seront implémentés
        # import colis.signals
        # colis.signals.connect_signals()

        # Import des tâches Celery (si utilisé)
        try:
            import colis.tasks  # noqa
        except ImportError:
            pass
# ~/ebi3/logistics/apps.py

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LogisticsConfig(AppConfig):
    name = 'logistics'
    verbose_name = _('Logistique')

    def ready(self):
        """
        Méthode appelée quand l'app est prête
        """
        # Import et connexion des signaux
        try:
            import logistics.signals  # noqa: F401
        except ImportError:
            pass

        # Configuration des tâches périodiques
        self.setup_periodic_tasks()

    def setup_periodic_tasks(self):
        """
        Configurer les tâches périodiques (si vous utilisez Celery)
        """
        try:
            # Vérifier si Celery est installé
            from celery import Celery

            # Tâches pour gérer les expirations
            from .tasks import (
                expire_old_reservations,
                expire_old_proposals,
                update_route_statuses,
                send_delivery_reminders
            )

            # Ces tâches seraient configurées dans celery.py
            pass
        except ImportError:
            # Celery n'est pas installé, utiliser les signaux
            pass
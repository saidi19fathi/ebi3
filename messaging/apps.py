# ~/ebi3/messaging/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class MessagingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'messaging'
    verbose_name = _("Messagerie")

    def ready(self):
        import messaging.signals  # Import des signaux
# ~/ebi3/audit/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = _("Audit & Sécurité")

    # def ready(self):
        # Import des signaux
      #  import audit.signals
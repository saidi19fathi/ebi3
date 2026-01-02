from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TranslationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'translations'
    verbose_name = _('Système de Traduction')

    def ready(self):
        """
        Initialisation de l'application.
        """
        try:
            # Import des signaux
            import translations.signals  # noqa
        except ImportError as e:
            print(f"Erreur lors de l'import des signaux translations: {e}")
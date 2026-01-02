"""
Middleware pour la détection automatique de la langue utilisateur
et la gestion des préférences de traduction.
"""
import logging
from django.utils import translation
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from .models import TranslationSettings

logger = logging.getLogger(__name__)


class LanguageDetectionMiddleware(MiddlewareMixin):
    """
    Middleware pour détecter et définir la langue préférée de l'utilisateur.
    Priorité:
    1. Langue explicite dans l'URL
    2. Session utilisateur
    3. Préférences utilisateur en base
    4. Header Accept-Language du navigateur
    5. Langue par défaut du site
    """

    def process_request(self, request):
        # Langue depuis l'URL (si applicable)
        lang_from_url = self._get_language_from_url(request)
        if lang_from_url:
            request.user_language = lang_from_url
            translation.activate(lang_from_url)
            return

        # Langue depuis la session
        if hasattr(request, 'session'):
            lang_from_session = request.session.get('user_language')
            if lang_from_session and lang_from_session in self._get_supported_languages():
                request.user_language = lang_from_session
                translation.activate(lang_from_session)
                return

        # Langue depuis les préférences utilisateur
        if request.user.is_authenticated:
            try:
                user_settings = TranslationSettings.objects.filter(user=request.user).first()
                if user_settings and user_settings.preferred_languages:
                    user_lang = user_settings.preferred_languages[0]
                    if user_lang in self._get_supported_languages():
                        request.user_language = user_lang
                        translation.activate(user_lang)
                        return
            except Exception as e:
                logger.error(f"Erreur récupération préférences utilisateur: {e}")

        # Langue depuis le navigateur
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if accept_language:
            browser_lang = self._parse_accept_language(accept_language)
            if browser_lang:
                request.user_language = browser_lang
                translation.activate(browser_lang)
                return

        # Langue par défaut
        request.user_language = settings.LANGUAGE_CODE
        translation.activate(settings.LANGUAGE_CODE)

    def process_response(self, request, response):
        # Sauvegarde la langue dans la session si différente
        if hasattr(request, 'session') and hasattr(request, 'user_language'):
            current_lang = request.session.get('user_language')
            if current_lang != request.user_language:
                request.session['user_language'] = request.user_language

        # Ajoute l'en-tête Content-Language
        if hasattr(request, 'user_language'):
            response['Content-Language'] = request.user_language

        return response

    def _get_language_from_url(self, request):
        """
        Extrait la langue depuis l'URL (support pour /fr/, /en/, etc.).
        """
        path = request.path_info
        if path.startswith('/'):
            path = path[1:]

        # Vérifie les préfixes de langue
        for lang_code in self._get_supported_languages():
            if path.startswith(f'{lang_code}/') or path == lang_code:
                return lang_code

        return None

    def _parse_accept_language(self, accept_language):
        """
        Parse le header Accept-Language pour trouver la meilleure langue.
        """
        languages = accept_language.split(',')
        supported = self._get_supported_languages()

        for lang in languages:
            try:
                lang_code = lang.split(';')[0].strip().split('-')[0].lower()
                if lang_code in supported:
                    return lang_code
            except:
                continue

        return None

    def _get_supported_languages(self):
        """
        Retourne la liste des langues supportées.
        """
        if hasattr(settings, 'DEEPSEEK_CONFIG'):
            return settings.DEEPSEEK_CONFIG.get('ENABLED_LANGUAGES', [settings.LANGUAGE_CODE])
        return [settings.LANGUAGE_CODE]


class TranslationPreferencesMiddleware(MiddlewareMixin):
    """
    Middleware pour gérer les préférences de traduction utilisateur.
    """

    def process_request(self, request):
        # Ajoute les préférences de traduction à l'objet request
        request.translation_preferences = self._get_user_preferences(request)

        # Vérifie si la traduction automatique est activée
        request.auto_translate_enabled = self._is_auto_translate_enabled(request)

    def _get_user_preferences(self, request):
        """
        Récupère les préférences de traduction de l'utilisateur.
        """
        preferences = {
            'auto_translate': True,
            'show_badge': True,
            'allow_editing': True,
            'preferred_languages': [],
        }

        try:
            # Préférences globales
            global_settings = TranslationSettings.objects.filter(user=None).first()
            if global_settings:
                preferences.update({
                    'auto_translate': global_settings.auto_translate_enabled,
                    'show_badge': global_settings.show_translation_badge,
                    'allow_editing': global_settings.allow_translation_editing,
                })

            # Préférences utilisateur (si authentifié)
            if request.user.is_authenticated:
                user_settings = TranslationSettings.objects.filter(user=request.user).first()
                if user_settings:
                    preferences.update({
                        'auto_translate': user_settings.auto_translate_enabled,
                        'show_badge': user_settings.show_translation_badge,
                        'allow_editing': user_settings.allow_translation_editing,
                        'preferred_languages': user_settings.preferred_languages or [],
                    })

            # Langues supportées
            preferences['supported_languages'] = self._get_supported_languages()

        except Exception as e:
            logger.error(f"Erreur récupération préférences: {e}")

        return preferences

    def _is_auto_translate_enabled(self, request):
        """
        Vérifie si la traduction automatique est activée.
        """
        if hasattr(request, 'translation_preferences'):
            return request.translation_preferences.get('auto_translate', True)
        return True

    def _get_supported_languages(self):
        """
        Retourne la liste des langues supportées.
        """
        if hasattr(settings, 'DEEPSEEK_CONFIG'):
            return settings.DEEPSEEK_CONFIG.get('ENABLED_LANGUAGES', [settings.LANGUAGE_CODE])
        return [settings.LANGUAGE_CODE]
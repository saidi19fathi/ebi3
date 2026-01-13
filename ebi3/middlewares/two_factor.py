# ~/ebi3/ebi3/middlewares/two_factor.py
"""
Middleware pour la vérification 2FA
"""
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class TwoFactorAuthMiddleware:
    """
    Middleware qui vérifie la 2FA pour les routes sensibles
    Compatible avec Django 6.0+
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.config = getattr(settings, 'TWO_FACTOR_MIDDLEWARE_CONFIG', {})

        # Routes exemptées de la 2FA - initialiser comme liste vide
        self.exempt_paths = []

    def __call__(self, request):
        """Méthode principale du middleware pour Django 6.0+"""
        # Initialiser les paths exemptés si ce n'est pas encore fait
        if not self.exempt_paths:
            self._initialize_exempt_paths()

        # Appeler process_request pour la logique 2FA
        response = self.process_request(request)

        # Si process_request retourne une réponse, c'est une redirection
        if response is not None:
            return response

        # Sinon, continuer avec le middleware suivant
        response = self.get_response(request)
        return response

    def _initialize_exempt_paths(self):
        """Initialiser les chemins exemptés - appelé lors de la première requête"""
        # Chemins fixes
        self.exempt_paths = [
            '/static/',
            '/media/',
            '/admin/login/',
            '/admin/jsi18n/',
            '/favicon.ico',
            '/robots.txt',
        ]

        # Ajouter les URLs dynamiques
        try:
            self.exempt_paths.append(reverse('users:login'))
        except NoReverseMatch:
            logger.warning("URL 'users:login' not found, skipping from 2FA exemptions")
            pass

        try:
            self.exempt_paths.append(reverse('users:logout'))
        except NoReverseMatch:
            logger.warning("URL 'users:logout' not found, skipping from 2FA exemptions")
            pass

        try:
            self.exempt_paths.append(reverse('users:register'))
        except NoReverseMatch:
            logger.warning("URL 'users:register' not found, skipping from 2FA exemptions")
            pass

        try:
            self.exempt_paths.append(reverse('core:home'))
        except NoReverseMatch:
            logger.warning("URL 'core:home' not found, skipping from 2FA exemptions")
            pass

        # Ajouter payment_webhook seulement si l'URL existe
        try:
            self.exempt_paths.append(reverse('payments:payment_webhook'))
        except NoReverseMatch:
            logger.warning("URL 'payments:payment_webhook' not found, skipping from 2FA exemptions")
            pass

    def process_request(self, request):
        """Vérifier si la 2FA est requise"""

        # Si le middleware n'est pas activé
        if not self.config.get('enabled', True):
            return None

        # Vérifier si l'utilisateur est authentifié
        if not request.user.is_authenticated:
            return None

        # Vérifier les chemins exemptés
        if any(request.path.startswith(path) for path in self.exempt_paths):
            return None

        # Vérifier si l'utilisateur a la 2FA activée
        if not hasattr(request.user, 'two_factor_enabled') or not request.user.two_factor_enabled:
            return None

        # Vérifier si la session a déjà validé la 2FA
        if request.session.get('2fa_verified', False):
            # Vérifier si la session 2FA est encore valide
            from django.utils import timezone
            verified_at = request.session.get('2fa_verified_at')
            if verified_at:
                verified_time = timezone.datetime.fromisoformat(verified_at)
                remember_days = self.config.get('remember_device_days', 30)

                # Si "se souvenir de l'appareil" est activé et valide
                if request.session.get('2fa_remember_device'):
                    if timezone.now() - verified_time < timezone.timedelta(days=remember_days):
                        return None
                # Sinon, vérifier si c'est dans la même session
                elif timezone.now() - verified_time < timezone.timedelta(hours=1):
                    return None

        # Vérifier si la route est sensible
        sensitive_paths = self.config.get('sensitive_paths', [])
        is_sensitive_path = any(request.path.startswith(path) for path in sensitive_paths)

        # Pour le staff, toujours vérifier
        is_staff_required = self.config.get('required_for_staff', True) and request.user.is_staff

        # Pour les actions sensibles, toujours vérifier
        is_sensitive_action = self.config.get('required_for_sensitive_actions', True) and is_sensitive_path

        if is_staff_required or is_sensitive_action:
            # Rediriger vers la vérification 2FA
            try:
                verify_url = reverse('users:verify_2fa')
            except NoReverseMatch:
                logger.error("URL 'users:verify_2fa' not found, cannot redirect to 2FA verification")
                return None

            # Stocker la prochaine URL
            request.session['next_url'] = request.get_full_path()

            logger.info(f"2FA required for user {request.user} accessing {request.path}")
            return redirect(verify_url)

        return None
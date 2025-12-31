# ~/ebi3/ebi3/middlewares/rate_limit.py
"""
Middleware pour la limitation de débit (rate limiting)
"""
import time
import hashlib
from django.core.cache import cache
# from django.utils.deprecation import MiddlewareMixin  # REMOVED for Django 6.0
from django.http import HttpResponseForbidden, JsonResponse
from django.conf import settings
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Appeler process_request si existant
        if hasattr(self, 'process_request'):
            response = self.process_request(request)
            if response is not None:
                return response

        response = self.get_response(request)
        return response
    """
    Middleware de limitation de débit par IP et utilisateur
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.config = {
            'enabled': getattr(settings, 'RATE_LIMIT_ENABLED', True),
            'default': getattr(settings, 'RATE_LIMIT_DEFAULT', '1000/hour'),
            'anonymous': getattr(settings, 'RATE_LIMIT_ANONYMOUS', '100/hour'),
            'authenticated': getattr(settings, 'RATE_LIMIT_AUTHENTICATED', '5000/hour'),
            'special': getattr(settings, 'RATE_LIMIT_SPECIAL', {}),
        }

    def parse_rate(self, rate):
        """
        Parse une chaîne de rate limit comme '100/hour'
        Retourne (nombre, secondes)
        """
        if rate == 'unlimited':
            return None, None

        try:
            num, period = rate.split('/')
            num = int(num)

            if period == 'second':
                period_seconds = 1
            elif period == 'minute':
                period_seconds = 60
            elif period == 'hour':
                period_seconds = 3600
            elif period == 'day':
                period_seconds = 86400
            else:
                raise ValueError(f"Unknown period: {period}")

            return num, period_seconds
        except ValueError as e:
            logger.error(f"Invalid rate limit format: {rate} - {e}")
            return 1000, 3600  # Default fallback

    def get_rate_limit_for_path(self, path):
        """Obtenir la limite de débit pour un chemin spécifique"""
        for route, rate in self.config['special'].items():
            if path.startswith(route):
                return rate
        return None

    def get_client_identifier(self, request):
        """
        Obtenir un identifiant unique pour le client.
        Utilise l'IP pour les anonymes, user_id pour les authentifiés.
        """
        # Obtenir l'IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        # Pour les utilisateurs authentifiés, combiner IP et user_id
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}:{ip}"
        else:
            identifier = f"anon:{ip}"

        return identifier

    def is_rate_limited(self, request):
        """Vérifier si le client a dépassé la limite de débit"""
        if not self.config['enabled']:
            return False

        identifier = self.get_client_identifier(request)
        path = request.path

        # Déterminer la limite à appliquer
        special_rate = self.get_rate_limit_for_path(path)

        if special_rate:
            rate_limit = special_rate
        elif request.user.is_authenticated:
            rate_limit = self.config['authenticated']
        else:
            rate_limit = self.config['anonymous']

        # Si pas de limite
        if rate_limit == 'unlimited':
            return False

        # Parse la limite
        num_requests, period_seconds = self.parse_rate(rate_limit)

        if num_requests is None:
            return False

        # Créer une clé de cache basée sur l'identifiant, le chemin et la période
        current_window = int(time.time() / period_seconds)
        cache_key = f"ratelimit:{identifier}:{path}:{current_window}"

        # Obtenir le compteur actuel
        current_count = cache.get(cache_key, 0)

        # Si la limite est dépassée
        if current_count >= num_requests:
            logger.warning(f"Rate limit exceeded: {identifier} on {path}")

            # Enregistrer l'événement
            from audit.models import RateLimitEvent
            try:
                RateLimitEvent.objects.create(
                    identifier=identifier[:100],
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    path=path[:200],
                    user=request.user if request.user.is_authenticated else None,
                    limit=num_requests,
                    period=period_seconds,
                    count=current_count + 1
                )
            except:
                pass

            return True

        # Incrémenter le compteur
        cache.set(cache_key, current_count + 1, period_seconds)

        return False

    def process_request(self, request):
        """Vérifier la limite de débit avant de traiter la requête"""

        # Chemins exemptés
        exempt_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/robots.txt',
        ]

        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        # Vérifier la limite
        if self.is_rate_limited(request):
            response_data = {
                'error': 'rate_limit_exceeded',
                'message': 'Too many requests. Please try again later.',
                'retry_after': 60,  # secondes
            }

            response = JsonResponse(response_data, status=429)
            response['Retry-After'] = '60'
            return response

        return None

    def process_response(self, request, response):
        """Ajouter des headers de rate limiting à la réponse"""
        if not self.config['enabled']:
            return response

        identifier = self.get_client_identifier(request)
        path = request.path

        # Obtenir la limite actuelle
        special_rate = self.get_rate_limit_for_path(path)

        if special_rate:
            rate_limit = special_rate
        elif request.user.is_authenticated:
            rate_limit = self.config['authenticated']
        else:
            rate_limit = self.config['anonymous']

        if rate_limit != 'unlimited':
            num_requests, period_seconds = self.parse_rate(rate_limit)

            if num_requests:
                # Ajouter les headers de rate limiting
                current_window = int(time.time() / period_seconds)
                cache_key = f"ratelimit:{identifier}:{path}:{current_window}"
                current_count = cache.get(cache_key, 0)

                response['X-RateLimit-Limit'] = str(num_requests)
                response['X-RateLimit-Remaining'] = str(max(0, num_requests - current_count))
                response['X-RateLimit-Reset'] = str((current_window + 1) * period_seconds)

        return response
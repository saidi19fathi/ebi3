# ~/ebi3/ebi3/middlewares/audit.py
"""
Middleware d'audit pour le logging complet des requêtes et réponses
"""
import time
import json
import logging
# from django.utils.deprecation import MiddlewareMixin  # REMOVED for Django 6.0
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class AuditMiddleware::
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
    Middleware d'audit qui logge :
    - Toutes les requêtes entrantes
    - Les réponses sortantes
    - Les erreurs
    - Les requêtes lentes
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.config = getattr(settings, 'AUDIT_MIDDLEWARE_CONFIG', {})

    def get_client_ip(self, request):
        """Obtenir l'adresse IP réelle du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def mask_sensitive_data(self, data):
        """Masquer les données sensibles"""
        if not isinstance(data, dict):
            return data

        masked_fields = self.config.get('mask_fields', [])
        result = data.copy()

        for key, value in result.items():
            if isinstance(value, dict):
                result[key] = self.mask_sensitive_data(value)
            elif isinstance(value, str) and any(field in key.lower() for field in masked_fields):
                result[key] = '***MASKED***'

        return result

    def process_request(self, request):
        """Enregistrer le début de la requête"""
        if not self.config.get('log_requests', True):
            return None

        # Début du timer
        request.start_time = time.time()

        # Préparer les données de log
        ip = self.get_client_ip(request)
        user = request.user if request.user.is_authenticated else 'anonymous'

        log_data = {
            'timestamp': timezone.now().isoformat(),
            'type': 'REQUEST_START',
            'ip': ip,
            'user': str(user),
            'method': request.method,
            'path': request.path,
            'query_string': request.META.get('QUERY_STRING', ''),
            'content_type': request.content_type,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
            'referer': request.META.get('HTTP_REFERER', '')[:200],
        }

        # Ajouter les paramètres (masqués si nécessaire)
        if self.config.get('log_sensitive_data', False):
            if request.method == 'GET':
                log_data['get_params'] = dict(request.GET)
            elif request.method == 'POST':
                log_data['post_params'] = dict(request.POST)
        else:
            if request.method == 'GET':
                log_data['get_params'] = self.mask_sensitive_data(dict(request.GET))
            elif request.method == 'POST':
                log_data['post_params'] = self.mask_sensitive_data(dict(request.POST))

        # Logger
        logger.info(f"AUDIT REQUEST: {json.dumps(log_data)}")

        return None

    def process_response(self, request, response):
        """Enregistrer la fin de la requête"""
        if not hasattr(request, 'start_time'):
            return response

        end_time = time.time()
        duration = end_time - request.start_time

        # Vérifier les requêtes lentes
        slow_threshold = self.config.get('slow_request_threshold', 5.0)
        is_slow = duration > slow_threshold

        if self.config.get('log_responses', True) or (is_slow and self.config.get('log_slow_requests', True)):
            ip = self.get_client_ip(request)
            user = request.user if request.user.is_authenticated else 'anonymous'

            log_data = {
                'timestamp': timezone.now().isoformat(),
                'type': 'REQUEST_END',
                'ip': ip,
                'user': str(user),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration': round(duration, 3),
                'is_slow': is_slow,
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
            }

            # Ajouter les détails d'erreur pour les codes 4xx/5xx
            if response.status_code >= 400:
                log_data['error'] = True
                if hasattr(response, 'content'):
                    try:
                        content = response.content.decode('utf-8')[:500]
                        log_data['error_content'] = content
                    except:
                        pass

            # Logger
            logger.info(f"AUDIT RESPONSE: {json.dumps(log_data)}")

            # Alerter pour les requêtes lentes
            if is_slow:
                logger.warning(f"SLOW REQUEST ({duration:.2f}s): {request.method} {request.path}")

            # Sauvegarder dans la base de données
            from audit.models import AuditLog
            try:
                AuditLog.objects.create(
                    timestamp=timezone.now(),
                    user=user if user != 'anonymous' else None,
                    action=f"{request.method} {request.path}",
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                    status_code=response.status_code,
                    duration=duration,
                    is_slow=is_slow,
                    metadata=log_data
                )
            except Exception as e:
                logger.error(f"Failed to save audit log: {e}")

        return response

    def process_exception(self, request, exception):
        """Enregistrer les exceptions"""
        if not self.config.get('log_errors', True):
            return None

        ip = self.get_client_ip(request)
        user = request.user if request.user.is_authenticated else 'anonymous'

        log_data = {
            'timestamp': timezone.now().isoformat(),
            'type': 'EXCEPTION',
            'ip': ip,
            'user': str(user),
            'method': request.method,
            'path': request.path,
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': self.get_traceback(exception),
        }

        # Logger
        logger.error(f"AUDIT EXCEPTION: {json.dumps(log_data)}")

        # Sauvegarder dans la base de données
        from audit.models import ErrorLog
        try:
            ErrorLog.objects.create(
                timestamp=timezone.now(),
                user=user if user != 'anonymous' else None,
                ip_address=ip,
                method=request.method,
                path=request.path,
                exception_type=type(exception).__name__,
                exception_message=str(exception)[:500],
                traceback=log_data['traceback'][:2000],
                metadata=log_data
            )
        except Exception as e:
            logger.error(f"Failed to save error log: {e}")

        return None

    def get_traceback(self, exception):
        """Obtenir la traceback de l'exception"""
        import traceback
        return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
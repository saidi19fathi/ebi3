# ~/ebi3/ebi3/middlewares/security.py
"""
Middleware de sécurité avancé pour la détection et prévention d'attaques
"""
import re
import time
import hashlib
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden, HttpResponse
# from django.utils.deprecation import MiddlewareMixin  # REMOVED for Django 6.0
from django.utils import timezone
import logging
from ipaddress import ip_address, ip_network
import json

logger = logging.getLogger(__name__)


class SecurityMiddleware::
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
    Middleware de sécurité avancé qui détecte et bloque :
    - Attaques par injection SQL
    - Tentatives XSS
    - Attaques par force brute
    - IPs suspectes
    - Requêtes malveillantes
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.config = getattr(settings, 'SECURITY_MIDDLEWARE_CONFIG', {})

        # Patterns de détection
        self.sql_injection_patterns = [
            r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
            r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
            r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
            r"((\%27)|(\'))union",
            r"exec(\s|\+)+(s|x)p\w+",
            r"insert\s+into.+values",
            r"select\s+.+from",
            r"drop\s+(table|database)",
            r"update\s+.+set",
            r"delete\s+from",
            r"truncate\s+table",
        ]

        self.xss_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"alert\(",
            r"document\.cookie",
            r"eval\(",
            r"<iframe.*?>",
            r"<object.*?>",
            r"<embed.*?>",
            r"<applet.*?>",
        ]

        # Liste noire d'IPs (peut être chargée depuis une base de données)
        self.blacklisted_ips = set()
        self.suspicious_ips = {}

        # Charger les IPs blacklistées depuis le cache
        self.load_blacklisted_ips()

    def load_blacklisted_ips(self):
        """Charger les IPs blacklistées depuis le cache"""
        cached = cache.get('security:blacklisted_ips')
        if cached:
            self.blacklisted_ips = set(cached)

    def save_blacklisted_ips(self):
        """Sauvegarder les IPs blacklistées dans le cache"""
        cache.set('security:blacklisted_ips', list(self.blacklisted_ips), 3600)

    def get_client_ip(self, request):
        """Obtenir l'adresse IP réelle du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def is_ip_blacklisted(self, ip):
        """Vérifier si une IP est blacklistée"""
        return ip in self.blacklisted_ips

    def blacklist_ip(self, ip, reason="Suspicious activity"):
        """Ajouter une IP à la liste noire"""
        self.blacklisted_ips.add(ip)
        self.save_blacklisted_ips()

        # Log l'événement
        logger.warning(f"IP {ip} blacklisted: {reason}")

        # Sauvegarder dans la base de données si nécessaire
        from audit.models import SecurityEvent
        SecurityEvent.objects.create(
            event_type='IP_BLACKLISTED',
            ip_address=ip,
            description=reason,
            severity='HIGH'
        )

    def detect_sql_injection(self, request):
        """Détecter les tentatives d'injection SQL"""
        if not self.config.get('detect_sql_injection', True):
            return False

        # Vérifier les paramètres GET
        for key, value in request.GET.items():
            if isinstance(value, str):
                for pattern in self.sql_injection_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True

        # Vérifier les paramètres POST
        for key, value in request.POST.items():
            if isinstance(value, str):
                for pattern in self.sql_injection_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True

        # Vérifier le body pour les requêtes JSON
        if request.content_type == 'application/json' and request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
                # Convertir le dictionnaire en chaîne pour vérification
                data_str = json.dumps(data)
                for pattern in self.sql_injection_patterns:
                    if re.search(pattern, data_str, re.IGNORECASE):
                        return True
            except:
                pass

        return False

    def detect_xss(self, request):
        """Détecter les tentatives XSS"""
        if not self.config.get('detect_xss', True):
            return False

        # Vérifier les paramètres GET
        for key, value in request.GET.items():
            if isinstance(value, str):
                for pattern in self.xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True

        # Vérifier les paramètres POST
        for key, value in request.POST.items():
            if isinstance(value, str):
                for pattern in self.xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return True

        return False

    def detect_bruteforce(self, request):
        """Détecter les attaques par force brute"""
        if not self.config.get('detect_bruteforce', True):
            return False

        ip = self.get_client_ip(request)
        path = request.path

        # Vérifier les tentatives de login
        if '/login/' in path or '/signin/' in path:
            cache_key = f'bruteforce:{ip}:{path}'
            attempts = cache.get(cache_key, 0)

            max_attempts = self.config.get('max_login_attempts', 5)
            if attempts >= max_attempts:
                # Bloquer l'IP temporairement
                block_time = self.config.get('login_block_time', 3600)
                cache_key_block = f'ip_blocked:{ip}'
                cache.set(cache_key_block, True, block_time)

                # Ajouter à la liste noire si trop d'échecs
                if attempts >= max_attempts * 2:
                    self.blacklist_ip(ip, "Too many failed login attempts")

                return True

            # Incrémenter le compteur
            cache.set(cache_key, attempts + 1, 300)  # 5 minutes

        return False

    def check_request_frequency(self, request):
        """Vérifier la fréquence des requêtes"""
        ip = self.get_client_ip(request)
        cache_key = f'request_freq:{ip}'

        # Obtenir l'historique des requêtes
        request_history = cache.get(cache_key, [])
        current_time = time.time()

        # Filtrer les requêtes des dernières secondes
        recent_requests = [t for t in request_history if current_time - t < 10]

        # Si trop de requêtes en 10 secondes
        if len(recent_requests) > 100:  # 10 requêtes par seconde max
            return True

        # Ajouter la requête actuelle
        recent_requests.append(current_time)
        cache.set(cache_key, recent_requests[-100:], 60)  # Garder 100 dernières

        return False

    def process_request(self, request):
        """Traiter la requête avant qu'elle n'atteigne la vue"""

        # Récupérer l'IP du client
        ip = self.get_client_ip(request)

        # 1. Vérifier si l'IP est blacklistée
        if self.is_ip_blacklisted(ip):
            logger.warning(f"Blacklisted IP attempted access: {ip}")
            return HttpResponseForbidden(
                "Access denied. Your IP address has been blocked for security reasons."
            )

        # 2. Vérifier si l'IP est temporairement bloquée
        if cache.get(f'ip_blocked:{ip}'):
            logger.warning(f"Temporarily blocked IP attempted access: {ip}")
            return HttpResponseForbidden(
                "Access temporarily blocked. Please try again later."
            )

        # 3. Détecter les attaques par injection SQL
        if self.detect_sql_injection(request):
            logger.warning(f"SQL injection attempt from IP {ip}")
            self.blacklist_ip(ip, "SQL injection attempt")
            return HttpResponseForbidden("Security violation detected.")

        # 4. Détecter les tentatives XSS
        if self.detect_xss(request):
            logger.warning(f"XSS attempt from IP {ip}")
            self.blacklist_ip(ip, "XSS attempt")
            return HttpResponseForbidden("Security violation detected.")

        # 5. Détecter les attaques par force brute
        if self.detect_bruteforce(request):
            logger.warning(f"Bruteforce attempt from IP {ip}")
            return HttpResponseForbidden(
                "Too many login attempts. Please try again later."
            )

        # 6. Vérifier la fréquence des requêtes
        if self.check_request_frequency(request):
            logger.warning(f"High request frequency from IP {ip}")
            # Bloquer temporairement
            cache.set(f'ip_blocked:{ip}', True, 300)  # 5 minutes
            return HttpResponseForbidden(
                "Request rate limit exceeded. Please slow down."
            )

        # 7. Vérifier les headers suspects
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if self.is_suspicious_user_agent(user_agent):
            logger.warning(f"Suspicious User-Agent from IP {ip}: {user_agent}")
            # Suivre mais ne pas bloquer immédiatement
            self.track_suspicious_activity(ip, "Suspicious User-Agent")

        # Ajouter l'IP à l'objet request pour un usage ultérieur
        request.client_ip = ip

        return None

    def is_suspicious_user_agent(self, user_agent):
        """Détecter les User-Agents suspects"""
        suspicious_patterns = [
            r'sqlmap', r'nmap', r'nikto', r'hydra',
            r'wget', r'curl', r'python-requests',
            r'^$',  # User-Agent vide
        ]

        if not user_agent:
            return True

        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return True

        return False

    def track_suspicious_activity(self, ip, reason):
        """Suivre les activités suspectes"""
        cache_key = f'suspicious:{ip}'
        activities = cache.get(cache_key, [])
        activities.append({
            'timestamp': timezone.now().isoformat(),
            'reason': reason
        })
        cache.set(cache_key, activities[-10:], 3600)  # Garder 10 dernières

        # Si trop d'activités suspectes, blacklister
        if len(activities) >= 5:
            self.blacklist_ip(ip, f"Multiple suspicious activities: {reason}")

    def process_response(self, request, response):
        """Traiter la réponse après la vue"""

        # Ajouter des headers de sécurité
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Content Security Policy (CSP)
        # Note: À adapter selon les besoins de votre application
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response['Content-Security-Policy'] = csp_policy

        # Feature Policy
        response['Feature-Policy'] = (
            "camera 'none'; "
            "microphone 'none'; "
            "geolocation 'none'; "
            "payment 'none';"
        )

        # Permissions Policy (remplace Feature-Policy)
        response['Permissions-Policy'] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=()"
        )

        # Désactiver la mise en cache pour les pages sensibles
        sensitive_paths = ['/admin/', '/payments/', '/wallet/', '/settings/']
        if any(request.path.startswith(path) for path in sensitive_paths):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        # Log si configuré
        if self.config.get('log_all_requests', True):
            self.log_request(request, response)

        return response

    def log_request(self, request, response):
        """Logger les détails de la requête"""
        ip = self.get_client_ip(request)
        user = request.user if hasattr(request, 'user') else 'anonymous'

        log_data = {
            'timestamp': timezone.now().isoformat(),
            'ip': ip,
            'user': str(user),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'referer': request.META.get('HTTP_REFERER', ''),
            'content_type': request.content_type,
        }

        # Ne pas logger les données sensibles
        sensitive_keys = ['password', 'token', 'secret', 'key', 'pin', 'cvv']

        if request.method == 'GET':
            # Filtrer les paramètres GET sensibles
            filtered_params = {}
            for key, value in request.GET.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    filtered_params[key] = '***FILTERED***'
                else:
                    filtered_params[key] = value
            log_data['get_params'] = filtered_params

        elif request.method == 'POST':
            # Filtrer les paramètres POST sensibles
            filtered_params = {}
            for key, value in request.POST.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    filtered_params[key] = '***FILTERED***'
                else:
                    filtered_params[key] = value
            log_data['post_params'] = filtered_params

        # Logger
        logger.info(f"Security log: {json.dumps(log_data)}")

        # Sauvegarder dans la base de données si nécessaire
        from audit.models import RequestLog
        try:
            RequestLog.objects.create(
                ip_address=ip,
                user=user if user != 'anonymous' else None,
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                user_agent=log_data['user_agent'][:200],
                referer=log_data['referer'][:200],
                request_data=log_data
            )
        except:
            pass  # Ne pas bloquer si le logging échoue
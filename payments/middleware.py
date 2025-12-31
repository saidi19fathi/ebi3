# ~/ebi3/payments/middleware.py
"""
Middleware pour la sécurité des paiements
"""

import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from ipaddress import ip_address, ip_network

from .exceptions import RateLimitExceededError, FraudDetectionError

logger = logging.getLogger(__name__)


class PaymentSecurityMiddleware(MiddlewareMixin):
    """
    Middleware de sécurité pour les paiements
    - Limite de taux
    - Détection de fraude
    - Filtrage IP
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        # Configuration
        self.rate_limit = getattr(settings, 'PAYMENT_RATE_LIMIT', {
            'requests_per_minute': 60,
            'requests_per_hour': 300,
            'requests_per_day': 1000,
        })

        self.blocked_ips = getattr(settings, 'BLOCKED_IPS', [])
        self.allowed_countries = getattr(settings, 'ALLOWED_COUNTRIES_FOR_PAYMENTS', [])

        logger.info("PaymentSecurityMiddleware initialized")

    def __call__(self, request):
        # Ne pas appliquer le middleware aux URLs admin et statiques
        if self._should_skip_middleware(request):
            return self.get_response(request)

        # Vérifier si c'est une requête de paiement
        if self._is_payment_request(request):
            try:
                # 1. Vérifier l'adresse IP
                self._check_ip_address(request)

                # 2. Appliquer la limite de taux
                self._apply_rate_limiting(request)

                # 3. Détecter les comportements suspects
                self._detect_suspicious_behavior(request)

            except (RateLimitExceededError, FraudDetectionError) as e:
                logger.warning(f"Payment security violation: {str(e)} - IP: {self._get_client_ip(request)}")
                return self._security_error_response(request, e)
            except Exception as e:
                logger.error(f"Payment security middleware error: {str(e)}")
                # Ne pas bloquer en cas d'erreur interne

        return self.get_response(request)

    def _should_skip_middleware(self, request):
        """Déterminer si le middleware doit être ignoré"""
        skip_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
            '/api/docs/',
        ]

        path = request.path
        return any(path.startswith(skip_path) for skip_path in skip_paths)

    def _is_payment_request(self, request):
        """Déterminer si c'est une requête de paiement"""
        payment_paths = [
            '/payments/',
            '/checkout/',
            '/api/payments/',
            '/webhooks/stripe/',
            '/webhooks/paypal/',
        ]

        path = request.path
        return any(path.startswith(payment_path) for payment_path in payment_paths)

    def _get_client_ip(self, request):
        """Obtenir l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _check_ip_address(self, request):
        """Vérifier l'adresse IP du client"""
        client_ip = self._get_client_ip(request)

        # Vérifier les IPs bloquées
        for blocked_ip in self.blocked_ips:
            if ip_address(client_ip) in ip_network(blocked_ip):
                logger.warning(f"Blocked IP attempt: {client_ip}")
                raise FraudDetectionError(
                    message=_("Accès non autorisé."),
                    risk_level='HIGH'
                )

        # Vérifier le pays (si géolocalisation activée)
        if hasattr(settings, 'GEOIP_PATH') and self.allowed_countries:
            try:
                from django.contrib.gis.geoip2 import GeoIP2
                g = GeoIP2()
                country_code = g.country_code(client_ip)

                if country_code and country_code not in self.allowed_countries:
                    logger.warning(f"Payment attempt from restricted country: {country_code} - IP: {client_ip}")
                    raise FraudDetectionError(
                        message=_("Paiements non autorisés depuis votre pays."),
                        risk_level='MEDIUM'
                    )
            except Exception as e:
                logger.debug(f"GeoIP check failed: {str(e)}")
                # Ne pas bloquer en cas d'erreur de géolocalisation

    def _apply_rate_limiting(self, request):
        """Appliquer la limite de taux"""
        client_ip = self._get_client_ip(request)
        user_id = request.user.id if request.user.is_authenticated else None

        # Clés de cache pour la limite de taux
        minute_key = f"rate_limit:minute:{client_ip}:{user_id}"
        hour_key = f"rate_limit:hour:{client_ip}:{user_id}"
        day_key = f"rate_limit:day:{client_ip}:{user_id}"

        current_time = int(time.time())

        # Limite par minute
        minute_requests = cache.get(minute_key, [])
        minute_requests = [t for t in minute_requests if t > current_time - 60]

        if len(minute_requests) >= self.rate_limit['requests_per_minute']:
            raise RateLimitExceededError(
                message=_("Trop de requêtes. Veuillez réessayer dans une minute."),
                retry_after=60
            )

        minute_requests.append(current_time)
        cache.set(minute_key, minute_requests, 60)

        # Limite par heure
        hour_requests = cache.get(hour_key, [])
        hour_requests = [t for t in hour_requests if t > current_time - 3600]

        if len(hour_requests) >= self.rate_limit['requests_per_hour']:
            raise RateLimitExceededError(
                message=_("Trop de requêtes. Veuillez réessayer dans une heure."),
                retry_after=3600
            )

        hour_requests.append(current_time)
        cache.set(hour_key, hour_requests, 3600)

        # Limite par jour
        day_requests = cache.get(day_key, [])
        day_requests = [t for t in day_requests if t > current_time - 86400]

        if len(day_requests) >= self.rate_limit['requests_per_day']:
            raise RateLimitExceededError(
                message=_("Limite quotidienne dépassée. Réessayez demain."),
                retry_after=86400
            )

        day_requests.append(current_time)
        cache.set(day_key, day_requests, 86400)

    def _detect_suspicious_behavior(self, request):
        """Détecter les comportements suspects"""
        # 1. Vérifier les en-têtes User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not user_agent or len(user_agent) < 10:
            logger.warning(f"Suspicious request: Missing or short User-Agent - IP: {self._get_client_ip(request)}")
            raise FraudDetectionError(
                message=_("Requête suspecte détectée."),
                risk_level='LOW'
            )

        # 2. Vérifier les bots connus
        bot_keywords = ['bot', 'crawler', 'spider', 'scraper']
        if any(keyword in user_agent.lower() for keyword in bot_keywords):
            logger.warning(f"Bot detected: {user_agent} - IP: {self._get_client_ip(request)}")
            raise FraudDetectionError(
                message=_("Les bots ne sont pas autorisés."),
                risk_level='MEDIUM'
            )

        # 3. Vérifier les requêtes POST sans Referer (pour les formulaires)
        if request.method == 'POST' and not request.META.get('HTTP_REFERER'):
            if request.path.startswith('/payments/') or request.path.startswith('/checkout/'):
                logger.warning(f"Suspicious POST without Referer: {request.path} - IP: {self._get_client_ip(request)}")
                raise FraudDetectionError(
                    message=_("Requête suspecte détectée."),
                    risk_level='MEDIUM'
                )

        # 4. Vérifier les tailles de requêtes anormales
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"Oversized request: {content_length} bytes - IP: {self._get_client_ip(request)}")
            raise FraudDetectionError(
                message=_("Requête trop volumineuse."),
                risk_level='LOW'
            )

    def _security_error_response(self, request, exception):
        """Réponse d'erreur de sécurité"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path.startswith('/api/'):
            return JsonResponse({
                'error': True,
                'message': str(exception),
                'code': getattr(exception, '__class__.__name__', 'SECURITY_ERROR')
            }, status=429 if isinstance(exception, RateLimitExceededError) else 403)

        return HttpResponseForbidden(f"""
            <html>
                <head>
                    <title>Erreur de sécurité</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                        .error {{ color: #d32f2f; }}
                    </style>
                </head>
                <body>
                    <h1 class="error">Erreur de sécurité</h1>
                    <p>{str(exception)}</p>
                    <p>Veuillez contacter le support si vous pensez qu'il s'agit d'une erreur.</p>
                </body>
            </html>
        """)


class PaymentDataMiddleware(MiddlewareMixin):
    """
    Middleware pour sécuriser les données de paiement
    - Masquer les données sensibles dans les logs
    - Valider les tokens CSRF pour les paiements
    - Prévenir les fuites d'informations
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        # Données sensibles à masquer
        self.sensitive_fields = [
            'card_number', 'cvv', 'expiry_date',
            'password', 'token', 'secret_key',
            'iban', 'bic', 'account_number',
            'private_key', 'api_key'
        ]

        logger.info("PaymentDataMiddleware initialized")

    def process_request(self, request):
        """Traiter la requête entrante"""
        # Renforcer la validation CSRF pour les paiements
        if self._is_sensitive_payment_request(request):
            if not request.META.get('CSRF_COOKIE'):
                logger.warning(f"Missing CSRF token for payment request: {request.path}")
                # Ne pas bloquer, mais logger l'événement

        return None

    def process_response(self, request, response):
        """Traiter la réponse sortante"""
        # Masquer les données sensibles dans les logs
        if hasattr(response, 'data'):
            self._mask_sensitive_data(response.data)

        # Ajouter des en-têtes de sécurité
        response['X-Payment-Security'] = 'enabled'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'

        # Pour les réponses JSON de paiement, ne pas mettre en cache
        if request.path.startswith('/payments/') or request.path.startswith('/api/payments/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response

    def _is_sensitive_payment_request(self, request):
        """Déterminer si c'est une requête de paiement sensible"""
        sensitive_paths = [
            '/payments/process/',
            '/payments/webhook/',
            '/checkout/confirm/',
            '/api/payments/charge/',
        ]

        return any(request.path.startswith(path) for path in sensitive_paths)

    def _mask_sensitive_data(self, data):
        """Masquer les données sensibles"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                    data[key] = '***MASKED***'
                elif isinstance(value, (dict, list)):
                    self._mask_sensitive_data(value)
        elif isinstance(data, list):
            for item in data:
                self._mask_sensitive_data(item)

    def process_exception(self, request, exception):
        """Traiter les exceptions"""
        # Ne pas logger les données sensibles dans les exceptions
        logger.error(f"Payment exception: {type(exception).__name__} - Path: {request.path}")
        return None


class PaymentSessionMiddleware(MiddlewareMixin):
    """
    Middleware pour la gestion des sessions de paiement
    - Session dédiée pour les paiements
    - Timeout de session
    - Validation de session
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        self.session_timeout = getattr(settings, 'PAYMENT_SESSION_TIMEOUT', 1800)  # 30 minutes
        self.payment_session_key = 'payment_session_data'

        logger.info("PaymentSessionMiddleware initialized")

    def process_request(self, request):
        """Traiter la requête entrante"""
        if self._is_payment_flow(request):
            # Initialiser ou vérifier la session de paiement
            self._initialize_payment_session(request)

            # Vérifier le timeout de session
            if self._is_session_expired(request):
                logger.info(f"Payment session expired for user: {request.user.id if request.user.is_authenticated else 'anonymous'}")
                # Nettoyer la session expirée
                if self.payment_session_key in request.session:
                    del request.session[self.payment_session_key]

        return None

    def process_response(self, request, response):
        """Traiter la réponse sortante"""
        if self._is_payment_flow(request):
            # Mettre à jour le timestamp de la session
            if hasattr(request, 'payment_session'):
                request.session[f'{self.payment_session_key}_timestamp'] = time.time()
                request.session.modified = True

        return response

    def _is_payment_flow(self, request):
        """Déterminer si c'est un flux de paiement"""
        payment_paths = [
            '/checkout/',
            '/payments/checkout/',
            '/payments/confirm/',
            '/payments/process/',
        ]

        return any(request.path.startswith(path) for path in payment_paths)

    def _initialize_payment_session(self, request):
        """Initialiser la session de paiement"""
        if self.payment_session_key not in request.session:
            request.session[self.payment_session_key] = {
                'started_at': time.time(),
                'step': 'initialized',
                'data': {},
                'attempts': 0,
            }
            request.session[f'{self.payment_session_key}_timestamp'] = time.time()
            request.session.modified = True

        # Stocker dans l'objet request pour un accès facile
        request.payment_session = request.session[self.payment_session_key]

    def _is_session_expired(self, request):
        """Vérifier si la session a expiré"""
        if f'{self.payment_session_key}_timestamp' not in request.session:
            return True

        last_activity = request.session[f'{self.payment_session_key}_timestamp']
        return (time.time() - last_activity) > self.session_timeout

    def get_payment_session_data(self, request, key=None, default=None):
        """Obtenir les données de session de paiement"""
        if not hasattr(request, 'payment_session'):
            return default

        if key:
            return request.payment_session.get('data', {}).get(key, default)

        return request.payment_session.get('data', {})

    def set_payment_session_data(self, request, key, value):
        """Définir les données de session de paiement"""
        if not hasattr(request, 'payment_session'):
            self._initialize_payment_session(request)

        if 'data' not in request.payment_session:
            request.payment_session['data'] = {}

        request.payment_session['data'][key] = value
        request.session.modified = True

    def increment_payment_attempts(self, request):
        """Incrémenter le compteur de tentatives"""
        if not hasattr(request, 'payment_session'):
            self._initialize_payment_session(request)

        request.payment_session['attempts'] = request.payment_session.get('attempts', 0) + 1
        request.session.modified = True

        return request.payment_session['attempts']

    def clear_payment_session(self, request):
        """Effacer la session de paiement"""
        if self.payment_session_key in request.session:
            del request.session[self.payment_session_key]

        if f'{self.payment_session_key}_timestamp' in request.session:
            del request.session[f'{self.payment_session_key}_timestamp']

        if hasattr(request, 'payment_session'):
            delattr(request, 'payment_session')

        request.session.modified = True


class FraudDetectionMiddleware(MiddlewareMixin):
    """
    Middleware de détection de fraude avancée
    - Analyse comportementale
    - Score de risque
    - Blocage automatique
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

        # Configuration de détection de fraude
        self.risk_threshold = getattr(settings, 'FRAUD_RISK_THRESHOLD', 70)
        self.suspicious_patterns = [
            # Adresses email suspectes
            r'[\w\.-]+@[\w\.-]+\.(xyz|top|club|win|bid)',
            # IPs de VPN/Tor
            r'^(?:tor|vpn|proxy)',
            # User-Agents malformés
            r'^$|^(?:Mozilla|curl|Python|Java)/?',
        ]

        logger.info("FraudDetectionMiddleware initialized")

    def process_request(self, request):
        """Analyser la requête pour détecter la fraude"""
        if not self._is_payment_request(request):
            return None

        # Calculer le score de risque
        risk_score = self._calculate_risk_score(request)

        if risk_score >= self.risk_threshold:
            logger.warning(f"High risk payment detected: Score={risk_score}, IP={self._get_client_ip(request)}, Path={request.path}")

            # Bloquer immédiatement les scores très élevés
            if risk_score >= 90:
                raise FraudDetectionError(
                    message=_("Transaction bloquée pour des raisons de sécurité."),
                    risk_level='CRITICAL'
                )

            # Marquer pour examen manuel
            request.high_risk_payment = True
            request.risk_score = risk_score

        return None

    def _is_payment_request(self, request):
        """Vérifier si c'est une requête de paiement"""
        return request.path.startswith('/payments/') or request.path.startswith('/checkout/')

    def _get_client_ip(self, request):
        """Obtenir l'adresse IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

    def _calculate_risk_score(self, request):
        """Calculer le score de risque"""
        score = 0

        # 1. Vérifier l'adresse IP (30 points max)
        ip_score = self._calculate_ip_risk(request)
        score += ip_score

        # 2. Vérifier l'email (20 points max)
        email_score = self._calculate_email_risk(request)
        score += email_score

        # 3. Vérifier le comportement (30 points max)
        behavior_score = self._calculate_behavior_risk(request)
        score += behavior_score

        # 4. Vérifier les données de paiement (20 points max)
        payment_score = self._calculate_payment_data_risk(request)
        score += payment_score

        return min(score, 100)

    def _calculate_ip_risk(self, request):
        """Calculer le risque basé sur l'IP"""
        score = 0
        client_ip = self._get_client_ip(request)

        # Vérifier les IPs à haut risque
        high_risk_ips = getattr(settings, 'HIGH_RISK_IPS', [])
        for risky_ip in high_risk_ips:
            if ip_address(client_ip) in ip_network(risky_ip):
                score += 30
                break

        # Vérifier la géolocalisation
        try:
            from django.contrib.gis.geoip2 import GeoIP2
            g = GeoIP2()
            country = g.country_code(client_ip)

            high_risk_countries = getattr(settings, 'HIGH_RISK_COUNTRIES', [])
            if country in high_risk_countries:
                score += 20
        except Exception:
            pass

        # Vérifier si c'est une IP partagée (VPN/Proxy)
        if self._is_shared_ip(client_ip):
            score += 15

        return score

    def _calculate_email_risk(self, request):
        """Calculer le risque basé sur l'email"""
        score = 0

        # Récupérer l'email de la requête
        email = None
        if request.method == 'POST':
            if 'email' in request.POST:
                email = request.POST['email']
            elif hasattr(request, 'data') and 'email' in request.data:
                email = request.data['email']

        if email:
            # Vérifier les domaines à risque
            import re
            for pattern in self.suspicious_patterns:
                if re.search(pattern, email, re.IGNORECASE):
                    score += 20
                    break

            # Vérifier l'âge du compte (si utilisateur authentifié)
            if request.user.is_authenticated:
                account_age = (timezone.now() - request.user.date_joined).days
                if account_age < 1:  # Compte créé aujourd'hui
                    score += 10

        return score

    def _calculate_behavior_risk(self, request):
        """Calculer le risque basé sur le comportement"""
        score = 0

        # Vitesse de remplissage du formulaire
        if request.method == 'POST' and hasattr(request, 'payment_session'):
            session_data = request.payment_session
            if 'form_start_time' in session_data:
                form_time = time.time() - session_data['form_start_time']
                if form_time < 2:  # Formulaire rempli en moins de 2 secondes
                    score += 15

        # Heure de la transaction
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:  # Transactions nocturnes
            score += 10

        # Tentatives échouées récentes
        if hasattr(request, 'payment_session'):
            attempts = request.payment_session.get('attempts', 0)
            if attempts > 3:
                score += attempts * 5

        return score

    def _calculate_payment_data_risk(self, request):
        """Calculer le risque basé sur les données de paiement"""
        score = 0

        if request.method == 'POST':
            # Montant inhabituel
            amount = None
            if 'amount' in request.POST:
                try:
                    amount = float(request.POST['amount'])
                except ValueError:
                    pass

            if amount:
                # Montant très élevé
                if amount > 10000:
                    score += 15
                # Montant très faible (test)
                elif amount < 1:
                    score += 10

            # Données de carte BIN suspectes
            if 'card_number' in request.POST:
                card_number = request.POST['card_number'].replace(' ', '')
                if len(card_number) >= 6:
                    bin_number = card_number[:6]
                    suspicious_bins = getattr(settings, 'SUSPICIOUS_CARD_BINS', [])
                    if bin_number in suspicious_bins:
                        score += 20

        return score

    def _is_shared_ip(self, ip):
        """Vérifier si c'est une IP partagée (VPN/Proxy)"""
        # Liste simplifiée de plages IP connues pour les VPN/Proxy
        shared_ip_ranges = [
            '10.0.0.0/8',
            '172.16.0.0/12',
            '192.168.0.0/16',
            '100.64.0.0/10',  # CGNAT
        ]

        try:
            ip_addr = ip_address(ip)
            for ip_range in shared_ip_ranges:
                if ip_addr in ip_network(ip_range):
                    return True
        except ValueError:
            pass

        return False


class CORSMiddleware(MiddlewareMixin):
    """
    Middleware CORS spécifique aux paiements
    """

    def process_response(self, request, response):
        """Ajouter les en-têtes CORS pour les paiements"""
        # Appliquer seulement aux APIs de paiement
        if request.path.startswith('/api/payments/'):
            origin = request.META.get('HTTP_ORIGIN', '')

            # Vérifier les origines autorisées
            allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            if origin in allowed_origins or '*' in allowed_origins:
                response['Access-Control-Allow-Origin'] = origin
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
                response['Access-Control-Max-Age'] = '86400'  # 24 heures

        return response
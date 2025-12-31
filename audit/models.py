# ~/ebi3/audit/models.py
"""
Modèles pour l'audit et le logging de sécurité
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class AuditLog(models.Model):
    """Log d'audit général"""

    class ActionType(models.TextChoices):
        LOGIN = 'LOGIN', _('Connexion')
        LOGOUT = 'LOGOUT', _('Déconnexion')
        CREATE = 'CREATE', _('Création')
        UPDATE = 'UPDATE', _('Mise à jour')
        DELETE = 'DELETE', _('Suppression')
        VIEW = 'VIEW', _('Consultation')
        PAYMENT = 'PAYMENT', _('Paiement')
        REFUND = 'REFUND', _('Remboursement')
        WITHDRAWAL = 'WITHDRAWAL', _('Retrait')
        SECURITY = 'SECURITY', _('Événement sécurité')
        SYSTEM = 'SYSTEM', _('Système')

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('Log d\'audit')
        verbose_name_plural = _('Logs d\'audit')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user or 'System'} - {self.action_type} - {self.timestamp}"


class RequestLog(models.Model):
    """Log des requêtes HTTP"""

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField()
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    query_string = models.TextField(blank=True)
    status_code = models.IntegerField()
    user_agent = models.CharField(max_length=500, blank=True)
    referer = models.CharField(max_length=500, blank=True)
    duration = models.FloatField(null=True, blank=True)  # en secondes
    is_slow = models.BooleanField(default=False)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = _('Log de requête')
        verbose_name_plural = _('Logs de requêtes')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['method', 'timestamp']),
            models.Index(fields=['status_code', 'timestamp']),
            models.Index(fields=['is_slow', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.method} {self.path} - {self.status_code} - {self.timestamp}"


class ErrorLog(models.Model):
    """Log des erreurs"""

    class SeverityLevel(models.TextChoices):
        DEBUG = 'DEBUG', _('Debug')
        INFO = 'INFO', _('Information')
        WARNING = 'WARNING', _('Avertissement')
        ERROR = 'ERROR', _('Erreur')
        CRITICAL = 'CRITICAL', _('Critique')

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    severity = models.CharField(max_length=10, choices=SeverityLevel.choices, default='ERROR')
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    exception_type = models.CharField(max_length=200)
    exception_message = models.TextField()
    traceback = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('Log d\'erreur')
        verbose_name_plural = _('Logs d\'erreurs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['exception_type', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.severity}: {self.exception_type} - {self.timestamp}"


class SecurityEvent(models.Model):
    """Événements de sécurité"""

    class EventType(models.TextChoices):
        LOGIN_ATTEMPT = 'LOGIN_ATTEMPT', _('Tentative de connexion')
        LOGIN_SUCCESS = 'LOGIN_SUCCESS', _('Connexion réussie')
        LOGIN_FAILED = 'LOGIN_FAILED', _('Échec de connexion')
        PASSWORD_CHANGE = 'PASSWORD_CHANGE', _('Changement de mot de passe')
        TWO_FACTOR_ENABLED = '2FA_ENABLED', _('2FA activée')
        TWO_FACTOR_DISABLED = '2FA_DISABLED', _('2FA désactivée')
        IP_BLACKLISTED = 'IP_BLACKLISTED', _('IP blacklistée')
        SQL_INJECTION = 'SQL_INJECTION', _('Tentative injection SQL')
        XSS_ATTEMPT = 'XSS_ATTEMPT', _('Tentative XSS')
        BRUTEFORCE = 'BRUTEFORCE', _('Attaque par force brute')
        SUSPICIOUS_ACTIVITY = 'SUSPICIOUS_ACTIVITY', _('Activité suspecte')

    class SeverityLevel(models.TextChoices):
        LOW = 'LOW', _('Faible')
        MEDIUM = 'MEDIUM', _('Moyen')
        HIGH = 'HIGH', _('Élevé')
        CRITICAL = 'CRITICAL', _('Critique')

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    severity = models.CharField(max_length=10, choices=SeverityLevel.choices, default='MEDIUM')
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_security_events'
    )
    resolution_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Événement de sécurité')
        verbose_name_plural = _('Événements de sécurité')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['resolved', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.ip_address} - {self.timestamp}"


class RateLimitEvent(models.Model):
    """Événements de rate limiting"""

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    identifier = models.CharField(max_length=200)  # IP ou user:ip
    ip_address = models.GenericIPAddressField()
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    path = models.CharField(max_length=500)
    limit = models.IntegerField()  # Nombre maximum de requêtes
    period = models.IntegerField()  # Période en secondes
    count = models.IntegerField()  # Nombre de requêtes au moment du dépassement
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = _('Événement de rate limiting')
        verbose_name_plural = _('Événements de rate limiting')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['identifier', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['path', 'timestamp']),
        ]

    def __str__(self):
        return f"Rate limit exceeded: {self.identifier} on {self.path}"


class BlacklistedIP(models.Model):
    """IPs blacklistées"""

    class BlockReason(models.TextChoices):
        BRUTEFORCE = 'BRUTEFORCE', _('Force brute')
        SQL_INJECTION = 'SQL_INJECTION', _('Injection SQL')
        XSS = 'XSS', _('XSS')
        SPAM = 'SPAM', _('Spam')
        FRAUD = 'FRAUD', _('Fraude')
        ABUSE = 'ABUSE', _('Abus')
        OTHER = 'OTHER', _('Autre')

    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.CharField(max_length=20, choices=BlockReason.choices)
    description = models.TextField(blank=True)
    blocked_at = models.DateTimeField(auto_now_add=True)
    blocked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_permanent = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('IP blacklistée')
        verbose_name_plural = _('IPs blacklistées')
        ordering = ['-blocked_at']
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['reason', 'blocked_at']),
            models.Index(fields=['is_permanent', 'blocked_at']),
        ]

    def __str__(self):
        return f"{self.ip_address} - {self.reason}"
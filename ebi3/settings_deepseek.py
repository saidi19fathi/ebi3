"""
Configuration spécifique pour le module de traduction DeepSeek.
À importer dans settings.py principal.
"""
import os
from datetime import timedelta
from celery.schedules import crontab

# ============================================================================
# CONFIGURATION DEEPSEEK TRANSLATION
# ============================================================================

# Clé API DeepSeek (à définir dans les variables d'environnement)
DEEPSEEK_API_KEY = os.environ.get('sk-4f4d359edced46c9b28c5e3e9532b943', '')

# Configuration du module de traduction
DEEPSEEK_CONFIG = {
    'API_KEY': DEEPSEEK_API_KEY,
    'ENABLED_LANGUAGES': ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'ru', 'zh', 'tr', 'nl'],
    'AUTO_TRANSLATE_FIELDS': ['title', 'description', 'content', 'body', 'message', 'comment'],
    'BATCH_SIZE': 5,
    'RETRY_ATTEMPTS': 3,
    'QUALITY_THRESHOLD': 0.7,
    'RATE_LIMIT_PER_MINUTE': 60,
    'API_URL': 'https://api.deepseek.com/v1/chat/completions',
    'MODEL': 'deepseek-chat',
    'TIMEOUT': 30,
    'TEMPERATURE': 0.1,
    'MAX_TOKENS': 4000,
}

# Cache Redis pour les traductions (configuration optionnelle)
TRANSLATION_CACHE_CONFIG = {
    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
    'TIMEOUT': 86400,  # 24 heures
    'KEY_PREFIX': 'translations',
}

# Configuration Celery pour les tâches asynchrones de traduction
TRANSLATION_CELERY_BEAT_SCHEDULE = {
    # Tâches de nettoyage des traductions
    'cleanup-old-translation-jobs': {
        'task': 'translations.tasks.cleanup_old_jobs',
        'schedule': crontab(hour=3, minute=0),  # 3h00 chaque jour
        'args': (30,),  # Supprime les jobs de plus de 30 jours
    },
    'retry-failed-translation-jobs': {
        'task': 'translations.tasks.retry_failed_jobs',
        'schedule': crontab(hour='*/2', minute=30),  # Toutes les 2h30
    },
    'update-translation-cache': {
        'task': 'translations.tasks.update_translation_cache',
        'schedule': crontab(hour=4, minute=0),  # 4h00 chaque jour
    },
    # Statistiques quotidiennes
    'generate-translation-stats': {
        'task': 'translations.tasks.generate_daily_stats',
        'schedule': crontab(hour=5, minute=0),  # 5h00 chaque jour
    },
}

# Middleware pour la traduction
TRANSLATION_MIDDLEWARE = [
    'translations.middleware.LanguageDetectionMiddleware',
    'translations.middleware.TranslationPreferencesMiddleware',
]

# Applications pour la traduction
TRANSLATION_APPS = [
    'translations',
]

# Configuration des langues supportées
TRANSLATION_LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
    ('ar', 'العربية'),
    ('es', 'Español'),
    ('de', 'Deutsch'),
    ('it', 'Italiano'),
    ('pt', 'Português'),
    ('ru', 'Русский'),
    ('zh', '中文'),
    ('tr', 'Türkçe'),
    ('nl', 'Nederlands'),
]

# Paramètres de sécurité pour les données de traduction
TRANSLATION_SECURITY = {
    'DATA_RETENTION_DAYS': 365,  # Conservation des données
    'MAX_TEXT_LENGTH': 10000,  # Longueur max par texte
    'DAILY_LIMIT_PER_USER': 100,  # Limite quotidienne par utilisateur
    'MAX_BATCH_SIZE': 50,  # Taille max des batchs
    'ALLOW_USER_DISABLE': True,  # Autoriser la désactivation par utilisateur
}

# Configuration du monitoring
TRANSLATION_MONITORING = {
    'ENABLE_LOGGING': True,
    'LOG_LEVEL': 'INFO',
    'ENABLE_METRICS': True,
    'METRICS_PORT': 9090,  # Port pour les métriques Prometheus (optionnel)
    'ALERT_THRESHOLDS': {
        'ERROR_RATE': 0.05,  # 5% d'erreurs max
        'AVG_RESPONSE_TIME': 2.0,  # 2 secondes max
        'CACHE_HIT_RATIO': 0.3,  # 30% de cache hit minimum
    },
}

# Configuration de l'interface utilisateur
TRANSLATION_UI = {
    'SHOW_TRANSLATION_BADGE': True,
    'ALLOW_MANUAL_TRANSLATION': True,
    'ALLOW_TRANSLATION_EDITING': True,
    'SHOW_LANGUAGE_SELECTOR': True,
    'DEFAULT_VIEW_MODE': 'auto',  # 'auto', 'original', 'translated'
    'ENABLE_PREVIEW': True,
    'PREVIEW_CHAR_LIMIT': 500,
}

# Configuration des webhooks (optionnel)
TRANSLATION_WEBHOOKS = {
    'ENABLE': False,
    'URL': os.environ.get('TRANSLATION_WEBHOOK_URL', ''),
    'SECRET': os.environ.get('TRANSLATION_WEBHOOK_SECRET', ''),
    'EVENTS': ['translation.completed', 'translation.failed', 'job.completed'],
}

# Configuration du fallback
TRANSLATION_FALLBACK = {
    'ENABLE': True,
    'STRATEGY': 'original',  # 'original', 'cached', 'similar'
    'MIN_CONFIDENCE': 0.5,
    'MAX_ATTEMPTS': 2,
}

# Configuration du coût et du budget
TRANSLATION_BUDGET = {
    'MONTHLY_LIMIT': 100.00,  # $100 par mois
    'COST_PER_CHARACTER': 0.000002,  # Coût approximatif par caractère
    'ALERT_THRESHOLD': 0.8,  # Alerte à 80% du budget
    'ENABLE_LIMITS': True,
}

# URLs des traductions
TRANSLATION_URLS = {
    'API_PREFIX': 'api/translations/',
    'ADMIN_PREFIX': 'admin/translations/',
    'USER_PREFIX': 'translations/',
}

# Feature flags (activation progressive des fonctionnalités)
TRANSLATION_FEATURE_FLAGS = {
    'ENABLE_REAL_TIME_UPDATES': False,  # WebSockets/SSE
    'ENABLE_BATCH_PROCESSING': True,
    'ENABLE_MEMORY_CACHE': True,
    'ENABLE_QUALITY_SCORING': True,
    'ENABLE_USER_PREFERENCES': True,
    'ENABLE_ADMIN_DASHBOARD': True,
}
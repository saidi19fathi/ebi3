"""
Modèles pour le système de traduction automatique multilingue.
Stocke les traductions pour tout contenu textuel de l'application.
"""
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils.translation import get_language_info
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey

class TranslationMemory(models.Model):
    """
    Mémoire de traduction pour stocker les paires source-traduction
    et réutiliser les traductions fréquentes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_text_hash = models.CharField(max_length=64, db_index=True)
    source_language = models.CharField(max_length=10)
    target_language = models.CharField(max_length=10)
    translated_text = models.TextField()
    usage_count = models.PositiveIntegerField(default=0)
    confidence_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'translation_memory'
        unique_together = ['source_text_hash', 'source_language', 'target_language']
        indexes = [
            models.Index(fields=['source_text_hash']),
            models.Index(fields=['source_language', 'target_language']),
        ]
        verbose_name = 'Mémoire de traduction'
        verbose_name_plural = 'Mémoires de traduction'

    def __str__(self):
        return f"{self.source_language} → {self.target_language} ({self.usage_count})"


class TranslationJob(models.Model):
    """
    Suivi des travaux de traduction pour chaque contenu.
    """
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('partial', 'Partiel'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey('content_type', 'object_id')

    source_language = models.CharField(max_length=10)
    field_name = models.CharField(max_length=100)  # Nom du champ à traduire
    original_text = models.TextField()

    # Métadonnées de traitement
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    target_languages = models.JSONField(default=list)  # Liste des langues cibles
    completed_languages = models.JSONField(default=list)  # Langues terminées
    failed_languages = models.JSONField(default=list)  # Langues échouées

    # Métriques
    total_characters = models.PositiveIntegerField(default=0)
    api_calls_count = models.PositiveIntegerField(default=0)
    processing_time = models.FloatField(null=True, blank=True)  # en secondes

    # Retry management
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Erreurs
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'translation_jobs'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['content_type', 'object_id', 'field_name']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Travail de traduction'
        verbose_name_plural = 'Travaux de traduction'

    def __str__(self):
        return f"Traduction {self.field_name} - {self.get_status_display()}"

    @property
    def progress_percentage(self):
        if not self.target_languages:
            return 0
        total = len(self.target_languages)
        completed = len(self.completed_languages)
        return int((completed / total) * 100) if total > 0 else 0

    def mark_as_processing(self):
        self.status = 'processing'
        self.started_at = models.DateTimeField(auto_now=True)
        self.save(update_fields=['status', 'started_at'])

    def mark_as_completed(self):
        self.status = 'completed'
        self.completed_at = models.DateTimeField(auto_now=True)
        self.save(update_fields=['status', 'completed_at'])

    def add_completed_language(self, language_code):
        if language_code not in self.completed_languages:
            self.completed_languages.append(language_code)
            self.save(update_fields=['completed_languages'])

    def add_failed_language(self, language_code, error=None):
        if language_code not in self.failed_languages:
            self.failed_languages.append(language_code)
            if error:
                self.error_message = str(error)[:500]
            self.save(update_fields=['failed_languages', 'error_message'])


class Translation(models.Model):
    """
    Stockage des traductions pour chaque langue.
    """
    QUALITY_CHOICES = [
        ('auto', 'Automatique'),
        ('human', 'Humaine'),
        ('edited', 'Éditée'),
        ('reviewed', 'Révisée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Référence au contenu original
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Informations de traduction
    field_name = models.CharField(max_length=100)  # Champ traduit
    language = models.CharField(max_length=10)  # Code langue cible
    translated_text = models.TextField()

    # Métadonnées
    source_text = models.TextField()  # Texte original pour référence
    source_language = models.CharField(max_length=10)
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default='auto')
    confidence_score = models.FloatField(null=True, blank=True)

    # Référence au travail de traduction
    translation_job = models.ForeignKey(
        TranslationJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='translations'
    )

    # Versioning
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_translations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_translations'
    )
    last_edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'translations'
        unique_together = ['content_type', 'object_id', 'field_name', 'language', 'version']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'field_name', 'language', 'is_current']),
            models.Index(fields=['language', 'is_current']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Traduction'
        verbose_name_plural = 'Traductions'

    def __str__(self):
        return f"{self.field_name} ({self.language})"

    def save(self, *args, **kwargs):
        # Si c'est une nouvelle version, marquer l'ancienne comme non courante
        if self.pk:
            old = Translation.objects.get(pk=self.pk)
            if old.translated_text != self.translated_text:
                self.version = old.version + 1
                Translation.objects.filter(
                    content_type=self.content_type,
                    object_id=self.object_id,
                    field_name=self.field_name,
                    language=self.language,
                    is_current=True
                ).update(is_current=False)
                self.is_current = True
        super().save(*args, **kwargs)

    @property
    def language_name(self):
        try:
            return get_language_info(self.language)['name_translated']
        except:
            return self.language


class TranslationSettings(models.Model):
    """
    Paramètres de traduction globaux et par utilisateur.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        unique=True,
        verbose_name="Utilisateur"
    )

    # Paramètres globaux (user=None) ou par utilisateur
    auto_translate_enabled = models.BooleanField(default=True, verbose_name="Traduction automatique activée")
    preferred_languages = models.JSONField(
        default=list,
        verbose_name="Langues préférées",
        help_text="Liste des codes de langue par ordre de préférence"
    )

    # Options d'affichage
    show_translation_badge = models.BooleanField(
        default=True,
        verbose_name="Afficher le badge 'Traduit automatiquement'"
    )
    allow_translation_editing = models.BooleanField(
        default=True,
        verbose_name="Autoriser l'édition des traductions"
    )

    # Paramètres de qualité
    quality_threshold = models.FloatField(
        default=0.7,
        verbose_name="Seuil de qualité minimum",
        help_text="Score de confiance minimum pour accepter une traduction automatique"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'translation_settings'
        verbose_name = 'Paramètre de traduction'
        verbose_name_plural = 'Paramètres de traduction'

    def __str__(self):
        if self.user:
            return f"Paramètres traduction - {self.user.username}"
        return "Paramètres traduction globaux"


class APILog(models.Model):
    """
    Journal des appels API pour le monitoring et le debugging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.CharField(max_length=255)
    source_language = models.CharField(max_length=10)
    target_language = models.CharField(max_length=10)
    character_count = models.PositiveIntegerField()
    success = models.BooleanField()
    response_time = models.FloatField()  # en secondes
    status_code = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'translation_api_logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['success']),
            models.Index(fields=['source_language', 'target_language']),
        ]
        verbose_name = 'Log API'
        verbose_name_plural = 'Logs API'

    def __str__(self):
        status = "OK" if self.success else "ÉCHEC"
        return f"{self.endpoint} - {status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
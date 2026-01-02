from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg, Q
from datetime import datetime, timedelta
from django.utils import timezone

from .models import (
    TranslationMemory, TranslationJob, Translation,
    TranslationSettings, APILog
)

# Essayer d'importer humanize, mais continuer sans si non disponible
try:
    import humanize
    HUMANIZE_AVAILABLE = True
except ImportError:
    HUMANIZE_AVAILABLE = False
    print("Module 'humanize' non installé. L'installation est recommandée: pip install humanize")


@admin.register(TranslationMemory)
class TranslationMemoryAdmin(admin.ModelAdmin):
    list_display = (
        'source_language', 'target_language',
        'translated_text_preview', 'usage_count',
        'confidence_score_display', 'created_at'
    )
    list_filter = ('source_language', 'target_language', 'created_at')
    search_fields = ('translated_text', 'source_text_hash')
    readonly_fields = ('source_text_hash', 'usage_count', 'created_at', 'updated_at')

    def translated_text_preview(self, obj):
        if len(obj.translated_text) > 50:
            return f"{obj.translated_text[:50]}..."
        return obj.translated_text
    translated_text_preview.short_description = _('Texte traduit')

    def confidence_score_display(self, obj):
        if obj.confidence_score:
            return f"{obj.confidence_score:.2%}"
        return "-"
    confidence_score_display.short_description = _('Confiance')


@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    list_display = (
        'content_object_link', 'field_name',
        'source_language', 'status_display',
        'progress_bar', 'total_characters',
        'created_at_display'
    )
    list_filter = ('status', 'source_language', 'created_at', 'content_type')
    search_fields = ('original_text', 'field_name', 'object_id')
    readonly_fields = (
        'content_type', 'object_id', 'original_text',
        'source_language', 'total_characters',
        'created_at', 'started_at', 'completed_at',
        'progress_percentage', 'target_languages_display',
        'completed_languages_display', 'failed_languages_display'
    )
    actions = ['retry_failed_jobs', 'cancel_jobs']

    def content_object_link(self, obj):
        if obj.content_object:
            app_label = obj.content_type.app_label
            model_name = obj.content_type.model
            try:
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.object_id])
                return format_html('<a href="{}">{}</a>', url, str(obj.content_object)[:50])
            except:
                return str(obj.content_object)[:50]
        return f"{obj.content_type} - {obj.object_id}"
    content_object_link.short_description = _('Contenu')

    def status_display(self, obj):
        colors = {
            'pending': 'gray',
            'processing': 'orange',
            'completed': 'green',
            'failed': 'red',
            'partial': 'yellow',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = _('Statut')

    def progress_bar(self, obj):
        percentage = obj.progress_percentage
        color = 'green' if percentage == 100 else 'orange' if percentage > 0 else 'gray'
        return format_html(
            '<div style="width: 100px; background: #eee; border-radius: 3px;">'
            '<div style="width: {}px; height: 20px; background: {}; border-radius: 3px; text-align: center; color: white; line-height: 20px;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    progress_bar.short_description = _('Progression')

    def created_at_display(self, obj):
        now = timezone.now()
        delta = now - obj.created_at
        if delta < timedelta(minutes=1):
            return _("À l'instant")
        elif delta < timedelta(hours=1):
            return _("Il y a {} minutes").format(delta.seconds // 60)
        elif delta < timedelta(days=1):
            return _("Il y a {} heures").format(delta.seconds // 3600)
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_display.short_description = _('Créé')

    def target_languages_display(self, obj):
        return ", ".join(obj.target_languages) if obj.target_languages else "-"
    target_languages_display.short_description = _('Langues cibles')

    def completed_languages_display(self, obj):
        return ", ".join(obj.completed_languages) if obj.completed_languages else "-"
    completed_languages_display.short_description = _('Langues terminées')

    def failed_languages_display(self, obj):
        return ", ".join(obj.failed_languages) if obj.failed_languages else "-"
    failed_languages_display.short_description = _('Langues échouées')

    def retry_failed_jobs(self, request, queryset):
        count = 0
        for job in queryset.filter(status__in=['failed', 'partial']):
            job.status = 'pending'
            job.retry_count = 0
            job.error_message = ''
            job.save()
            count += 1
        self.message_user(request, f"{count} travaux relancés.")
    retry_failed_jobs.short_description = _('Relancer les travaux échoués')

    def cancel_jobs(self, request, queryset):
        count = queryset.update(status='failed', error_message='Annulé par administrateur')
        self.message_user(request, f"{count} travaux annulés.")
    cancel_jobs.short_description = _('Annuler les travaux sélectionnés')


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = (
        'content_object_link', 'field_name',
        'language_display', 'quality_display',
        'translated_text_preview', 'confidence_score_display',
        'is_current_display', 'created_at'
    )
    list_filter = ('language', 'quality', 'is_current', 'created_at', 'content_type')
    search_fields = ('translated_text', 'source_text', 'field_name', 'object_id')
    readonly_fields = (
        'content_type', 'object_id', 'source_text',
        'source_language', 'version', 'created_at', 'updated_at'
    )

    def content_object_link(self, obj):
        if obj.content_object:
            app_label = obj.content_type.app_label
            model_name = obj.content_type.model
            try:
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.object_id])
                return format_html('<a href="{}">{}</a>', url, str(obj.content_object)[:50])
            except:
                return str(obj.content_object)[:50]
        return f"{obj.content_type} - {obj.object_id}"
    content_object_link.short_description = _('Contenu')

    def language_display(self, obj):
        from django.utils.translation import get_language_info
        try:
            return get_language_info(obj.language)['name_translated']
        except:
            return obj.language
    language_display.short_description = _('Langue')

    def quality_display(self, obj):
        colors = {
            'auto': 'gray',
            'human': 'green',
            'edited': 'blue',
            'reviewed': 'purple',
        }
        color = colors.get(obj.quality, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_quality_display()
        )
    quality_display.short_description = _('Qualité')

    def translated_text_preview(self, obj):
        if len(obj.translated_text) > 60:
            return f"{obj.translated_text[:60]}..."
        return obj.translated_text
    translated_text_preview.short_description = _('Texte traduit')

    def confidence_score_display(self, obj):
        if obj.confidence_score:
            return f"{obj.confidence_score:.2%}"
        return "-"
    confidence_score_display.short_description = _('Confiance')

    def is_current_display(self, obj):
        if obj.is_current:
            return format_html('<span style="color: green; font-weight: bold;">✓</span>')
        return format_html('<span style="color: gray;">✗</span>')
    is_current_display.short_description = _('Courant')


@admin.register(TranslationSettings)
class TranslationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user_display', 'auto_translate_enabled', 'show_translation_badge', 'updated_at')
    list_filter = ('auto_translate_enabled', 'show_translation_badge')
    search_fields = ('user__username', 'user__email')

    def user_display(self, obj):
        if obj.user:
            return obj.user.username
        return _("Paramètres globaux")
    user_display.short_description = _('Utilisateur')


@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    list_display = (
        'endpoint', 'source_language', 'target_language',
        'character_count', 'success_display', 'response_time_display',
        'cost_display', 'created_at'
    )
    list_filter = ('success', 'source_language', 'target_language', 'created_at')
    search_fields = ('endpoint', 'error_message')
    readonly_fields = ('created_at',)

    def success_display(self, obj):
        if obj.success:
            return format_html('<span style="color: green; font-weight: bold;">✓ SUCCÈS</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ ÉCHEC</span>')
    success_display.short_description = _('Statut')

    def response_time_display(self, obj):
        if obj.response_time < 1:
            return f"{obj.response_time*1000:.0f}ms"
        return f"{obj.response_time:.2f}s"
    response_time_display.short_description = _('Temps réponse')

    def cost_display(self, obj):
        if obj.cost_estimate:
            return f"${obj.cost_estimate:.6f}"
        return "-"
    cost_display.short_description = _('Coût estimé')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# Dashboard personnalisé pour les traductions
class TranslationDashboard(admin.AdminSite):
    site_header = "Tableau de bord des traductions"
    site_title = "Dashboard Traductions"
    index_title = "Statistiques des traductions"

    def index(self, request, extra_context=None):
        from django.db.models import Count, Avg
        from datetime import timedelta

        # Statistiques de base
        stats = {
            'total_translations': Translation.objects.count(),
            'total_jobs': TranslationJob.objects.count(),
            'active_jobs': TranslationJob.objects.filter(status='processing').count(),
            'failed_jobs': TranslationJob.objects.filter(status='failed').count(),
        }

        # Distribution par langue
        lang_dist = Translation.objects.values('language').annotate(
            count=Count('id')
        ).order_by('-count')

        # Performance API (dernières 24h)
        last_24h = timezone.now() - timedelta(hours=24)
        api_stats = APILog.objects.filter(
            created_at__gte=last_24h
        ).aggregate(
            avg_response=Avg('response_time'),
            success_rate=Avg('success') * 100
        )

        extra_context = {
            'stats': stats,
            'lang_dist': lang_dist,
            'api_stats': api_stats,
            'recent_jobs': TranslationJob.objects.order_by('-created_at')[:10],
            'recent_errors': APILog.objects.filter(success=False).order_by('-created_at')[:10],
        }

        return super().index(request, extra_context)


# Enregistrement du dashboard
translation_dashboard = TranslationDashboard(name='translation_dashboard')
translation_dashboard.register(TranslationJob, TranslationJobAdmin)
translation_dashboard.register(Translation, TranslationAdmin)
translation_dashboard.register(APILog, APILogAdmin)
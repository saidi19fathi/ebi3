"""
Vues pour le module de traduction.
"""
import json
import logging
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from .models import Translation, TranslationJob, TranslationMemory, TranslationSettings, APILog
from .api import get_api_client, DeepSeekAPIError
from .forms import ManualTranslationForm, TranslationSettingsForm

logger = logging.getLogger(__name__)


# API Views
class TranslateAPIView(View):
    """API pour la traduction manuelle."""

    def post(self, request):
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            source_lang = data.get('source_language', 'auto')
            target_lang = data.get('target_language')

            if not text:
                return JsonResponse({'error': 'Texte requis'}, status=400)

            if not target_lang:
                return JsonResponse({'error': 'Langue cible requise'}, status=400)

            # Détection automatique de la langue
            if source_lang == 'auto':
                # Logique simplifiée - à améliorer
                source_lang = settings.LANGUAGE_CODE

            # Appel API
            api_client = get_api_client()
            result = api_client.translate_text(text, source_lang, target_lang)

            return JsonResponse({
                'success': True,
                'translated_text': result['translated_text'],
                'source_language': source_lang,
                'target_language': target_lang,
                'confidence_score': result.get('confidence_score'),
                'from_cache': result.get('from_cache', False),
            })

        except DeepSeekAPIError as e:
            logger.error(f"API Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return JsonResponse({'error': 'Erreur interne'}, status=500)


class TranslationJobListAPIView(LoginRequiredMixin, View):
    """API pour lister les travaux de traduction."""

    def get(self, request):
        try:
            jobs = TranslationJob.objects.all().order_by('-created_at')[:50]

            data = []
            for job in jobs:
                data.append({
                    'id': str(job.id),
                    'content_type': f"{job.content_type.app_label}.{job.content_type.model}",
                    'object_id': job.object_id,
                    'field_name': job.field_name,
                    'status': job.status,
                    'progress': job.progress_percentage,
                    'source_language': job.source_language,
                    'target_languages': job.target_languages,
                    'completed_languages': job.completed_languages,
                    'created_at': job.created_at.isoformat(),
                })

            return JsonResponse({'jobs': data})

        except Exception as e:
            logger.error(f"Error fetching jobs: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class TranslationJobDetailAPIView(LoginRequiredMixin, View):
    """API pour les détails d'un travail de traduction."""

    def get(self, request, pk):
        try:
            job = get_object_or_404(TranslationJob, pk=pk)

            # Récupère les traductions associées
            translations = job.translations.all()
            translations_data = []

            for trans in translations:
                translations_data.append({
                    'language': trans.language,
                    'translated_text': trans.translated_text[:200] + '...' if len(trans.translated_text) > 200 else trans.translated_text,
                    'quality': trans.quality,
                    'confidence_score': trans.confidence_score,
                    'created_at': trans.created_at.isoformat(),
                })

            data = {
                'id': str(job.id),
                'content_type': f"{job.content_type.app_label}.{job.content_type.model}",
                'object_id': job.object_id,
                'field_name': job.field_name,
                'original_text': job.original_text,
                'status': job.status,
                'progress': job.progress_percentage,
                'source_language': job.source_language,
                'target_languages': job.target_languages,
                'completed_languages': job.completed_languages,
                'failed_languages': job.failed_languages,
                'total_characters': job.total_characters,
                'api_calls_count': job.api_calls_count,
                'processing_time': job.processing_time.total_seconds() if job.processing_time else None,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'error_message': job.error_message,
                'translations': translations_data,
            }

            return JsonResponse(data)

        except Exception as e:
            logger.error(f"Error fetching job details: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class SupportedLanguagesAPIView(View):
    """API pour les langues supportées."""

    def get(self, request):
        try:
            api_client = get_api_client()
            languages = api_client.get_supported_languages()

            # Ajoute les noms des langues
            language_map = api_client.LANGUAGE_MAP
            languages_with_names = []

            for code in languages:
                languages_with_names.append({
                    'code': code,
                    'name': language_map.get(code, code.capitalize()),
                    'native_name': self._get_native_name(code),
                })

            return JsonResponse({'languages': languages_with_names})

        except Exception as e:
            logger.error(f"Error fetching languages: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def _get_native_name(self, language_code):
        """Retourne le nom natif de la langue."""
        # Mapping simplifié
        native_names = {
            'fr': 'Français',
            'en': 'English',
            'ar': 'العربية',
            'es': 'Español',
            'de': 'Deutsch',
            'it': 'Italiano',
            'pt': 'Português',
            'ru': 'Русский',
            'zh': '中文',
            'tr': 'Türkçe',
            'nl': 'Nederlands',
        }
        return native_names.get(language_code, language_code.capitalize())


class TranslationStatsAPIView(LoginRequiredMixin, View):
    """API pour les statistiques de traduction."""

    def get(self, request):
        try:
            # Période (par défaut: 30 derniers jours)
            days = int(request.GET.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)

            # Statistiques générales
            total_translations = Translation.objects.count()
            total_jobs = TranslationJob.objects.count()
            active_jobs = TranslationJob.objects.filter(status='processing').count()

            # Distribution par langue
            lang_dist = Translation.objects.values('language').annotate(
                count=Count('id')
            ).order_by('-count')

            # Performance API
            api_stats = APILog.objects.filter(
                created_at__gte=start_date
            ).aggregate(
                total_calls=Count('id'),
                success_rate=Avg('success', output_field=models.FloatField()) * 100,
                avg_response_time=Avg('response_time'),
                total_cost=Sum('cost_estimate'),
            )

            # Travaux par statut
            jobs_by_status = TranslationJob.objects.values('status').annotate(
                count=Count('id')
            )

            data = {
                'period': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': timezone.now().isoformat(),
                },
                'totals': {
                    'translations': total_translations,
                    'jobs': total_jobs,
                    'active_jobs': active_jobs,
                },
                'language_distribution': list(lang_dist),
                'api_performance': api_stats,
                'jobs_by_status': list(jobs_by_status),
            }

            return JsonResponse(data)

        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# Admin Views
class TranslationDashboardView(LoginRequiredMixin, TemplateView):
    """Tableau de bord d'administration."""
    template_name = 'translations/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        context['total_translations'] = Translation.objects.count()
        context['total_jobs'] = TranslationJob.objects.count()
        context['active_jobs'] = TranslationJob.objects.filter(status='processing').count()
        context['failed_jobs'] = TranslationJob.objects.filter(status='failed').count()

        # Distribution par langue
        context['language_distribution'] = Translation.objects.values(
            'language'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Derniers travaux
        context['recent_jobs'] = TranslationJob.objects.order_by('-created_at')[:10]

        # Performance API (24h)
        last_24h = timezone.now() - timedelta(hours=24)
        context['api_stats'] = APILog.objects.filter(
            created_at__gte=last_24h
        ).aggregate(
            total_calls=Count('id'),
            success_rate=Avg('success', output_field=models.FloatField()) * 100,
            avg_response_time=Avg('response_time'),
        )

        # Erreurs récentes
        context['recent_errors'] = APILog.objects.filter(
            success=False
        ).order_by('-created_at')[:10]

        return context


class TranslationJobListView(LoginRequiredMixin, ListView):
    """Liste des travaux de traduction."""
    model = TranslationJob
    template_name = 'translations/admin/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtres
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(field_name__icontains=search) |
                Q(original_text__icontains=search) |
                Q(object_id__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TranslationJob.STATUS_CHOICES
        return context


class TranslationJobDetailView(LoginRequiredMixin, DetailView):
    """Détail d'un travail de traduction."""
    model = TranslationJob
    template_name = 'translations/admin/job_detail.html'
    context_object_name = 'job'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['translations'] = self.object.translations.all()
        return context


class TranslationMemoryView(LoginRequiredMixin, ListView):
    """Mémoire de traduction."""
    model = TranslationMemory
    template_name = 'translations/admin/memory_list.html'
    context_object_name = 'memory_entries'
    paginate_by = 50
    ordering = ['-usage_count']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtres
        source_lang = self.request.GET.get('source_language')
        if source_lang:
            queryset = queryset.filter(source_language=source_lang)

        target_lang = self.request.GET.get('target_language')
        if target_lang:
            queryset = queryset.filter(target_language=target_lang)

        return queryset


class TranslationSettingsView(LoginRequiredMixin, FormView):
    """Paramètres de traduction."""
    template_name = 'translations/admin/settings.html'
    form_class = TranslationSettingsForm

    def get_initial(self):
        # Récupère les paramètres globaux
        settings_obj, _ = TranslationSettings.objects.get_or_create(user=None)
        return {
            'auto_translate_enabled': settings_obj.auto_translate_enabled,
            'show_translation_badge': settings_obj.show_translation_badge,
            'allow_translation_editing': settings_obj.allow_translation_editing,
            'preferred_languages': settings_obj.preferred_languages,
            'quality_threshold': settings_obj.quality_threshold,
        }

    def form_valid(self, form):
        # Sauvegarde les paramètres globaux
        settings_obj, _ = TranslationSettings.objects.get_or_create(user=None)
        for field in form.changed_data:
            setattr(settings_obj, field, form.cleaned_data[field])
        settings_obj.save()

        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class APILogsView(LoginRequiredMixin, ListView):
    """Logs API."""
    model = APILog
    template_name = 'translations/admin/api_logs.html'
    context_object_name = 'logs'
    paginate_by = 50
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtres
        success = self.request.GET.get('success')
        if success:
            queryset = queryset.filter(success=(success == 'true'))

        source_lang = self.request.GET.get('source_language')
        if source_lang:
            queryset = queryset.filter(source_language=source_lang)

        target_lang = self.request.GET.get('target_language')
        if target_lang:
            queryset = queryset.filter(target_language=target_lang)

        return queryset


# User Views
class UserPreferencesView(LoginRequiredMixin, FormView):
    """Préférences utilisateur."""
    template_name = 'translations/user/preferences.html'
    form_class = TranslationSettingsForm

    def get_initial(self):
        # Récupère les paramètres utilisateur
        settings_obj, _ = TranslationSettings.objects.get_or_create(user=self.request.user)
        return {
            'auto_translate_enabled': settings_obj.auto_translate_enabled,
            'show_translation_badge': settings_obj.show_translation_badge,
            'allow_translation_editing': settings_obj.allow_translation_editing,
            'preferred_languages': settings_obj.preferred_languages,
            'quality_threshold': settings_obj.quality_threshold,
        }

    def form_valid(self, form):
        # Sauvegarde les paramètres utilisateur
        settings_obj, _ = TranslationSettings.objects.get_or_create(user=self.request.user)
        for field in form.changed_data:
            setattr(settings_obj, field, form.cleaned_data[field])
        settings_obj.save()

        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class ManualTranslationView(LoginRequiredMixin, View):
    """Traduction manuelle."""

    def post(self, request):
        try:
            data = json.loads(request.body)
            content_type_id = data.get('content_type_id')
            object_id = data.get('object_id')
            field_name = data.get('field_name')

            if not all([content_type_id, object_id, field_name]):
                return JsonResponse({'error': 'Paramètres manquants'}, status=400)

            # Déclenche la traduction via signal
            from django.contrib.contenttypes.models import ContentType
            from .signals import translate_content_signal

            content_type = ContentType.objects.get_for_id(content_type_id)
            model_class = content_type.model_class()
            instance = model_class.objects.get(pk=object_id)

            # Envoie le signal
            translate_content_signal.send(
                sender=model_class,
                instance=instance,
                field_name=field_name
            )

            return JsonResponse({'success': True, 'message': 'Traduction lancée'})

        except Exception as e:
            logger.error(f"Manual translation error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class TranslationUpdatesView(View):
    """Endpoint pour les mises à jour en temps réel (SSE/WebSockets)."""

    def get(self, request):
        # Pour SSE (Server-Sent Events)
        response = HttpResponse(
            self.generate_events(request),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def generate_events(self, request):
        """Génère les événements SSE."""
        import time

        # Récupère le dernier ID d'événement
        last_id = request.GET.get('last_id', '0')

        # Boucle d'événements
        try:
            while True:
                # Vérifie les nouvelles traductions
                new_translations = Translation.objects.filter(
                    created_at__gt=timezone.now() - timedelta(seconds=5)
                )

                for translation in new_translations:
                    event_data = {
                        'type': 'translation_completed',
                        'id': str(translation.id),
                        'content_type': f"{translation.content_type.app_label}.{translation.content_type.model}",
                        'object_id': translation.object_id,
                        'field_name': translation.field_name,
                        'language': translation.language,
                        'timestamp': translation.created_at.isoformat(),
                    }

                    yield f"id: {translation.id}\n"
                    yield f"event: translation\n"
                    yield f"data: {json.dumps(event_data)}\n\n"

                # Vérifie les mises à jour des travaux
                updated_jobs = TranslationJob.objects.filter(
                    updated_at__gt=timezone.now() - timedelta(seconds=5)
                )

                for job in updated_jobs:
                    event_data = {
                        'type': 'job_updated',
                        'id': str(job.id),
                        'status': job.status,
                        'progress': job.progress_percentage,
                        'completed_languages': job.completed_languages,
                        'timestamp': job.updated_at.isoformat(),
                    }

                    yield f"id: {job.id}\n"
                    yield f"event: job\n"
                    yield f"data: {json.dumps(event_data)}\n\n"

                # Attente avant la prochaine vérification
                time.sleep(2)

        except GeneratorExit:
            # Client déconnecté
            pass
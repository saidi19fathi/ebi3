"""
URLs pour le module de traduction.
"""
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'translations'

urlpatterns = [
    # API endpoints
    path('api/', include([
        path('translate/', views.TranslateAPIView.as_view(), name='api_translate'),
        path('jobs/', views.TranslationJobListAPIView.as_view(), name='api_jobs'),
        path('jobs/<uuid:pk>/', views.TranslationJobDetailAPIView.as_view(), name='api_job_detail'),
        path('languages/', views.SupportedLanguagesAPIView.as_view(), name='api_languages'),
        path('stats/', views.TranslationStatsAPIView.as_view(), name='api_stats'),
    ])),

    # Vue d'administration des traductions
    path('admin/', include([
        path('dashboard/', login_required(views.TranslationDashboardView.as_view()), name='admin_dashboard'),
        path('jobs/', login_required(views.TranslationJobListView.as_view()), name='admin_jobs'),
        path('jobs/<uuid:pk>/', login_required(views.TranslationJobDetailView.as_view()), name='admin_job_detail'),
        path('memory/', login_required(views.TranslationMemoryView.as_view()), name='admin_memory'),
        path('settings/', login_required(views.TranslationSettingsView.as_view()), name='admin_settings'),
        path('logs/', login_required(views.APILogsView.as_view()), name='admin_logs'),
    ])),

    # Actions utilisateur
    path('preferences/', login_required(views.UserPreferencesView.as_view()), name='user_preferences'),
    path('translate-manual/', login_required(views.ManualTranslationView.as_view()), name='manual_translate'),

    # Webhook pour les mises à jour (si WebSockets/SSE)
    path('updates/', views.TranslationUpdatesView.as_view(), name='translation_updates'),
]
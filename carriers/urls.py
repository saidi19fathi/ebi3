# ~/ebi3/carriers/urls.py

from django.urls import path, include
from django.views.generic import TemplateView
from . import views

app_name = 'carriers'

urlpatterns = [
    # ============================================================================
    # PAGES PUBLIQUES
    # ============================================================================

    # Liste des transporteurs
    path('', views.CarrierListView.as_view(), name='carrier_list'),

    # Recherche avancée
    path('search/', views.CarrierSearchView.as_view(), name='search'),

    # ============================================================================
    # INSCRIPTION ET PROFIL TRANSPORTEUR (PLACÉS AVANT LES URLS GÉNÉRIQUES)
    # ============================================================================

    # Devenir transporteur
    path('apply/', views.CarrierApplyView.as_view(), name='apply'),
    path('apply/success/', TemplateView.as_view(template_name='carriers/apply_success.html'), name='apply_success'),

    # Documents et vérifications
    path('documents/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='document_delete'),
    path('verification/', views.VerificationStatusView.as_view(), name='verification_status'),

    # ============================================================================
    # PROFIL PUBLIC DES TRANSPORTEURS
    # ============================================================================

    # Détail d'un transporteur (doit être APRÈS les URLs spécifiques)
    path('<str:username>/', views.CarrierDetailView.as_view(), name='carrier_detail'),

    # Avis sur un transporteur
    path('<str:username>/reviews/', views.CarrierReviewsView.as_view(), name='carrier_reviews'),
    path('<str:username>/review/create/', views.ReviewCreateView.as_view(), name='create_review'),
    path('review/<int:pk>/update/', views.ReviewUpdateView.as_view(), name='update_review'),
    path('review/<int:pk>/delete/', views.ReviewDeleteView.as_view(), name='delete_review'),

    # ============================================================================
    # DASHBOARD TRANSPORTEUR (authentifié)
    # ============================================================================

    # Dashboard principal
    path('dashboard/', views.CarrierDashboardView.as_view(), name='carrier_dashboard'),

    # Gestion du profil
    path('dashboard/profile/', views.CarrierProfileUpdateView.as_view(), name='profile_update'),
    path('dashboard/profile/complete/', views.ProfileCompletionView.as_view(), name='profile_completion'),

    # Disponibilité
    path('dashboard/availability/', views.AvailabilityUpdateView.as_view(), name='availability_update'),
    path('dashboard/availability/toggle/', views.toggle_availability, name='toggle_availability'),

    # ============================================================================
    # NOUVELLE INTÉGRATION AVEC LOGISTICS
    # ============================================================================

    # Missions logistiques du transporteur
    path('<str:username>/missions/', views.CarrierMissionsView.as_view(), name='carrier_missions'),
    path('dashboard/missions/', views.CarrierMissionsDashboardView.as_view(), name='missions_dashboard'),
    path('dashboard/missions/active/', views.ActiveMissionsView.as_view(), name='active_missions'),
    path('dashboard/missions/completed/', views.CompletedMissionsView.as_view(), name='completed_missions'),
    path('dashboard/missions/<int:pk>/', views.MissionDetailView.as_view(), name='mission_detail'),

    # Routes du transporteur
    path('<str:username>/routes/', views.CarrierRoutesView.as_view(), name='carrier_routes'),
    path('dashboard/routes/', views.CarrierRoutesDashboardView.as_view(), name='routes_dashboard'),
    path('dashboard/routes/create/', views.RouteCreateView.as_view(), name='route_create'),
    path('dashboard/routes/<int:pk>/edit/', views.RouteUpdateView.as_view(), name='route_update'),
    path('dashboard/routes/<int:pk>/delete/', views.RouteDeleteView.as_view(), name='route_delete'),
    path('dashboard/routes/<int:pk>/toggle/', views.toggle_route_status, name='toggle_route_status'),

    # Propositions de transport
    path('<str:username>/proposals/', views.CarrierProposalsView.as_view(), name='carrier_proposals'),
    path('dashboard/proposals/', views.CarrierProposalsDashboardView.as_view(), name='proposals_dashboard'),
    path('dashboard/proposals/active/', views.ActiveProposalsView.as_view(), name='active_proposals'),
    path('dashboard/proposals/accepted/', views.AcceptedProposalsView.as_view(), name='accepted_proposals'),
    path('dashboard/proposals/expired/', views.ExpiredProposalsView.as_view(), name='expired_proposals'),

    # Dashboard logistique complet
    path('dashboard/logistics/', views.CarrierLogisticsDashboardView.as_view(), name='carrier_logistics_dashboard'),

    # Statistiques et rapports
    path('dashboard/statistics/', views.CarrierStatisticsView.as_view(), name='carrier_statistics'),
    path('dashboard/reports/', views.CarrierReportsView.as_view(), name='carrier_reports'),
    path('dashboard/earnings/', views.EarningsView.as_view(), name='earnings'),

    # ============================================================================
    # GESTION DES CAPACITÉS ET SERVICES
    # ============================================================================

    # Capacités
    path('dashboard/capacities/', views.CapacitiesUpdateView.as_view(), name='capacities_update'),

    # Services
    path('dashboard/services/', views.ServicesUpdateView.as_view(), name='services_update'),

    # Véhicules
    path('dashboard/vehicles/', views.VehiclesListView.as_view(), name='vehicles_list'),
    path('dashboard/vehicles/add/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('dashboard/vehicles/<int:pk>/edit/', views.VehicleUpdateView.as_view(), name='vehicle_update'),
    path('dashboard/vehicles/<int:pk>/delete/', views.VehicleDeleteView.as_view(), name='vehicle_delete'),

    # ============================================================================
    # GESTION DES DOCUMENTS ET ASSURANCES
    # ============================================================================

    # Documents
    path('dashboard/documents/', views.DocumentsListView.as_view(), name='documents_list'),
    path('dashboard/documents/add/', views.DocumentCreateView.as_view(), name='document_create'),

    # Assurances
    path('dashboard/insurance/', views.InsuranceInfoView.as_view(), name='insurance_info'),
    path('dashboard/insurance/update/', views.InsuranceUpdateView.as_view(), name='insurance_update'),

    # ============================================================================
    # COMMUNICATION ET NOTIFICATIONS
    # ============================================================================

    # Messagerie
    path('dashboard/messages/', views.CarrierMessagesView.as_view(), name='carrier_messages'),
    path('dashboard/messages/unread/', views.UnreadMessagesView.as_view(), name='unread_messages'),

    # Notifications
    path('dashboard/notifications/', views.CarrierNotificationsView.as_view(), name='carrier_notifications'),
    path('dashboard/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # ============================================================================
    # PARAMÈTRES ET CONFIGURATION
    # ============================================================================

    # Paramètres
    path('dashboard/settings/', views.CarrierSettingsView.as_view(), name='carrier_settings'),
    path('dashboard/settings/notifications/', views.NotificationSettingsView.as_view(), name='notification_settings'),
    path('dashboard/settings/privacy/', views.PrivacySettingsView.as_view(), name='privacy_settings'),

    # Sécurité
    path('dashboard/security/', views.SecuritySettingsView.as_view(), name='security_settings'),

    # ============================================================================
    # PAGES D'AIDE ET SUPPORT
    # ============================================================================

    # Aide et support
    path('help/', views.CarrierHelpView.as_view(), name='carrier_help'),
    path('faq/', views.CarrierFAQView.as_view(), name='carrier_faq'),
    path('guide/', views.CarrierGuideView.as_view(), name='carrier_guide'),
    path('contact-support/', views.ContactSupportView.as_view(), name='contact_support'),

    # Termes et conditions
    path('terms/', views.CarrierTermsView.as_view(), name='carrier_terms'),
    path('privacy/', views.CarrierPrivacyView.as_view(), name='carrier_privacy'),

    # ============================================================================
    # REDIRECTIONS ET PAGES SPÉCIALES
    # ============================================================================

    # Redirections
    path('profile/redirect/', views.profile_redirect, name='profile_redirect'),
    path('dashboard/redirect/', views.dashboard_redirect, name='dashboard_redirect'),

    # Pages spéciales
    path('become-carrier/', TemplateView.as_view(template_name='carriers/become_carrier.html'), name='become_carrier'),
    path('success-stories/', views.SuccessStoriesView.as_view(), name='success_stories'),
    path('testimonials/', views.TestimonialsView.as_view(), name='testimonials'),

    # ============================================================================
    # API ET WEBHOOKS (PLACÉS APRÈS LES URLs GÉNÉRIQUES)
    # ============================================================================

    # API pour applications mobiles
    path('api/v1/', include([
        path('profile/', views.CarrierProfileAPIView.as_view(), name='api_profile'),
        path('missions/', views.MissionsAPIView.as_view(), name='api_missions'),
        path('missions/<int:pk>/', views.MissionDetailAPIView.as_view(), name='api_mission_detail'),
        path('routes/', views.RoutesAPIView.as_view(), name='api_routes'),
        path('earnings/', views.EarningsAPIView.as_view(), name='api_earnings'),
        path('location/update/', views.UpdateLocationAPIView.as_view(), name='api_update_location'),
    ])),

    # Webhooks pour paiements et notifications externes
    path('webhooks/stripe/', views.StripeWebhookView.as_view(), name='stripe_webhook'),
    path('webhooks/tracking/', views.TrackingWebhookView.as_view(), name='tracking_webhook'),
]

# URLs conditionnelles pour le développement
import sys
if 'runserver' in sys.argv or 'test' in sys.argv:
    urlpatterns += [
        # URLs de test et développement
        path('test/dashboard/', views.TestDashboardView.as_view(), name='test_dashboard'),
        path('test/missions/', views.TestMissionsView.as_view(), name='test_missions'),
        path('test/routes/', views.TestRoutesView.as_view(), name='test_routes'),
        path('debug/statistics/', views.DebugStatisticsView.as_view(), name='debug_statistics'),
    ]

# Handler d'erreurs spécifiques aux transporteurs
handler404 = 'carriers.views.handler404'
handler500 = 'carriers.views.handler500'
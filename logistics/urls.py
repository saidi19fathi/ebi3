# ~/ebi3/logistics/urls.py

from django.urls import path, include
from django.views.generic import RedirectView
from . import views

app_name = 'logistics'

urlpatterns = [
    # Dashboard et page d'accueil
    path('', views.LogisticsDashboardView.as_view(), name='dashboard'),
    path('dashboard/', RedirectView.as_view(pattern_name='logistics:dashboard'), name='dashboard_redirect'),

    # Réservations
    path('reservations/', views.ReservationListView.as_view(), name='reservation_list'),
    path('reservations/create/<slug:slug>/', views.ReservationCreateView.as_view(), name='reservation_create'),
    path('reservations/create-with-route/<int:route_id>/', views.reservation_create_with_route, name='reservation_create_with_route'),
    path('reservations/<int:pk>/', views.ReservationDetailView.as_view(), name='reservation_detail'),
    path('reservations/<int:pk>/edit/', views.ReservationUpdateView.as_view(), name='reservation_update'),
    path('reservations/<int:pk>/cancel/', views.ReservationCancelView.as_view(), name='reservation_cancel'),
    path('reservations/<int:pk>/update-status/', views.ReservationStatusUpdateView.as_view(), name='reservation_update_status'),
    path('reservations/<int:pk>/quick-pay/', views.ReservationStatusUpdateView.as_view(), name='reservation_quick_pay'),  # Pour paiement rapide

    # Missions
    path('missions/', views.MissionListView.as_view(), name='mission_list'),
    path('missions/<int:pk>/', views.MissionDetailView.as_view(), name='mission_detail'),
    path('missions/<int:pk>/update/', views.MissionUpdateView.as_view(), name='mission_update'),
    path('missions/<int:mission_id>/tracking/', views.TrackingEventCreateView.as_view(), name='tracking_event_create'),

    # Routes
    path('routes/', views.RouteListView.as_view(), name='route_list'),
    path('routes/create/', views.RouteCreateView.as_view(), name='route_create'),
    path('routes/<int:pk>/', views.RouteDetailView.as_view(), name='route_detail'),
    path('routes/<int:pk>/edit/', views.RouteUpdateView.as_view(), name='route_update'),
    path('routes/<int:pk>/delete/', views.RouteDeleteView.as_view(), name='route_delete'),
    path('routes/<int:pk>/book/', views.RouteDetailView.as_view(), name='route_book'),  # POST seulement

    # Propositions de transport
    path('proposals/', views.MyProposalsListView.as_view(), name='proposal_list'),
    path('proposals/create/<slug:slug>/', views.TransportProposalCreateView.as_view(), name='proposal_create'),
    path('proposals/<int:pk>/', views.TransportProposalDetailView.as_view(), name='proposal_detail'),
    path('proposals/<int:pk>/respond/', views.TransportProposalRespondView.as_view(), name='proposal_respond'),
    path('proposals/<int:pk>/cancel/', views.cancel_proposal, name='proposal_cancel'),

    # API pour suivi en temps réel
    path('api/tracking/<int:pk>/', views.TrackingAPIView.as_view(), name='tracking_api'),
    path('api/update-location/<int:mission_id>/', views.update_location_api, name='update_location_api'),

    # Notifications
    path('notifications/', views.logistics_notifications, name='notifications'),

    # Administration et paramètres
    path('settings/', views.LogisticsSettingsView.as_view(), name='settings'),
    path('reports/', views.LogisticsReportsView.as_view(), name='reports'),

    # Pages d'information
    path('faq/', views.LogisticsFAQView.as_view(), name='faq'),
    path('guide/', views.LogisticsGuideView.as_view(), name='guide'),

    # API REST (pour développement futur)
    path('api/v1/', include([
        path('reservations/', views.ReservationListView.as_view(), name='api_reservation_list'),
        path('reservations/<int:pk>/', views.ReservationDetailView.as_view(), name='api_reservation_detail'),
        path('missions/', views.MissionListView.as_view(), name='api_mission_list'),
        path('missions/<int:pk>/', views.MissionDetailView.as_view(), name='api_mission_detail'),
        path('routes/', views.RouteListView.as_view(), name='api_route_list'),
        path('routes/<int:pk>/', views.RouteDetailView.as_view(), name='api_route_detail'),
    ])),
]

# URLs spécifiques pour les intégrations avec d'autres apps
integration_urls = [
    # Intégration avec ads - pour créer des réservations depuis les annonces
    path('ad/<slug:slug>/reserve/', views.ReservationCreateView.as_view(), name='ad_reserve'),

    # Intégration avec carriers - pour voir les missions d'un transporteur
    path('carrier/<str:username>/missions/', views.MissionListView.as_view(), name='carrier_missions'),

    # Intégration avec users - pour voir les réservations d'un utilisateur
    path('user/<str:username>/reservations/', views.ReservationListView.as_view(), name='user_reservations'),
]

urlpatterns += integration_urls

# URLs de debug/development (à désactiver en production)
debug_urls = [
    path('test/notifications/', views.logistics_notifications, name='test_notifications'),
    path('test/api/', views.TrackingAPIView.as_view(), name='test_api'),
]

# Ajouter les URLs de debug si en mode développement
import sys
if 'runserver' in sys.argv or 'test' in sys.argv:
    urlpatterns += debug_urls
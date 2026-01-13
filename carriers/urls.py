# ~/ebi3/carriers/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CarrierRegistrationView,
    carrier_dashboard,
    carrier_profile,
    mission_list,
    mission_detail,
    mission_accept,
    update_mission_status,
    upload_delivery_proof,
    collection_days,
    collection_day_detail,
    organize_collection,
    optimize_route,
    start_collection,
    financial_dashboard,
    expense_reports,
    expense_report_detail,
    documents_management,
    generate_customs_form,
    marketplace_offers,
    marketplace_search,
    notifications,
    mark_notification_read,
    CarrierListView,
    carrier_public_profile,
    leave_review,
    api_carrier_stats,
    api_collection_planning,
    api_mission_update_location
)

app_name = 'carriers'

urlpatterns = [
    # 1. INSCRIPTION (PRIORITAIRE - CORRIGÉ)
    path('register/', CarrierRegistrationView.as_view(
        template_name='carriers/registration/register.html'
    ), name='register'),

    # 2. SUCCÈS D'INSCRIPTION
    path('registration/success/', registration_success, name='registration_success'),

    # 3. AUTHENTIFICATION
    path('login/', auth_views.LoginView.as_view(
        template_name='carriers/registration/login.html',
        redirect_authenticated_user=True,
        next_page='carriers:dashboard'
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(
        next_page='core:home'
    ), name='logout'),

    # 4. DASHBOARD ET PROFIL
    path('dashboard/', carrier_dashboard, name='dashboard'),
    path('profile/', carrier_profile, name='profile'),

    # 5. MISSIONS
    path('missions/', mission_list, name='mission_list'),
    path('missions/<int:pk>/', mission_detail, name='mission_detail'),
    path('missions/<int:pk>/accept/', mission_accept, name='mission_accept'),
    path('missions/<int:pk>/update-status/', update_mission_status, name='update_mission_status'),
    path('missions/<int:pk>/delivery-proof/', upload_delivery_proof, name='upload_delivery_proof'),

    # 6. COLLECTES
    path('collection/days/', collection_days, name='collection_days'),
    path('collection/days/<int:pk>/', collection_day_detail, name='collection_day_detail'),
    path('collection/days/<int:pk>/organize/', organize_collection, name='organize_collection'),
    path('collection/days/<int:pk>/optimize/', optimize_route, name='optimize_route'),
    path('collection/days/<int:pk>/start/', start_collection, name='start_collection'),

    # 7. FINANCES
    path('financial/', financial_dashboard, name='financial_dashboard'),
    path('financial/reports/', expense_reports, name='expense_reports'),
    path('financial/reports/<int:pk>/', expense_report_detail, name='expense_report_detail'),

    # 8. DOCUMENTS
    path('documents/', documents_management, name='documents'),
    path('documents/customs/<int:document_id>/', generate_customs_form, name='generate_customs_form'),

    # 9. MARKETPLACE (OPTIONNEL - À ACTIVER PLUS TARD)
    path('marketplace/offers/', marketplace_offers, name='marketplace_offers'),
    # path('marketplace/search/', marketplace_search, name='marketplace_search'),

    # 10. NOTIFICATIONS
    path('notifications/', notifications, name='notifications'),
    path('notifications/<int:pk>/read/', mark_notification_read, name='mark_notification_read'),

    # 11. PROFILS PUBLICS
    path('list/', CarrierListView.as_view(), name='carrier_list'),
    path('<str:username>/', carrier_public_profile, name='public_profile'),
    path('<str:username>/review/', leave_review, name='leave_review'),

    # 12. API
    path('api/stats/', api_carrier_stats, name='api_stats'),
    path('api/collection/<int:day_id>/planning/', api_collection_planning, name='api_collection_planning'),
    path('api/mission/<int:mission_id>/location/', api_mission_update_location, name='api_mission_update_location'),
]
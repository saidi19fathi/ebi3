# ~/ebi3/colis/urls.py - VERSION COMPLÈTE CORRIGÉE
from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'colis'

urlpatterns = [
    # ============================================================================
    # PAGES ESSENTIELLES - ORDRE IMPORTANT !
    # ============================================================================

    # Accueil des colis
    path('', views.PackageListView.as_view(), name='package_list'),

    # Création - DOIT ÊTRE AVANT LES SLUGS !
    path('publier/', views.PackageCreateView.as_view(), name='package_create'),

    # Mes colis
    path('mes-colis/', views.MyPackagesListView.as_view(), name='my_packages'),

    # Mes favoris - URL MANQUANTE
    path('mes-favoris/', views.PackageFavoritesListView.as_view(), name='favorite_list'),
    path('send-contact-message/', views.send_contact_message, name='send_contact_message'),

    # Recherche
    path('recherche/', views.search_packages, name='search'),

    # Catégories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),

    # ============================================================================
    # OFFRES DE TRANSPORT
    # ============================================================================

    # Mes offres
    path('mes-offres/', views.MyTransportOffersListView.as_view(), name='my_offers'),

    # ============================================================================
    # TRANSPORTEUR
    # ============================================================================

    path('transporteur/colis-disponibles/', views.AvailablePackagesView.as_view(), name='available_packages'),
    path('transporteur/dashboard/', views.CarrierDashboardView.as_view(), name='carrier_dashboard'),

    # ============================================================================
    # COLIS SPÉCIFIQUES - APRÈS LES URLS FIXES !
    # ============================================================================

    # Détail d'un colis - LA DERNIÈRE ROUTE AVEC SLUG
    path('<slug:slug>/', views.PackageDetailView.as_view(), name='package_detail'),

    # Actions sur un colis
    path('<slug:slug>/modifier/', views.PackageUpdateView.as_view(), name='package_edit'),
    path('<slug:slug>/supprimer/', views.PackageDeleteView.as_view(), name='package_delete'),
    path('<slug:slug>/signaler/', views.PackageReportView.as_view(), name='package_report'),

    # Favoris pour un colis spécifique
    path('<slug:slug>/favori/', views.toggle_package_favorite, name='toggle_favorite'),

    # Offres pour un colis spécifique
    path('<slug:slug>/offre/creer/', views.TransportOfferCreateView.as_view(), name='offer_create'),

    # ============================================================================
    # ACTIONS SUR LES OFFRES
    # ============================================================================

    path('offres/<int:pk>/accepter/', views.accept_transport_offer, name='accept_offer'),
    path('offres/<int:pk>/rejeter/', views.reject_transport_offer, name='reject_offer'),
    path('offres/<int:pk>/annuler/', views.cancel_transport_offer, name='cancel_offer'),

    # ============================================================================
    # PAGES D'AIDE
    # ============================================================================

    path('comment-ca-marche/', TemplateView.as_view(template_name='colis/how_it_works.html'), name='how_it_works'),
    path('guide-des-prix/', TemplateView.as_view(template_name='colis/price_guide.html'), name='price_guide'),
    path('conseils-emballage/', TemplateView.as_view(template_name='colis/packaging_tips.html'), name='packaging_tips'),
    path('faq/', TemplateView.as_view(template_name='colis/faq.html'), name='faq'),
    path('conditions-generales/', TemplateView.as_view(template_name='colis/terms.html'), name='terms'),
    path('politique-de-confidentialite/', TemplateView.as_view(template_name='colis/privacy.html'), name='privacy'),

    # ============================================================================
    # API ET AJAX
    # ============================================================================

    path('api/categories/', views.get_categories_api, name='get_categories'),
]
# ~/ebi3/colis/urls.py
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.sitemaps.views import sitemap
from django.contrib.sitemaps import Sitemap
from . import views

app_name = 'colis'

# Classes de sitemap
class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return [
            'colis:how_it_works',
            'colis:price_guide',
            'colis:packaging_tips',
            'colis:faq',
            'colis:terms',
        ]

    def location(self, item):
        from django.urls import reverse
        return reverse(item)

class PackageSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        try:
            from .models import Package
            return Package.objects.filter(status=Package.Status.AVAILABLE).order_by('-created_at')
        except:
            return []

    def lastmod(self, obj):
        return obj.updated_at

class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        try:
            from .models import Category
            return Category.objects.filter(is_active=True)
        except:
            return []

class CarrierSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        try:
            from carriers.models import Carrier
            return Carrier.objects.filter(status='APPROVED', is_available=True)
        except:
            return []

class XMLIndexSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return []

    def lastmod(self, obj):
        return None

def get_active_sitemaps():
    return {
        'index': XMLIndexSitemap,
        'static': StaticSitemap,
        'packages': PackageSitemap,
        'categories': CategorySitemap,
        'carriers': CarrierSitemap,
    }

# Vue pour sitemap de nouvelles
class NewsSitemapView(TemplateView):
    template_name = 'colis/sitemaps/news_sitemap.xml'
    content_type = 'application/xml'

urlpatterns = [
    # ============================================================================
    # PAGES PUBLIQUES
    # ============================================================================

    # Accueil des colis
    path('', views.PackageListView.as_view(), name='package_list'),

    # Recherche avancée
    path('recherche/', views.search_packages, name='search'),
    path('resultats/', views.PackageListView.as_view(), name='search_results'),

    # Catégories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),

    # ============================================================================
    # COLIS SPÉCIFIQUES
    # ============================================================================

    # Détail d'un colis
    path('colis/<slug:slug>/', views.PackageDetailView.as_view(), name='package_detail'),

    # Actions sur un colis (authentification requise)
    path('colis/<slug:slug>/modifier/', views.PackageUpdateView.as_view(), name='package_edit'),
    path('colis/<slug:slug>/supprimer/', views.PackageDeleteView.as_view(), name='package_delete'),
    path('colis/<slug:slug>/signaler/', views.PackageReportView.as_view(), name='package_report'),

    # Favoris
    path('colis/<slug:slug>/favori/', views.toggle_package_favorite, name='toggle_favorite'),

    # ============================================================================
    # GESTION DES COLIS (UTILISATEUR)
    # ============================================================================

    # Création
    path('publier/', views.PackageCreateView.as_view(), name='package_create'),

    # Mes colis
    path('mes-colis/', views.MyPackagesListView.as_view(), name='my_packages'),
    path('mes-favoris/', views.PackageFavoritesListView.as_view(), name='favorite_list'),

    # Gestion avancée
    path('colis/<slug:slug>/gestion/', views.package_management, name='package_management'),
    path('statistiques/', views.PackageStatisticsView.as_view(), name='package_statistics'),

    # ============================================================================
    # OFFRES DE TRANSPORT
    # ============================================================================

    # Faire une offre
    path('colis/<slug:slug>/offre/creer/', views.TransportOfferCreateView.as_view(), name='offer_create'),

    # Mes offres
    path('mes-offres/', views.MyTransportOffersListView.as_view(), name='my_offers'),

    # Actions sur les offres
    path('offres/<int:pk>/accepter/', views.accept_transport_offer, name='accept_offer'),
    path('offres/<int:pk>/rejeter/', views.reject_transport_offer, name='reject_offer'),
    path('offres/<int:pk>/annuler/', views.cancel_transport_offer, name='cancel_offer'),

    # ============================================================================
    # ESPACE TRANSPORTEUR
    # ============================================================================

    # Colis disponibles
    path('transporteur/colis-disponibles/', views.AvailablePackagesView.as_view(), name='available_packages'),

    # Tableau de bord transporteur
    path('transporteur/dashboard/', views.CarrierDashboardView.as_view(), name='carrier_dashboard'),

    # Devis rapide
    path('transporteur/devis-rapide/', views.quick_quote, name='quick_quote'),

    # ============================================================================
    # API ET FONCTIONNALITÉS AJAX
    # ============================================================================

    # Mise à jour de statut
    path('api/colis/<slug:slug>/statut/<str:status>/', views.update_package_status, name='update_status'),

    # Statistiques
    path('api/colis/<slug:slug>/statistiques/', views.package_stats, name='package_stats'),

    # ============================================================================
    # PAGES D'AIDE ET INFORMATION
    # ============================================================================

    # Comment ça marche
    path('comment-ca-marche/', TemplateView.as_view(template_name='colis/how_it_works.html'), name='how_it_works'),

    # Guide des prix
    path('guide-des-prix/', TemplateView.as_view(template_name='colis/price_guide.html'), name='price_guide'),

    # Conseils d'emballage
    path('conseils-emballage/', TemplateView.as_view(template_name='colis/packaging_tips.html'), name='packaging_tips'),

    # FAQ
    path('faq/', TemplateView.as_view(template_name='colis/faq.html'), name='faq'),

    # Conditions générales
    path('conditions-generales/', TemplateView.as_view(template_name='colis/terms.html'), name='terms'),

    path('politique-de-confidentialite/', TemplateView.as_view(template_name='colis/privacy.html'), name='privacy'),

    # ============================================================================
    # REDIRECTIONS ET URLS ALIAS
    # ============================================================================

    # Alias pour compatibilité
    path('annonces/', views.PackageListView.as_view(), name='ads'),  # Compatibilité avec anciens liens
    path('demandes/', views.PackageListView.as_view(), name='requests'),

    # Redirection transporteur
    path('devenir-transporteur/', TemplateView.as_view(template_name='colis/become_carrier.html'), name='become_carrier'),

    # ============================================================================
    # PAGES SPÉCIALES
    # ============================================================================

    # Succès stories
    path('success-stories/', TemplateView.as_view(template_name='colis/success_stories.html'), name='success_stories'),

    # Témoignages
    path('temoignages/', TemplateView.as_view(template_name='colis/testimonials.html'), name='testimonials'),

    # Blog
    path('blog/', TemplateView.as_view(template_name='colis/blog.html'), name='blog'),
    path('blog/category/<slug:slug>/', TemplateView.as_view(template_name='colis/blog_category.html'), name='blog_category'),
    path('blog/article/<slug:slug>/', TemplateView.as_view(template_name='colis/blog_post.html'), name='blog_post'),

    # ============================================================================
    # SITEMAPS
    # ============================================================================

    path('sitemap.xml', sitemap, {'sitemaps': get_active_sitemaps()},
         name='django.contrib.sitemaps.views.sitemap'),

    # Sitemaps individuels
    path('sitemap_index.xml', sitemap,
         {'sitemaps': {'index': XMLIndexSitemap()}},
         name='colis_sitemap_index'),

    path('sitemap_static.xml', sitemap,
         {'sitemaps': {'static': StaticSitemap()}},
         name='colis_sitemap_static'),

    path('sitemap_packages.xml', sitemap,
         {'sitemaps': {'packages': PackageSitemap()}},
         name='colis_sitemap_packages'),

    path('sitemap_categories.xml', sitemap,
         {'sitemaps': {'categories': CategorySitemap()}},
         name='colis_sitemap_categories'),

    path('sitemap_carriers.xml', sitemap,
         {'sitemaps': {'carriers': CarrierSitemap()}},
         name='colis_sitemap_carriers'),

    # Sitemap pour Google News (si applicable)
    path('news-sitemap.xml', NewsSitemapView.as_view(),
         name='colis_news_sitemap'),
]

# ============================================================================
# URLS API (versionnée)
# ============================================================================

api_urlpatterns = [
    # Version 1 de l'API
    path('v1/', include([
        # Colis
        path('packages/', views.PackageListView.as_view(), name='api_package_list'),
        path('packages/<slug:slug>/', views.PackageDetailView.as_view(), name='api_package_detail'),

        # Offres
        path('offers/', views.MyTransportOffersListView.as_view(), name='api_offer_list'),
        path('offers/create/', views.TransportOfferCreateView.as_view(), name='api_offer_create'),

        # Utilisateur
        path('user/packages/', views.MyPackagesListView.as_view(), name='api_user_packages'),
        path('user/favorites/', views.PackageFavoritesListView.as_view(), name='api_user_favorites'),

        # Transporteur
        path('carrier/available-packages/', views.AvailablePackagesView.as_view(), name='api_available_packages'),
        path('carrier/dashboard/', views.CarrierDashboardView.as_view(), name='api_carrier_dashboard'),

        # Recherche
        path('search/', views.search_packages, name='api_search'),

        # Catégories
        path('categories/', views.CategoryListView.as_view(), name='api_category_list'),
        path('categories/<slug:slug>/', views.CategoryDetailView.as_view(), name='api_category_detail'),
    ])),
]

# Ajouter les URLs API au pattern principal
urlpatterns += [
    path('api/', include(api_urlpatterns)),
]

# ============================================================================
# URLS D'ADMINISTRATION (si besoin de personnalisation)
# ============================================================================

admin_urlpatterns = [
    # Statistiques admin
    path('admin-stats/', login_required(TemplateView.as_view(template_name='colis/admin_stats.html')),
         name='admin_stats'),

    # Export de données
    path('export/csv/', login_required(TemplateView.as_view(template_name='colis/export_csv.html')),
         name='export_csv'),

    # Modération
    path('moderation/reports/', login_required(TemplateView.as_view(template_name='colis/moderation_reports.html')),
         name='moderation_reports'),
]

# Ajouter les URLs admin (protégées par login_required)
urlpatterns += [
    path('admin-tools/', include((admin_urlpatterns, 'admin_tools'))),
]

# ============================================================================
# URLS MOBILES (pour applications natives)
# ============================================================================

mobile_urlpatterns = [
    # Authentification mobile
    path('auth/login/', TemplateView.as_view(template_name='colis/mobile/login.html'), name='mobile_login'),
    path('auth/register/', TemplateView.as_view(template_name='colis/mobile/register.html'), name='mobile_register'),

    # Dashboard mobile
    path('dashboard/', TemplateView.as_view(template_name='colis/mobile/dashboard.html'), name='mobile_dashboard'),

    # Scanner QR code
    path('scanner/', TemplateView.as_view(template_name='colis/mobile/scanner.html'), name='mobile_scanner'),

    # Notifications
    path('notifications/', TemplateView.as_view(template_name='colis/mobile/notifications.html'), name='mobile_notifications'),
]

# Ajouter les URLs mobiles
urlpatterns += [
    path('mobile/', include((mobile_urlpatterns, 'mobile'))),
]

# ============================================================================
# URLS DE TEST ET DÉVELOPPEMENT
# ============================================================================

# Ces URLs ne sont actives qu'en mode DEBUG
from django.conf import settings

if settings.DEBUG:
    debug_urlpatterns = [
        # Pages de test
        path('test/package-card/', TemplateView.as_view(template_name='colis/test/package_card.html'),
             name='test_package_card'),
        path('test/offer-card/', TemplateView.as_view(template_name='colis/test/offer_card.html'),
             name='test_offer_card'),
        path('test/search-filters/', TemplateView.as_view(template_name='colis/test/search_filters.html'),
             name='test_search_filters'),

        # Données de test
        path('test-data/generate/', TemplateView.as_view(template_name='colis/test/generate_data.html'),
             name='test_generate_data'),

        # Composants UI
        path('ui/components/', TemplateView.as_view(template_name='colis/test/ui_components.html'),
             name='ui_components'),
    ]

    urlpatterns += [
        path('test/', include((debug_urlpatterns, 'test'))),
    ]

# ============================================================================
# URLS DE WEBHOOKS ET INTÉGRATIONS EXTERNES
# ============================================================================

webhook_urlpatterns = [
    # Webhook Stripe (paiements)
    path('stripe/', TemplateView.as_view(template_name='colis/webhooks/stripe.html'), name='webhook_stripe'),

    # Webhook Google Maps (géocodage)
    path('google-maps/', TemplateView.as_view(template_name='colis/webhooks/google_maps.html'), name='webhook_google_maps'),

    # Webhook SendGrid (emails)
    path('sendgrid/', TemplateView.as_view(template_name='colis/webhooks/sendgrid.html'), name='webhook_sendgrid'),

    # Webhook Twilio (SMS)
    path('twilio/', TemplateView.as_view(template_name='colis/webhooks/twilio.html'), name='webhook_twilio'),
]

urlpatterns += [
    path('webhooks/', include((webhook_urlpatterns, 'webhooks'))),
]

# ============================================================================
# URLS DE GÉOLOCALISATION
# ============================================================================

geolocation_urlpatterns = [
    # Recherche par localisation
    path('near-me/', TemplateView.as_view(template_name='colis/geolocation/near_me.html'), name='near_me'),

    # Calcul d'itinéraire
    path('route/', TemplateView.as_view(template_name='colis/geolocation/route.html'), name='route_calculation'),

    # Carte interactive
    path('map/', TemplateView.as_view(template_name='colis/geolocation/map.html'), name='interactive_map'),
]

urlpatterns += [
    path('location/', include((geolocation_urlpatterns, 'geolocation'))),
]

# ============================================================================
# URLS DE SUIVI ET TRACKING
# ============================================================================

tracking_urlpatterns = [
    # Suivi de colis
    path('<str:tracking_number>/', TemplateView.as_view(template_name='colis/tracking/tracking.html'),
         name='track_package'),

    # Historique de suivi
    path('<str:tracking_number>/history/',
         TemplateView.as_view(template_name='colis/tracking/history.html'), name='tracking_history'),

    # Notifications de suivi
    path('<str:tracking_number>/notifications/',
         TemplateView.as_view(template_name='colis/tracking/notifications.html'), name='tracking_notifications'),
]

urlpatterns += [
    path('track/', include((tracking_urlpatterns, 'tracking'))),
]

# ============================================================================
# URLS DE COMPATIBILITÉ ET REDIRECTIONS
# ============================================================================

# Redirections pour l'ancienne structure d'URLs
from django.views.generic.base import RedirectView

legacy_redirects = [
    # Anciennes URLs vers nouvelles
    path('ads/', RedirectView.as_view(pattern_name='colis:package_list', permanent=True)),
    path('ads/<slug:slug>/', RedirectView.as_view(pattern_name='colis:package_detail', permanent=True)),
    path('demandes/', RedirectView.as_view(pattern_name='colis:package_list', permanent=True)),
    path('demandes/<slug:slug>/', RedirectView.as_view(pattern_name='colis:package_detail', permanent=True)),

    # URLs raccourcies
    path('p/<slug:slug>/', RedirectView.as_view(pattern_name='colis:package_detail', permanent=True)),
    path('c/<slug:slug>/', RedirectView.as_view(pattern_name='colis:package_detail', permanent=True)),
]

urlpatterns += legacy_redirects

# ============================================================================
# FEEDS RSS
# ============================================================================

from django.contrib.syndication.views import Feed
from .models import Package

class LatestPackagesFeed(Feed):
    title = "Derniers colis disponibles sur Ebi3"
    link = "/colis/"
    description = "Nouveaux colis disponibles pour transport"

    def items(self):
        try:
            return Package.objects.filter(status=Package.Status.AVAILABLE).order_by('-created_at')[:20]
        except:
            return []

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return f"{item.description[:200]}... - {item.pickup_city} → {item.delivery_city}"

    def item_link(self, item):
        return item.get_absolute_url()

urlpatterns += [
    path('feed/rss/', LatestPackagesFeed(), name='package_feed'),
]

# ============================================================================
# ERROR HANDLERS (si besoin de personnalisation)
# ============================================================================

handler404 = 'colis.views.custom_404'
handler500 = 'colis.views.custom_500'

# ============================================================================
# URLS DE MAINTENANCE
# ============================================================================

maintenance_urlpatterns = [
    # Page de maintenance
    path('maintenance/', TemplateView.as_view(template_name='colis/maintenance.html'), name='maintenance'),

    # Status de l'API
    path('status/', TemplateView.as_view(template_name='colis/status.html'), name='api_status'),

    # Health check
    path('health/', TemplateView.as_view(template_name='colis/health.html'), name='health_check'),
]

urlpatterns += [
    path('system/', include((maintenance_urlpatterns, 'system'))),
]

# ============================================================================
# URLS DE DÉMONSTRATION (pour présentation)
# ============================================================================

demo_urlpatterns = [
    # Démo complète
    path('demo/', TemplateView.as_view(template_name='colis/demo/full_demo.html'), name='full_demo'),

    # Démo expéditeur
    path('demo/sender/', TemplateView.as_view(template_name='colis/demo/sender_demo.html'), name='sender_demo'),

    # Démo transporteur
    path('demo/carrier/', TemplateView.as_view(template_name='colis/demo/carrier_demo.html'), name='carrier_demo'),

    # Démo admin
    path('demo/admin/', TemplateView.as_view(template_name='colis/demo/admin_demo.html'), name='admin_demo'),
]

urlpatterns += [
    path('demo/', include((demo_urlpatterns, 'demo'))),
]

# ============================================================================
# URLS DE DOCUMENTATION
# ============================================================================

docs_urlpatterns = [
    # Documentation API
    path('api/', TemplateView.as_view(template_name='colis/docs/api_docs.html'), name='api_docs'),
    path('api/v1/', TemplateView.as_view(template_name='colis/docs/api_v1.html'), name='api_v1_docs'),

    # Documentation développeur
    path('developer/', TemplateView.as_view(template_name='colis/docs/developer.html'), name='developer_docs'),
    path('developer/integration/', TemplateView.as_view(template_name='colis/docs/integration.html'),
         name='integration_docs'),

    # Documentation transporteur
    path('carrier/', TemplateView.as_view(template_name='colis/docs/carrier.html'), name='carrier_docs'),

    # Documentation expéditeur
    path('sender/', TemplateView.as_view(template_name='colis/docs/sender.html'), name='sender_docs'),
]

urlpatterns += [
    path('docs/', include((docs_urlpatterns, 'docs'))),
]
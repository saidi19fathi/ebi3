# ~/ebi3/colis/sitemaps.py
"""
Sitemaps XML pour l'application colis
Améliore le SEO en fournissant aux moteurs de recherche
une carte complète du contenu du site
"""

from datetime import datetime, timezone
from django.contrib import sitemaps
from django.urls import reverse
from django.contrib.sites.models import Site
from django.utils.translation import gettext_lazy as _
from django.db.models import F
from .models import Package, PackageCategory


# ============================================================================
# SITEMAPS STATIQUES
# ============================================================================

class StaticSitemap(sitemaps.Sitemap):
    """
    Sitemap pour les pages statiques de l'application colis
    """
    priority = 1.0
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return [
            'colis:package_list',
            'colis:search',
            'colis:how_it_works',
            'colis:pricing',
            'colis:faq',
            'colis:contact',
            'colis:terms',
            'colis:privacy',
            'colis:safety',
            'colis:become_carrier',
            'colis:success_stories',
            'colis:testimonials',
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        """
        Retourne la date de dernière modification des pages statiques
        """
        # Pour les pages statiques, on utilise une date fixe
        # ou la date de déploiement
        return datetime(2024, 1, 1, tzinfo=timezone.utc)


class CategorySitemap(sitemaps.Sitemap):
    """
    Sitemap pour les catégories de colis
    """
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        """
        Retourne toutes les catégories actives avec au moins un colis disponible
        """
        return PackageCategory.objects.filter(
            is_active=True,
            packages__status='AVAILABLE'
        ).distinct().order_by('lft')

    def location(self, obj):
        return reverse('colis:category_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        """
        Dernière modification = date du dernier colis ajouté dans cette catégorie
        """
        last_package = obj.packages.filter(status='AVAILABLE').order_by('-created_at').first()
        if last_package:
            return last_package.created_at
        return obj.updated_at

    def priority(self, obj):
        """
        Priorité SEO basée sur le nombre de colis dans la catégorie
        """
        package_count = obj.packages.filter(status='AVAILABLE').count()
        if package_count > 100:
            return 0.9
        elif package_count > 50:
            return 0.8
        elif package_count > 20:
            return 0.7
        else:
            return 0.6


# ============================================================================
# SITEMAPS DYNAMIQUES - PACKAGES
# ============================================================================

class PackageSitemap(sitemaps.Sitemap):
    """
    Sitemap pour les colis individuels
    Optimisé pour les colis disponibles et récents
    """
    changefreq = 'daily'
    protocol = 'https'
    limit = 5000  # Limite Google sitemap

    def items(self):
        """
        Retourne les colis disponibles pour le sitemap
        """
        # Filtrer les colis disponibles et actifs
        return Package.objects.filter(
            status__in=['AVAILABLE', 'RESERVED', 'IN_TRANSIT'],
            is_archived=False
        ).select_related(
            'sender', 'category'
        ).prefetch_related(
            'images'
        ).order_by('-created_at')

    def location(self, obj):
        return reverse('colis:package_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        """
        Dernière modification = max(created_at, updated_at)
        """
        return max(obj.created_at, obj.updated_at) if obj.updated_at else obj.created_at

    def priority(self, obj):
        """
        Priorité SEO basée sur l'âge et le statut du colis
        """
        # Calculer l'âge en jours
        age_days = (datetime.now(timezone.utc) - obj.created_at).days

        # Priorité basée sur l'âge
        if age_days < 7:  # Moins d'une semaine
            return 0.9
        elif age_days < 30:  # Moins d'un mois
            return 0.8
        elif age_days < 90:  # Moins de 3 mois
            return 0.7
        else:
            return 0.6

    def changefreq(self, obj):
        """
        Fréquence de changement basée sur le statut
        """
        if obj.status == 'AVAILABLE':
            return 'daily'  # Les colis disponibles changent souvent
        elif obj.status == 'RESERVED':
            return 'weekly'
        elif obj.status == 'IN_TRANSIT':
            return 'daily'  # Suivi en temps réel
        else:
            return 'monthly'


class PackageIndexSitemap(sitemaps.Sitemap):
    """
    Sitemap d'index pour les pages de liste de colis avec filtres
    """
    changefreq = 'daily'
    priority = 0.7
    protocol = 'https'

    def items(self):
        """
        Génère des URLs de filtrage pour les moteurs de recherche
        """
        items = []

        # 1. Pages principales de filtrage
        items.append(('colis:package_list', {}))

        # 2. Filtres par catégorie
        categories = PackageCategory.objects.filter(
            is_active=True,
            packages__status='AVAILABLE'
        ).distinct()[:50]  # Limiter à 50 catégories

        for category in categories:
            items.append(('colis:category_detail', {'slug': category.slug}))

        # 3. Filtres par pays
        from django_countries import countries
        popular_countries = ['FR', 'MA', 'TN', 'DZ', 'BE', 'CH', 'CA']

        for country_code in popular_countries:
            items.append(('colis:package_list', {'country_to': country_code}))

        # 4. Filtres par prix (plages)
        price_ranges = [
            (0, 100),
            (100, 500),
            (500, 1000),
            (1000, 5000),
        ]

        for min_price, max_price in price_ranges:
            items.append(('colis:search', {
                'min_price': min_price,
                'max_price': max_price
            }))

        return items

    def location(self, item):
        url_name, params = item
        return reverse(url_name, kwargs=params) if params else reverse(url_name)


# ============================================================================
# SITEMAPS DYNAMIQUES - TRANSPORTEURS (OPTIONNEL)
# ============================================================================

class CarrierSitemap(sitemaps.Sitemap):
    """
    Sitemap pour les profils de transporteurs
    """
    changefreq = 'weekly'
    priority = 0.7
    protocol = 'https'
    limit = 2000

    def items(self):
        """
        Transporteurs actifs et vérifiés
        Note: Cette classe est optionnelle, dépend de l'existence du modèle Carrier
        """
        try:
            from carriers.models import Carrier
            return Carrier.objects.filter(
                status='APPROVED',
                is_available=True,
                verification_level__gte=2  # Au moins partiellement vérifié
            ).select_related('user').order_by('-average_rating', '-total_missions')
        except ImportError:
            # Retourner une liste vide si l'application carriers n'est pas disponible
            return []

    def location(self, obj):
        from django.urls import reverse
        return reverse('carriers:carrier_detail', kwargs={'username': obj.user.username})

    def lastmod(self, obj):
        """
        Dernière modification = date de dernière mise à jour du profil
        """
        return max(obj.user.date_joined, obj.updated_at)

    def priority(self, obj):
        """
        Priorité basée sur la réputation du transporteur
        """
        if obj.average_rating >= 4.5 and obj.total_missions > 50:
            return 0.9
        elif obj.average_rating >= 4.0 and obj.total_missions > 20:
            return 0.8
        elif obj.average_rating >= 3.5:
            return 0.7
        else:
            return 0.6


# ============================================================================
# SITEMAPS SPÉCIALISÉS
# ============================================================================

class RecentPackagesSitemap(sitemaps.Sitemap):
    """
    Sitemap pour les colis récemment ajoutés (dernières 24h)
    """
    changefreq = 'hourly'
    priority = 1.0
    protocol = 'https'
    limit = 100

    def items(self):
        from django.utils import timezone
        yesterday = timezone.now() - timezone.timedelta(days=1)

        return Package.objects.filter(
            status='AVAILABLE',
            created_at__gte=yesterday,
            is_archived=False
        ).order_by('-created_at')[:self.limit]

    def location(self, obj):
        return reverse('colis:package_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        return obj.created_at


class PopularPackagesSitemap(sitemaps.Sitemap):
    """
    Sitemap pour les colis populaires (plus de vues/favoris)
    """
    changefreq = 'daily'
    priority = 0.9
    protocol = 'https'
    limit = 100

    def items(self):
        """
        Colis les plus populaires basés sur les vues et favoris
        """
        return Package.objects.filter(
            status='AVAILABLE',
            is_archived=False
        ).annotate(
            popularity_score=(F('view_count') * 1) + (F('favorite_count') * 3)
        ).order_by('-popularity_score', '-created_at')[:self.limit]

    def location(self, obj):
        return reverse('colis:package_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        return max(obj.created_at, obj.updated_at) if obj.updated_at else obj.created_at


class GeoPackageSitemap(sitemaps.Sitemap):
    """
    Sitemap géographique pour les colis par ville/région
    """
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        """
        Retourne les combinaisons uniques pays/ville avec au moins 5 colis
        """
        from django.db.models import Count
        from django.db.models.functions import Lower

        return Package.objects.filter(
            status='AVAILABLE'
        ).values(
            'country_to', 'city_to'
        ).annotate(
            package_count=Count('id')
        ).filter(
            package_count__gte=5
        ).order_by('country_to', Lower('city_to'))

    def location(self, obj):
        """
        URL de recherche filtrée par ville
        """
        return reverse('colis:search') + f'?country_to={obj["country_to"]}&city_to={obj["city_to"]}'

    def lastmod(self, obj):
        """
        Dernière modification = date du dernier colis pour cette destination
        """
        last_package = Package.objects.filter(
            country_to=obj['country_to'],
            city_to=obj['city_to'],
            status='AVAILABLE'
        ).order_by('-created_at').first()

        return last_package.created_at if last_package else datetime.now(timezone.utc)


# ============================================================================
# SITEMAPS AVANCÉS POUR SEO TECHNIQUE
# ============================================================================

class XMLIndexSitemap(sitemaps.Sitemap):
    """
    Sitemap d'index qui liste tous les autres sitemaps
    """
    def items(self):
        """
        Liste de tous les sitemaps à inclure dans l'index
        """
        current_site = Site.objects.get_current()
        base_url = f"https://{current_site.domain}/colis/sitemap_"

        sitemaps_list = [
            f"{base_url}static.xml",
            f"{base_url}categories.xml",
            f"{base_url}packages.xml",
        ]

        # Ajouter conditionnellement le sitemap des transporteurs
        try:
            from carriers.models import Carrier
            if Carrier.objects.exists():
                sitemaps_list.append(f"{base_url}carriers.xml")
        except ImportError:
            pass

        # Ajouter d'autres sitemaps conditionnels
        if Package.objects.filter(status='AVAILABLE').count() > 100:
            sitemaps_list.extend([
                f"{base_url}recent.xml",
                f"{base_url}popular.xml",
            ])

        if Package.objects.filter(status='AVAILABLE').count() > 500:
            sitemaps_list.append(f"{base_url}geo.xml")

        return sitemaps_list

    def location(self, item):
        return item

    def lastmod(self, item):
        """
        Tous les sitemaps sont mis à jour quotidiennement
        """
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


class MobileSitemap(sitemaps.Sitemap):
    """
    Sitemap spécifique pour les versions mobiles
    """
    changefreq = 'daily'
    priority = 0.9
    protocol = 'https'
    limit = 1000

    def items(self):
        """
        Colis optimisés pour mobile (avec images et descriptions courtes)
        """
        return Package.objects.filter(
            status='AVAILABLE',
            images__isnull=False,  # Au moins une image
            is_archived=False
        ).exclude(
            description__isnull=True
        ).exclude(
            description=''
        ).distinct().order_by('-created_at')[:self.limit]

    def location(self, obj):
        return reverse('colis:package_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        return max(obj.created_at, obj.updated_at) if obj.updated_at else obj.created_at


class ImageSitemap(sitemaps.Sitemap):
    """
    Sitemap pour les images des colis (Google Images SEO)
    """
    changefreq = 'weekly'
    priority = 0.6
    protocol = 'https'
    limit = 1000

    def items(self):
        """
        Retourne les colis avec des images
        """
        return Package.objects.filter(
            images__isnull=False,
            status__in=['AVAILABLE', 'RESERVED', 'IN_TRANSIT'],
            is_archived=False
        ).prefetch_related('images').distinct().order_by('-created_at')[:self.limit]

    def location(self, obj):
        return reverse('colis:package_detail', kwargs={'slug': obj.slug})

    def lastmod(self, obj):
        return max(obj.created_at, obj.updated_at) if obj.updated_at else obj.created_at

    def _get_images(self, obj):
        """
        Retourne les informations des images pour le sitemap
        """
        images = []
        for img in obj.images.all()[:10]:  # Limiter à 10 images par colis
            if img.image:
                images.append({
                    'location': img.image.url,
                    'title': img.caption or f"Image de {obj.title}",
                    'caption': img.caption or f"Photo du colis {obj.title}",
                    'license': 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
                })
        return images


# ============================================================================
# SITEMAP FACTORY ET REGISTRE
# ============================================================================

def get_colis_sitemaps():
    """
    Retourne un dictionnaire de tous les sitemaps pour l'application colis
    """
    sitemaps_dict = {
        'static': StaticSitemap,
        'categories': CategorySitemap,
        'packages': PackageSitemap,
        'index': XMLIndexSitemap,
    }

    # Ajouter conditionnellement le sitemap des transporteurs
    try:
        from carriers.models import Carrier
        if Carrier.objects.exists():
            sitemaps_dict['carriers'] = CarrierSitemap
    except ImportError:
        pass

    # Ajouter des sitemaps supplémentaires
    if Package.objects.filter(status='AVAILABLE').count() > 0:
        sitemaps_dict['recent'] = RecentPackagesSitemap
        sitemaps_dict['popular'] = PopularPackagesSitemap
        sitemaps_dict['mobile'] = MobileSitemap
        sitemaps_dict['images'] = ImageSitemap

    if Package.objects.filter(status='AVAILABLE').count() > 500:
        sitemaps_dict['geo'] = GeoPackageSitemap

    return sitemaps_dict


def get_active_sitemaps():
    """
    Retourne les sitemaps actifs selon le contexte
    """
    sitemaps = {
        'static': StaticSitemap(),
        'categories': CategorySitemap(),
        'packages': PackageSitemap(),
    }

    # Ajouter conditionnellement le sitemap des transporteurs
    try:
        from carriers.models import Carrier
        if Carrier.objects.filter(status='APPROVED').exists():
            sitemaps['carriers'] = CarrierSitemap()
    except (ImportError, ModuleNotFoundError):
        # L'application carriers n'est pas disponible ou pas installée
        pass

    # Ajouter des sitemaps supplémentaires si beaucoup de contenu
    package_count = Package.objects.filter(status='AVAILABLE').count()

    if package_count > 0:
        sitemaps['recent'] = RecentPackagesSitemap()
        sitemaps['popular'] = PopularPackagesSitemap()
        sitemaps['mobile'] = MobileSitemap()
        sitemaps['images'] = ImageSitemap()

    if package_count > 500:
        sitemaps['geo'] = GeoPackageSitemap()

    return sitemaps


# ============================================================================
# UTILITAIRES POUR GÉNÉRATION DE SITEMAP
# ============================================================================

class SitemapGenerator:
    """
    Classe utilitaire pour générer et gérer les sitemaps
    """

    @staticmethod
    def generate_sitemap_index():
        """
        Génère le contenu XML de l'index des sitemaps
        """
        current_site = Site.objects.get_current()
        sitemaps = get_active_sitemaps()

        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        for name, sitemap in sitemaps.items():
            if name != 'index':  # Exclure l'index lui-même
                url = f"https://{current_site.domain}/colis/sitemap_{name}.xml"
                lastmod = datetime.now(timezone.utc).strftime('%Y-%m-%d')

                xml_content += f'  <sitemap>\n'
                xml_content += f'    <loc>{url}</loc>\n'
                xml_content += f'    <lastmod>{lastmod}</lastmod>\n'
                xml_content += f'  </sitemap>\n'

        xml_content += '</sitemapindex>'
        return xml_content

    @staticmethod
    def get_sitemap_stats():
        """
        Retourne des statistiques sur les sitemaps
        """
        stats = {
            'total_urls': 0,
            'by_type': {},
            'last_generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        }

        sitemaps = get_active_sitemaps()

        for name, sitemap in sitemaps.items():
            try:
                if hasattr(sitemap, 'items'):
                    items = sitemap.items()
                    if hasattr(items, 'count'):
                        count = items.count()
                    else:
                        count = len(items)
                    stats['by_type'][name] = count
                    stats['total_urls'] += count
                else:
                    stats['by_type'][name] = 0
            except Exception as e:
                stats['by_type'][name] = f"Error: {str(e)[:50]}"

        return stats

    @staticmethod
    def validate_sitemap_urls():
        """
        Valide que toutes les URLs du sitemap sont valides
        """
        from django.urls import resolve, Resolver404

        sitemaps = get_active_sitemaps()
        validation_results = []

        for name, sitemap in sitemaps.items():
            if hasattr(sitemap, 'items'):
                items = sitemap.items()[:5]  # Tester seulement les 5 premiers

                for item in items:
                    try:
                        url = sitemap.location(item)

                        # Tester la résolution de l'URL
                        try:
                            resolve(url)
                            url_valid = True
                        except Resolver404:
                            url_valid = False

                        validation_results.append({
                            'sitemap': name,
                            'url': url,
                            'item': str(item)[:100],
                            'url_valid': url_valid,
                        })
                    except Exception as e:
                        validation_results.append({
                            'sitemap': name,
                            'url': 'ERROR',
                            'item': str(item)[:100],
                            'error': str(e)[:100],
                        })

        return validation_results
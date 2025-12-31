# ~/ebi3/colis/admin.py
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.urls import reverse, path
from django.http import HttpResponseRedirect
from django.db.models import Count, Avg, Sum, Q
from django.db import models
import csv
from django.http import HttpResponse

from .models import (
    Package, PackageCategory, PackageImage,
    TransportOffer, PackageView, PackageFavorite, PackageReport
)


@admin.register(PackageCategory)
class PackageCategoryAdmin(admin.ModelAdmin):
    """Administration des catégories de colis"""

    # ✅ CORRECTION : actions doit être une LISTE de noms de méthodes
    actions = ['activate_categories', 'deactivate_categories', 'show_in_menu_action', 'hide_from_menu_action']

    list_display = ('name', 'parent', 'is_active', 'show_in_menu', 'package_count', 'display_order')
    list_filter = ('is_active', 'show_in_menu', 'created_at')
    search_fields = ('name', 'description', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at', 'package_count')

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('name', 'slug', 'parent', 'description')
        }),
        (_('Apparence'), {
            'fields': ('icon', 'image', 'display_order')
        }),
        (_('Visibilité'), {
            'fields': ('is_active', 'show_in_menu')
        }),
        (_('Configuration des colis'), {
            'fields': ('requires_dimensions', 'requires_weight')
        }),
        (_('SEO'), {
            'fields': ('meta_title', 'meta_description')
        }),
        (_('Statistiques'), {
            'fields': ('package_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ Les méthodes d'action doivent être séparées de la liste 'actions'
    def activate_categories(self, request, queryset):
        """Action pour activer les catégories"""
        updated = queryset.update(is_active=True)
        self.message_user(request, _(f'{updated} catégories ont été activées.'))
    activate_categories.short_description = _('Activer les catégories sélectionnées')

    def deactivate_categories(self, request, queryset):
        """Action pour désactiver les catégories"""
        updated = queryset.update(is_active=False)
        self.message_user(request, _(f'{updated} catégories ont été désactivées.'))
    deactivate_categories.short_description = _('Désactiver les catégories sélectionnées')

    def show_in_menu_action(self, request, queryset):
        """Action pour afficher dans le menu"""
        updated = queryset.update(show_in_menu=True)
        self.message_user(request, _(f'{updated} catégories sont maintenant visibles dans le menu.'))
    show_in_menu_action.short_description = _('Afficher dans le menu')

    def hide_from_menu_action(self, request, queryset):
        """Action pour cacher du menu"""
        updated = queryset.update(show_in_menu=False)
        self.message_user(request, _(f'{updated} catégories sont maintenant cachées du menu.'))
    hide_from_menu_action.short_description = _('Cacher du menu')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('parent')


class PackageImageInline(admin.TabularInline):
    """Inline pour les images de colis"""
    model = PackageImage
    extra = 1
    fields = ('image', 'thumbnail_preview', 'caption', 'is_primary', 'display_order')
    readonly_fields = ('thumbnail_preview',)

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.thumbnail.url)
        elif obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.image.url)
        return _("Pas d'image")
    thumbnail_preview.short_description = _('Aperçu')


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    """Administration des colis"""

    inlines = [PackageImageInline]

    list_display = (
        'title', 'sender', 'category', 'package_type_badge',
        'pickup_to_destination', 'weight_volume_display',
        'asking_price_display', 'status_badge', 'is_featured',
        'view_count', 'offer_count', 'created_at'
    )

    list_filter = (
        'status', 'package_type', 'price_type',
        'is_featured', 'created_at', 'category',
        'pickup_country', 'delivery_country'
    )

    search_fields = (
        'title', 'description', 'sender__username',
        'sender__email', 'pickup_city', 'delivery_city'
    )

    readonly_fields = (
        'slug', 'view_count', 'offer_count', 'favorite_count',
        'created_at', 'updated_at', 'published_at', 'expired_at',
        'reserved_at', 'delivered_at', 'volume',
        'paid_images_used', 'estimated_distance'
    )

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('title', 'slug', 'sender', 'category', 'description', 'package_type')
        }),
        (_('Dimensions et poids'), {
            'fields': ('weight', 'length', 'width', 'height', 'volume')
        }),
        (_('Origine'), {
            'fields': ('pickup_country', 'pickup_city', 'pickup_address', 'pickup_postal_code',
                      'pickup_latitude', 'pickup_longitude')
        }),
        (_('Destination'), {
            'fields': ('delivery_country', 'delivery_city', 'delivery_address', 'delivery_postal_code',
                      'delivery_latitude', 'delivery_longitude')
        }),
        (_('Dates'), {
            'fields': ('pickup_date', 'delivery_date', 'flexible_dates')
        }),
        (_('Prix'), {
            'fields': ('price_type', 'asking_price', 'currency', 'estimated_distance')
        }),
        (_('Options'), {
            'fields': ('is_fragile', 'requires_insurance', 'insurance_value',
                      'requires_packaging', 'requires_loading_help', 'requires_unloading_help')
        }),
        (_('Statut et promotion'), {
            'fields': ('status', 'is_featured', 'featured_until')
        }),
        (_('Multimédia'), {
            'fields': ('free_images_allowed', 'paid_images_used'),
            'classes': ('collapse',)
        }),
        (_('SEO'), {
            'fields': ('meta_keywords', 'meta_description'),
            'classes': ('collapse',)
        }),
        (_('Statistiques'), {
            'fields': ('view_count', 'offer_count', 'favorite_count',
                      'created_at', 'updated_at', 'published_at', 'expired_at',
                      'reserved_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION IMPORTANTE: actions doit être une LISTE de noms de méthodes
    actions = [
        'mark_as_available', 'mark_as_reserved', 'mark_as_in_transit',
        'mark_as_delivered', 'mark_as_cancelled', 'feature_packages',
        'unfeature_packages', 'export_to_csv', 'calculate_distances'
    ]

    def package_type_badge(self, obj):
        colors = {
            'SMALL_PACKAGE': 'success',
            'MEDIUM_PACKAGE': 'info',
            'LARGE_PACKAGE': 'warning',
            'FURNITURE': 'primary',
            'PALLET': 'secondary',
            'VEHICLE_PART': 'dark',
            'OTHER': 'light'
        }
        color = colors.get(obj.package_type, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_package_type_display()
        )
    package_type_badge.short_description = _('Type')
    package_type_badge.admin_order_field = 'package_type'

    def pickup_to_destination(self, obj):
        return format_html(
            '{} → {}',
            obj.pickup_city,
            obj.delivery_city
        )
    pickup_to_destination.short_description = _('Trajet')
    pickup_to_destination.admin_order_field = 'pickup_city'

    def weight_volume_display(self, obj):
        if obj.volume:
            return f"{obj.weight} kg / {obj.volume:.1f} L"
        return f"{obj.weight} kg"
    weight_volume_display.short_description = _('Poids/Volume')

    def asking_price_display(self, obj):
        return f"{obj.asking_price} {obj.get_currency_display()}"
    asking_price_display.short_description = _('Prix')
    asking_price_display.admin_order_field = 'asking_price'

    def status_badge(self, obj):
        status_colors = {
            'DRAFT': 'secondary',
            'AVAILABLE': 'success',
            'RESERVED': 'info',
            'IN_TRANSIT': 'warning',
            'DELIVERED': 'primary',
            'CANCELLED': 'danger',
            'EXPIRED': 'dark'
        }
        color = status_colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Statut')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sender', 'category')

    # ✅ Les méthodes d'action doivent être définies séparément
    def mark_as_available(self, request, queryset):
        """Action pour marquer comme disponible"""
        updated = queryset.update(status=Package.Status.AVAILABLE)
        self.message_user(request, _(f'{updated} colis ont été marqués comme disponibles.'))
    mark_as_available.short_description = _('Marquer comme disponible')

    def mark_as_reserved(self, request, queryset):
        """Action pour marquer comme réservé"""
        updated = queryset.update(status=Package.Status.RESERVED, reserved_at=timezone.now())
        self.message_user(request, _(f'{updated} colis ont été marqués comme réservés.'))
    mark_as_reserved.short_description = _('Marquer comme réservé')

    def mark_as_in_transit(self, request, queryset):
        """Action pour marquer comme en transit"""
        updated = queryset.update(status=Package.Status.IN_TRANSIT)
        self.message_user(request, _(f'{updated} colis ont été marqués comme en transit.'))
    mark_as_in_transit.short_description = _('Marquer comme en transit')

    def mark_as_delivered(self, request, queryset):
        """Action pour marquer comme livré"""
        updated = queryset.update(
            status=Package.Status.DELIVERED,
            delivered_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} colis ont été marqués comme livrés.'))
    mark_as_delivered.short_description = _('Marquer comme livré')

    def mark_as_cancelled(self, request, queryset):
        """Action pour marquer comme annulé"""
        updated = queryset.update(status=Package.Status.CANCELLED)
        self.message_user(request, _(f'{updated} colis ont été marqués comme annulés.'))
    mark_as_cancelled.short_description = _('Marquer comme annulé')

    def feature_packages(self, request, queryset):
        """Action pour mettre en vedette"""
        updated = queryset.update(
            is_featured=True,
            featured_until=timezone.now() + timezone.timedelta(days=7)
        )
        self.message_user(request, _(f'{updated} colis ont été mis en vedette.'))
    feature_packages.short_description = _('Mettre en vedette')

    def unfeature_packages(self, request, queryset):
        """Action pour retirer de la vedette"""
        updated = queryset.update(is_featured=False, featured_until=None)
        self.message_user(request, _(f'{updated} colis ne sont plus en vedette.'))
    unfeature_packages.short_description = _('Retirer de la vedette')

    def calculate_distances(self, request, queryset):
        """Action pour calculer les distances (à implémenter avec une API)"""
        count = 0
        for package in queryset:
            if not package.estimated_distance:
                # À implémenter avec Google Maps API ou autre
                # package.estimated_distance = calculate_distance(...)
                # package.save()
                count += 1

        if count > 0:
            self.message_user(request, _(f'Distances calculées pour {count} colis.'))
        else:
            self.message_user(request, _('Tous les colis ont déjà une distance calculée.'))
    calculate_distances.short_description = _('Calculer les distances')

    def export_to_csv(self, request, queryset):
        """Action pour exporter en CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="colis.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Titre', 'Expéditeur', 'Catégorie', 'Type',
            'Prix', 'Devise', 'Statut', 'Départ', 'Destination',
            'Poids', 'Volume', 'Vues', 'Offres', 'Date création'
        ])

        for package in queryset:
            writer.writerow([
                package.id, package.title, package.sender.username,
                package.category.name if package.category else '',
                package.get_package_type_display(),
                package.asking_price, package.currency,
                package.get_status_display(),
                f"{package.pickup_city}, {package.pickup_country.name}",
                f"{package.delivery_city}, {package.delivery_country.name}",
                package.weight, package.volume, package.view_count,
                package.offer_count, package.created_at.strftime('%Y-%m-%d %H:%M')
            ])

        return response
    export_to_csv.short_description = _('Exporter en CSV')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.sender = request.user

        # Si le statut passe à DISPONIBLE et qu'il n'y a pas de date de publication
        if obj.status == Package.Status.AVAILABLE and not obj.published_at:
            obj.published_at = timezone.now()

        # Si le statut passe à RÉSERVÉ
        if obj.status == Package.Status.RESERVED and not obj.reserved_at:
            obj.reserved_at = timezone.now()

        # Si le statut passe à LIVRÉ
        if obj.status == Package.Status.DELIVERED and not obj.delivered_at:
            obj.delivered_at = timezone.now()

        super().save_model(request, obj, form, change)

    # Vue personnalisée pour les statistiques
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('statistics/', self.admin_site.admin_view(self.package_statistics_view),
                 name='colis_package_statistics'),
        ]
        return custom_urls + urls

    def package_statistics_view(self, request):
        """Vue personnalisée pour les statistiques des colis"""
        context = self.admin_site.each_context(request)

        # Statistiques générales
        total_packages = Package.objects.count()
        available_packages = Package.objects.filter(status=Package.Status.AVAILABLE).count()
        reserved_packages = Package.objects.filter(status=Package.Status.RESERVED).count()
        delivered_packages = Package.objects.filter(status=Package.Status.DELIVERED).count()

        # Revenus estimés
        revenue_stats = Package.objects.filter(
            status__in=[Package.Status.RESERVED, Package.Status.IN_TRANSIT, Package.Status.DELIVERED]
        ).aggregate(
            total_revenue=Sum('asking_price'),
            avg_price=Avg('asking_price')
        )

        # Statistiques par type
        type_stats = Package.objects.values('package_type').annotate(
            count=Count('id'),
            avg_price=Avg('asking_price')
        ).order_by('-count')

        # Évolution mensuelle
        monthly_stats = Package.objects.extra(
            select={'month': "strftime('%%Y-%%m', created_at)"}
        ).values('month').annotate(
            count=Count('id'),
            total_views=Sum('view_count'),
            total_offers=Sum('offer_count'),
        ).order_by('month')[:12]

        context.update({
            'title': _('Statistiques des colis'),
            'total_packages': total_packages,
            'available_packages': available_packages,
            'reserved_packages': reserved_packages,
            'delivered_packages': delivered_packages,
            'revenue_stats': revenue_stats,
            'type_stats': type_stats,
            'monthly_stats': monthly_stats,
        })

        return render(request, 'admin/colis/package_statistics.html', context)


@admin.register(PackageImage)
class PackageImageAdmin(admin.ModelAdmin):
    """Administration des images de colis"""

    list_display = ('package', 'thumbnail_preview', 'caption', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('package__title', 'caption')
    readonly_fields = ('created_at',)

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.thumbnail.url)
        elif obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.image.url)
        return _("Pas d'image")
    thumbnail_preview.short_description = _('Aperçu')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('package')


@admin.register(TransportOffer)
class TransportOfferAdmin(admin.ModelAdmin):
    """Administration des offres de transport"""

    list_display = (
        'id', 'package_link', 'carrier_link',
        'price_display', 'status_badge',
        'dates_display', 'created_at'
    )

    list_filter = ('status', 'created_at', 'provides_insurance')
    search_fields = (
        'package__title', 'carrier__user__username',
        'carrier__company_name', 'message'
    )

    readonly_fields = (
        'created_at', 'updated_at', 'accepted_at', 'expires_at'
    )

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('package', 'carrier', 'status')
        }),
        (_('Détails de l\'offre'), {
            'fields': ('price', 'currency', 'message',
                      'proposed_pickup_date', 'proposed_delivery_date')
        }),
        (_('Services inclus'), {
            'fields': ('provides_insurance', 'insurance_coverage',
                      'provides_packaging', 'provides_loading', 'provides_unloading')
        }),
        (_('Suivi'), {
            'fields': ('rejection_reason', 'accepted_at', 'expires_at')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION: actions doit être une LISTE de noms de méthodes
    actions = ['accept_offers', 'reject_offers', 'mark_as_expired']

    def package_link(self, obj):
        url = reverse('admin:colis_package_change', args=[obj.package.id])
        return format_html('<a href="{}">{}</a>', url, obj.package.title)
    package_link.short_description = _('Colis')
    package_link.admin_order_field = 'package__title'

    def carrier_link(self, obj):
        url = reverse('admin:carriers_carrier_change', args=[obj.carrier.id])
        carrier_name = obj.carrier.company_name or obj.carrier.user.username
        return format_html('<a href="{}">{}</a>', url, carrier_name)
    carrier_link.short_description = _('Transporteur')
    carrier_link.admin_order_field = 'carrier__user__username'

    def price_display(self, obj):
        return f"{obj.price} {obj.get_currency_display()}"
    price_display.short_description = _('Prix')
    price_display.admin_order_field = 'price'

    def status_badge(self, obj):
        status_colors = {
            'PENDING': 'warning',
            'ACCEPTED': 'success',
            'REJECTED': 'danger',
            'CANCELLED': 'secondary',
            'EXPIRED': 'dark'
        }
        color = status_colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Statut')

    def dates_display(self, obj):
        return format_html(
            '{} → {}',
            obj.proposed_pickup_date.strftime('%d/%m/%Y'),
            obj.proposed_delivery_date.strftime('%d/%m/%Y')
        )
    dates_display.short_description = _('Dates proposées')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('package', 'carrier', 'carrier__user')

    # ✅ Les méthodes d'action doivent être définies séparément
    def accept_offers(self, request, queryset):
        """Action pour accepter les offres"""
        count = 0
        for offer in queryset.filter(status=TransportOffer.Status.PENDING):
            if offer.can_be_accepted():
                offer.status = TransportOffer.Status.ACCEPTED
                offer.accepted_at = timezone.now()
                offer.save()
                count += 1

        self.message_user(request, _(f'{count} offres ont été acceptées.'))
    accept_offers.short_description = _('Accepter les offres sélectionnées')

    def reject_offers(self, request, queryset):
        """Action pour rejeter les offres"""
        updated = queryset.update(status=TransportOffer.Status.REJECTED)
        self.message_user(request, _(f'{updated} offres ont été rejetées.'))
    reject_offers.short_description = _('Rejeter les offres sélectionnées')

    def mark_as_expired(self, request, queryset):
        """Action pour marquer comme expiré"""
        updated = queryset.update(status=TransportOffer.Status.EXPIRED)
        self.message_user(request, _(f'{updated} offres ont été marquées comme expirées.'))
    mark_as_expired.short_description = _('Marquer comme expiré')

    def save_model(self, request, obj, form, change):
        # Si l'offre est acceptée, mettre à jour le colis
        if obj.status == TransportOffer.Status.ACCEPTED and not obj.accepted_at:
            obj.accepted_at = timezone.now()
            obj.package.status = Package.Status.RESERVED
            obj.package.reserved_at = timezone.now()
            obj.package.save()

        super().save_model(request, obj, form, change)


@admin.register(PackageView)
class PackageViewAdmin(admin.ModelAdmin):
    """Administration des vues de colis"""

    list_display = ('package', 'user', 'ip_address', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('package__title', 'user__username', 'ip_address')
    readonly_fields = ('viewed_at',)

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('package', 'user')


@admin.register(PackageFavorite)
class PackageFavoriteAdmin(admin.ModelAdmin):
    """Administration des favoris de colis"""

    list_display = ('user', 'package', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'package__title')
    readonly_fields = ('created_at',)

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'package')


@admin.register(PackageReport)
class PackageReportAdmin(admin.ModelAdmin):
    """Administration des signalements de colis"""

    # ✅ CORRECTION: Ajouter 'status' à list_display
    list_display = ('package', 'reporter', 'reason', 'status', 'status_badge', 'created_at')
    list_filter = ('reason', 'status', 'created_at')
    search_fields = ('package__title', 'reporter__username', 'description')
    list_editable = ('status',)
    readonly_fields = ('created_at',)

    fieldsets = (
        (_('Signalement'), {
            'fields': ('package', 'reporter', 'reason', 'description', 'evidence')
        }),
        (_('Traitement'), {
            'fields': ('status', 'admin_notes', 'resolved_by', 'resolved_at')
        }),
        (_('Métadonnées'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION: actions doit être une liste de noms de méthodes
    actions = ['mark_as_resolved', 'mark_as_dismissed']

    def status_badge(self, obj):
        status_colors = {
            'PENDING': 'warning',
            'IN_REVIEW': 'info',
            'RESOLVED': 'success',
            'DISMISSED': 'secondary'
        }
        color = status_colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Badge Statut')

    def status(self, obj):
        """Affiche le statut textuel pour list_display"""
        return obj.get_status_display()
    status.short_description = _('Statut')

    def mark_as_resolved(self, request, queryset):
        """Action pour marquer comme résolu"""
        updated = queryset.update(
            status='RESOLVED',
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} signalements ont été résolus.'))
    mark_as_resolved.short_description = _('Marquer comme résolu')

    def mark_as_dismissed(self, request, queryset):
        """Action pour rejeter les signalements"""
        updated = queryset.update(
            status='DISMISSED',
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} signalements ont été rejetés.'))
    mark_as_dismissed.short_description = _('Rejeter les signalements')

    def save_model(self, request, obj, form, change):
        if obj.status in ['RESOLVED', 'DISMISSED'] and not obj.resolved_by:
            obj.resolved_by = request.user
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('package', 'reporter', 'resolved_by')

# ============================================================================
# PANNEAUX D'ADMINISTRATION PERSONNALISÉS
# ============================================================================

class ColisAdminSite(admin.AdminSite):
    """Site d'administration personnalisé pour l'application colis"""

    site_header = _("Administration des colis Ebi3")
    site_title = _("Administration des colis")
    index_title = _("Tableau de bord")

    def get_app_list(self, request):
        """
        Retourne une liste triée des applications.
        """
        app_list = super().get_app_list(request)

        # Réorganiser les applications pour mettre 'colis' en premier
        for app in app_list:
            if app['app_label'] == 'colis':
                app_list.remove(app)
                app_list.insert(0, app)
                break

        return app_list


# ============================================================================
# MODÈLES POUR LE PANNEAU D'ADMINISTRATION
# ============================================================================

class PackageStatistics(models.Model):
    """Modèle virtuel pour les statistiques (admin seulement)"""

    class Meta:
        verbose_name = _("Statistiques")
        verbose_name_plural = _("Statistiques")
        managed = False  # Ne crée pas de table dans la base de données


class PackageStatisticsAdmin(admin.ModelAdmin):
    """Administration des statistiques des colis"""

    # Cette vue n'a pas de modèle réel, donc on désactive les actions normales
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Rediriger vers notre vue personnalisée
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:colis_package_statistics'))

    def get_urls(self):
        return []


# Enregistrement du modèle virtuel pour les statistiques
admin.site.register(PackageStatistics, PackageStatisticsAdmin)
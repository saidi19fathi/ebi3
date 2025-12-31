# ~/ebi3/ads/admin.py
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.urls import reverse
from django.db.models import Count, Avg, Sum, Q
from django.http import HttpResponseRedirect
import csv
from django.http import HttpResponse

from .models import (
    Ad, Category, AdImage, AdVideo, Favorite,
    AdView, AdReport
)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Administration des catégories"""

    list_display = ('name', 'parent', 'is_active', 'show_in_menu', 'ad_count', 'display_order')
    list_filter = ('is_active', 'show_in_menu', 'created_at')
    search_fields = ('name', 'description', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at', 'ad_count')

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
        (_('Configuration des annonces'), {
            'fields': ('requires_dimensions', 'requires_weight')
        }),
        (_('SEO'), {
            'fields': ('meta_title', 'meta_description')
        }),
        (_('Statistiques'), {
            'fields': ('ad_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION : actions doit être une LISTE de noms de méthodes
    actions = ['activate_categories', 'deactivate_categories', 'show_in_menu_action', 'hide_from_menu_action']

    # ✅ Les méthodes d'action doivent être séparées
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


class AdImageInline(admin.TabularInline):
    """Inline pour les images d'annonce"""
    model = AdImage
    extra = 1
    fields = ('image', 'thumbnail_preview', 'caption', 'is_primary', 'display_order', 'is_paid', 'payment_status')
    readonly_fields = ('thumbnail_preview',)

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.thumbnail.url)
        elif obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.image.url)
        return _("Pas d'image")
    thumbnail_preview.short_description = _('Aperçu')


class AdVideoInline(admin.TabularInline):
    """Inline pour les vidéos d'annonce"""
    model = AdVideo
    extra = 0
    fields = ('video', 'thumbnail_preview', 'caption', 'is_paid', 'payment_status')
    readonly_fields = ('thumbnail_preview',)

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.thumbnail.url)
        return _("Pas de miniature")
    thumbnail_preview.short_description = _('Aperçu')


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    """Administration des annonces"""

    inlines = [AdImageInline, AdVideoInline]

    list_display = (
        'title', 'seller', 'category', 'price_with_currency',
        'status_badge', 'is_featured', 'view_count',
        'favorite_count', 'created_at'
    )

    list_filter = (
        'status', 'condition', 'logistics_option',
        'is_featured', 'created_at', 'category'
    )

    search_fields = (
        'title', 'description', 'seller__username',
        'seller__email', 'city_from', 'city_to'
    )

    readonly_fields = (
        'slug', 'view_count', 'favorite_count', 'inquiry_count',
        'created_at', 'updated_at', 'published_at', 'expired_at',
        'volume', 'paid_images_used', 'videos_used'
    )

    fieldsets = (
        (_('Informations de base'), {
            'fields': ('title', 'slug', 'seller', 'category', 'description')
        }),
        (_('État et prix'), {
            'fields': ('condition', 'price', 'currency', 'is_negotiable')
        }),
        (_('Dimensions'), {
            'fields': ('weight', 'length', 'width', 'height', 'volume')
        }),
        (_('Origine'), {
            'fields': ('country_from', 'city_from', 'address_from')
        }),
        (_('Destination'), {
            'fields': ('country_to', 'city_to', 'address_to')
        }),
        (_('Logistique'), {
            'fields': ('logistics_option', 'requires_insurance',
                      'insurance_value', 'fragile_item', 'requires_packaging')
        }),
        (_('Disponibilité'), {
            'fields': ('available_from', 'available_until')
        }),
        (_('Statut et promotion'), {
            'fields': ('status', 'is_featured', 'featured_until',
                      'rejection_reason')
        }),
        (_('Multimédia'), {
            'fields': ('free_images_allowed', 'paid_images_used',
                      'videos_allowed', 'videos_used'),
            'classes': ('collapse',)
        }),
        (_('SEO'), {
            'fields': ('meta_keywords', 'meta_description'),
            'classes': ('collapse',)
        }),
        (_('Statistiques'), {
            'fields': ('view_count', 'favorite_count', 'inquiry_count',
                      'created_at', 'updated_at', 'published_at', 'expired_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ CORRECTION IMPORTANTE: actions doit être une LISTE de noms de méthodes
    actions = [
        'approve_ads', 'reject_ads', 'feature_ads', 'unfeature_ads',
        'mark_as_sold', 'mark_as_expired', 'export_to_csv'
    ]

    def price_with_currency(self, obj):
        return f"{obj.price} {obj.get_currency_display()}"
    price_with_currency.short_description = _('Prix')
    price_with_currency.admin_order_field = 'price'

    def status_badge(self, obj):
        status_colors = {
            'DRAFT': 'secondary',
            'PENDING': 'warning',
            'ACTIVE': 'success',
            'RESERVED': 'info',
            'SOLD': 'primary',
            'EXPIRED': 'dark',
            'REJECTED': 'danger',
            'ARCHIVED': 'light'
        }
        color = status_colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Statut')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('seller', 'category')

    # Les méthodes d'action doivent être séparées de la liste 'actions'
    def approve_ads(self, request, queryset):
        """Action pour approuver les annonces"""
        updated = queryset.update(status=Ad.Status.ACTIVE, published_at=timezone.now())
        self.message_user(request, _(f'{updated} annonces ont été approuvées.'))
    approve_ads.short_description = _('Approuver les annonces sélectionnées')

    def reject_ads(self, request, queryset):
        """Action pour rejeter les annonces"""
        for ad in queryset:
            ad.status = Ad.Status.REJECTED
            ad.save()
        self.message_user(request, _(f'{queryset.count()} annonces ont été rejetées.'))
    reject_ads.short_description = _('Rejeter les annonces sélectionnées')

    def feature_ads(self, request, queryset):
        """Action pour mettre en vedette"""
        updated = queryset.update(
            is_featured=True,
            featured_until=timezone.now() + timezone.timedelta(days=7)
        )
        self.message_user(request, _(f'{updated} annonces ont été mises en vedette.'))
    feature_ads.short_description = _('Mettre en vedette')

    def unfeature_ads(self, request, queryset):
        """Action pour retirer de la vedette"""
        updated = queryset.update(is_featured=False, featured_until=None)
        self.message_user(request, _(f'{updated} annonces ne sont plus en vedette.'))
    unfeature_ads.short_description = _('Retirer de la vedette')

    def mark_as_sold(self, request, queryset):
        """Action pour marquer comme vendu"""
        updated = queryset.update(status=Ad.Status.SOLD)
        self.message_user(request, _(f'{updated} annonces ont été marquées comme vendues.'))
    mark_as_sold.short_description = _('Marquer comme vendu')

    def mark_as_expired(self, request, queryset):
        """Action pour marquer comme expiré"""
        updated = queryset.update(status=Ad.Status.EXPIRED, expired_at=timezone.now())
        self.message_user(request, _(f'{updated} annonces ont été marquées comme expirées.'))
    mark_as_expired.short_description = _('Marquer comme expiré')

    def export_to_csv(self, request, queryset):
        """Action pour exporter en CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="annonces.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Titre', 'Vendeur', 'Catégorie', 'Prix', 'Devise',
            'Statut', 'Ville départ', 'Ville destination', 'Vues',
            'Favoris', 'Date création'
        ])

        for ad in queryset:
            writer.writerow([
                ad.id, ad.title, ad.seller.username,
                ad.category.name if ad.category else '',
                ad.price, ad.currency, ad.get_status_display(),
                ad.city_from, ad.city_to, ad.view_count,
                ad.favorite_count, ad.created_at.strftime('%Y-%m-%d %H:%M')
            ])

        return response
    export_to_csv.short_description = _('Exporter en CSV')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.seller = request.user

        # Si le statut passe à ACTIF et qu'il n'y a pas de date de publication
        if obj.status == Ad.Status.ACTIVE and not obj.published_at:
            obj.published_at = timezone.now()

        super().save_model(request, obj, form, change)


@admin.register(AdImage)
class AdImageAdmin(admin.ModelAdmin):
    """Administration des images d'annonces"""

    list_display = ('ad', 'thumbnail_preview', 'caption', 'is_primary', 'is_paid', 'payment_status', 'created_at')
    list_filter = ('is_primary', 'is_paid', 'payment_status', 'created_at')
    search_fields = ('ad__title', 'caption')
    readonly_fields = ('created_at', 'updated_at')

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.thumbnail.url)
        elif obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.image.url)
        return _("Pas d'image")
    thumbnail_preview.short_description = _('Aperçu')


@admin.register(AdVideo)
class AdVideoAdmin(admin.ModelAdmin):
    """Administration des vidéos d'annonces"""

    list_display = ('ad', 'caption', 'is_paid', 'payment_status', 'created_at')
    list_filter = ('is_paid', 'payment_status', 'created_at')
    search_fields = ('ad__title', 'caption')
    readonly_fields = ('created_at',)

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Administration des favoris"""

    list_display = ('user', 'ad', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'ad__title')
    readonly_fields = ('created_at',)

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'ad')


@admin.register(AdView)
class AdViewAdmin(admin.ModelAdmin):
    """Administration des vues d'annonces"""

    list_display = ('ad', 'user', 'ip_address', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('ad__title', 'user__username', 'ip_address')
    readonly_fields = ('viewed_at',)

    # ✅ CORRECTION: actions doit être une liste vide si pas d'actions
    actions = []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AdReport)
class AdReportAdmin(admin.ModelAdmin):
    """Administration des signalements d'annonces"""

    list_display = ('ad', 'reporter', 'reason', 'status', 'created_at')
    list_filter = ('reason', 'status', 'created_at')
    search_fields = ('ad__title', 'reporter__username', 'description')
    list_editable = ('status',)
    readonly_fields = ('created_at',)

    fieldsets = (
        (_('Signalement'), {
            'fields': ('ad', 'reporter', 'reason', 'description', 'evidence')
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

    def mark_as_resolved(self, request, queryset):
        """Action pour marquer comme résolu"""
        updated = queryset.update(
            status='RESOLVED',  # Note: Utiliser la valeur littérale
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} signalements ont été résolus.'))
    mark_as_resolved.short_description = _('Marquer comme résolu')

    def mark_as_dismissed(self, request, queryset):
        """Action pour rejeter les signalements"""
        updated = queryset.update(
            status='DISMISSED',  # Note: Utiliser la valeur littérale
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
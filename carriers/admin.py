# ~/ebi3/carriers/admin.py
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import (
    Carrier, CarrierRoute, CarrierDocument,
    CarrierReview, CarrierAvailability, CarrierNotification
)

@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    """Administration des transporteurs"""

    # ✅ CORRECTION : 'actions' doit être une LISTE de noms de méthodes
    actions = ['approve_carriers', 'reject_carriers', 'suspend_carriers']

    list_display = (
        'user', 'company_name', 'carrier_type', 'status',
        'verification_level', 'vehicle_type', 'is_available',
        'average_rating', 'created_at'
    )

    list_filter = (
        'status', 'carrier_type', 'vehicle_type',
        'is_available', 'verification_level', 'created_at'
    )

    search_fields = (
        'user__username', 'user__email', 'company_name',
        'company_registration', 'vehicle_make', 'vehicle_model'
    )

    readonly_fields = (
        'created_at', 'updated_at', 'approved_at',
        'verified_at', 'average_rating', 'total_reviews',
        'total_missions', 'completed_missions', 'success_rate'
    )

    fieldsets = (
        (_('Informations utilisateur'), {
            'fields': ('user', 'carrier_type', 'status')
        }),
        (_('Informations professionnelles'), {
            'fields': (
                'company_name', 'company_registration', 'tax_id',
                'company_address'
            ),
            'classes': ('collapse',)
        }),
        (_('Véhicule'), {
            'fields': (
                'vehicle_type', 'vehicle_make', 'vehicle_model',
                'vehicle_year', 'vehicle_registration'
            )
        }),
        (_('Capacités'), {
            'fields': (
                'max_weight', 'max_volume',
                'max_length', 'max_width', 'max_height'
            )
        }),
        (_('Services'), {
            'fields': (
                'provides_packaging', 'provides_insurance',
                'provides_loading', 'provides_unloading'
            )
        }),
        (_('Tarification'), {
            'fields': ('base_price_per_km', 'min_price', 'currency')
        }),
        (_('Disponibilité'), {
            'fields': ('is_available', 'available_from', 'available_until')
        }),
        (_('Vérification'), {
            'fields': (
                'verification_level', 'verified_at',
                'rejection_reason'
            )
        }),
        (_('Statistiques'), {
            'fields': (
                'total_missions', 'completed_missions',
                'success_rate', 'average_rating', 'total_reviews'
            ),
            'classes': ('collapse',)
        }),
        (_('Documents'), {
            'fields': (
                'registration_certificate', 'insurance_certificate',
                'operator_license'
            ),
            'classes': ('collapse',)
        }),
        (_('Métadonnées'), {
            'fields': ('created_at', 'updated_at', 'approved_at'),
            'classes': ('collapse',)
        }),
    )

    # ✅ Les méthodes d'action doivent être définies séparément
    def approve_carriers(self, request, queryset):
        updated = queryset.update(
            status='APPROVED',
            approved_at=timezone.now(),
            verified_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} transporteurs ont été approuvés.'))
    approve_carriers.short_description = _('Approuver les transporteurs sélectionnés')

    def reject_carriers(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        self.message_user(request, _(f'{updated} transporteurs ont été rejetés.'))
    reject_carriers.short_description = _('Rejeter les transporteurs sélectionnés')

    def suspend_carriers(self, request, queryset):
        updated = queryset.update(status='SUSPENDED')
        self.message_user(request, _(f'{updated} transporteurs ont été suspendus.'))
    suspend_carriers.short_description = _('Suspendre les transporteurs sélectionnés')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(CarrierRoute)
class CarrierRouteAdmin(admin.ModelAdmin):
    """Administration des routes de transporteurs"""

    list_display = (
        'carrier', 'start_city', 'end_city',
        'departure_date', 'arrival_date', 'is_active',
        'available_weight', 'available_volume', 'is_full'
    )

    list_filter = ('is_active', 'is_full', 'frequency', 'departure_date')
    search_fields = ('carrier__user__username', 'start_city', 'end_city')
    date_hierarchy = 'departure_date'

    # ✅ AJOUT: actions doit être défini (liste vide si pas d'actions)
    actions = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('carrier', 'carrier__user')


@admin.register(CarrierDocument)
class CarrierDocumentAdmin(admin.ModelAdmin):
    """Administration des documents de transporteurs"""

    list_display = (
        'carrier', 'document_type', 'is_verified',
        'verified_at', 'expiry_date', 'created_at'
    )

    list_filter = ('document_type', 'is_verified', 'created_at')
    search_fields = ('carrier__user__username', 'description')
    readonly_fields = ('created_at', 'updated_at', 'verified_at')

    # ✅ AJOUT: actions doit être défini (liste vide si pas d'actions)
    actions = []

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('carrier', 'carrier__user', 'verified_by')


@admin.register(CarrierReview)
class CarrierReviewAdmin(admin.ModelAdmin):
    """Administration des avis sur transporteurs"""

    list_display = (
        'carrier', 'reviewer', 'rating', 'title',
        'is_approved', 'is_visible', 'created_at'
    )

    list_filter = ('is_approved', 'is_visible', 'rating', 'created_at')
    search_fields = ('carrier__user__username', 'reviewer__username', 'title', 'comment')
    list_editable = ('is_approved', 'is_visible')
    readonly_fields = ('created_at', 'updated_at')

    # ✅ AJOUT: actions doit être défini comme une liste
    actions = ['approve_reviews', 'reject_reviews']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('carrier', 'carrier__user', 'reviewer')

    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, _(f'{updated} avis ont été approuvés.'))
    approve_reviews.short_description = _('Approuver les avis sélectionnés')

    def reject_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False, is_visible=False)
        self.message_user(request, _(f'{updated} avis ont été rejetés.'))
    reject_reviews.short_description = _('Rejeter les avis sélectionnés')


# Enregistrement simplifié pour les autres modèles
@admin.register(CarrierAvailability)
class CarrierAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('carrier', 'start_datetime', 'end_datetime', 'is_booked')
    list_filter = ('is_booked', 'start_datetime')
    search_fields = ('carrier__user__username', 'notes')

    # ✅ AJOUT: actions doit être défini (liste vide si pas d'actions)
    actions = []


@admin.register(CarrierNotification)
class CarrierNotificationAdmin(admin.ModelAdmin):
    list_display = ('carrier', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_important', 'created_at')
    search_fields = ('carrier__user__username', 'title', 'message')
    readonly_fields = ('created_at',)

    # ✅ AJOUT: actions doit être défini (liste vide si pas d'actions)
    actions = []

    def has_add_permission(self, request):
        return False
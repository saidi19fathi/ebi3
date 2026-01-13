# ~/ebi3/carriers/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models import (
    Carrier, CarrierRoute, Mission, CollectionDay,
    CarrierDocument, FinancialTransaction, CarrierReview,
    CarrierOffer, CarrierAvailability, CarrierNotification,
    CarrierStatistics, ExpenseReport
)


@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    """Admin pour les transporteurs - Version corrigée pour les nouveaux noms de champs"""

    list_display = [
        'id', 'user_display', 'carrier_type', 'status',
        'verification_level', 'vehicle_type', 'transport_is_available_display',
        'transport_average_rating_display', 'created_at'
    ]

    list_filter = [
        'status', 'carrier_type', 'vehicle_type',
        'transport_is_available', 'created_at'
    ]

    search_fields = [
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'transport_company_name', 'vehicle_registration'
    ]

    readonly_fields = [
        'created_at', 'updated_at', 'approved_at', 'verified_at',
        'total_transport_missions', 'completed_transport_missions',
        'transport_success_rate', 'transport_average_rating',
        'transport_total_reviews', 'user_info_display'
    ]

    fieldsets = (
        (_("Informations utilisateur"), {
            'fields': ('user_info_display', 'status', 'verification_level')
        }),
        (_("Informations professionnelles"), {
            'fields': (
                'carrier_type', 'transport_company_name', 'transport_company_registration',
                'transport_tax_id', 'transport_company_address'
            )
        }),
        (_("Profil et documents"), {
            'fields': (
                'profile_photo_display', 'id_front_display', 'id_back_display',
                'vehicle_registration_certificate', 'transport_insurance_certificate',
                'transport_operator_license'
            )
        }),
        (_("Véhicule"), {
            'fields': (
                'vehicle_type', 'vehicle_make', 'vehicle_model',
                'vehicle_year', 'vehicle_registration',
                'vehicle_photo_front_display', 'vehicle_photo_back_display',
                'vehicle_photo_side_display'
            )
        }),
        (_("Capacités"), {
            'fields': (
                'max_weight', 'max_volume', 'max_length',
                'max_width', 'max_height'
            )
        }),
        (_("Zones de couverture"), {
            'fields': ('coverage_countries', 'coverage_cities')
        }),
        (_("Types de marchandises"), {
            'fields': ('accepted_merchandise_types_display', 'custom_merchandise_types')
        }),
        (_("Services et tarifs"), {
            'fields': (
                'provides_packaging', 'provides_insurance',
                'provides_loading', 'provides_unloading',
                'base_price_per_km', 'min_price', 'currency'
            )
        }),
        (_("Disponibilité"), {
            'fields': (
                'transport_is_available', 'transport_available_from', 'transport_available_until',
                'transport_weekly_schedule_display'
            )
        }),
        (_("Sécurité et conformité"), {
            'fields': (
                'rgpd_consent', 'terms_accepted'
            )
        }),
        (_("Statistiques transport"), {
            'fields': (
                'total_transport_missions', 'completed_transport_missions',
                'transport_success_rate', 'transport_average_rating',
                'transport_total_reviews'
            )
        }),
        (_("Métadonnées"), {
            'fields': ('created_at', 'updated_at', 'approved_at', 'verified_at')
        }),
    )

    actions = ['approve_carriers', 'reject_carriers', 'verify_documents']

    def user_display(self, obj):
        """Affiche l'utilisateur avec lien"""
        url = reverse("admin:users_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user)
    user_display.short_description = _("Utilisateur")

    def user_info_display(self, obj):
        """Affiche les informations utilisateur"""
        if obj.user:
            return format_html(
                '<strong>Utilisateur:</strong> <a href="{}">{}</a><br>'
                '<strong>Email:</strong> {}<br>'
                '<strong>Téléphone:</strong> {}<br>'
                '<strong>Rôle:</strong> {}',
                reverse("admin:users_user_change", args=[obj.user.id]),
                obj.user.get_full_name() or obj.user.username,
                obj.user.email,
                obj.user.phone,
                obj.user.get_role_display()
            )
        return _("Aucun utilisateur associé")
    user_info_display.short_description = _("Informations utilisateur")

    def profile_photo_display(self, obj):
        """Affiche la photo de profil"""
        if obj.profile_photo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.profile_photo.url
            )
        return _("Aucune photo")
    profile_photo_display.short_description = _("Photo de profil")

    def id_front_display(self, obj):
        """Affiche le recto de la pièce d'identité"""
        if obj.id_front:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.id_front.url
            )
        return _("Non fourni")
    id_front_display.short_description = _("Recto pièce d'identité")

    def id_back_display(self, obj):
        """Affiche le verso de la pièce d'identité"""
        if obj.id_back:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.id_back.url
            )
        return _("Non fourni")
    id_back_display.short_description = _("Verso pièce d'identité")

    def vehicle_photo_front_display(self, obj):
        """Affiche la photo avant du véhicule"""
        if obj.vehicle_photo_front:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.vehicle_photo_front.url
            )
        return _("Non fournie")
    vehicle_photo_front_display.short_description = _("Photo avant véhicule")

    def vehicle_photo_back_display(self, obj):
        """Affiche la photo arrière du véhicule"""
        if obj.vehicle_photo_back:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.vehicle_photo_back.url
            )
        return _("Non fournie")
    vehicle_photo_back_display.short_description = _("Photo arrière véhicule")

    def vehicle_photo_side_display(self, obj):
        """Affiche la photo côté du véhicule"""
        if obj.vehicle_photo_side:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 200px;" />',
                obj.vehicle_photo_side.url
            )
        return _("Non fournie")
    vehicle_photo_side_display.short_description = _("Photo côté véhicule")

    def accepted_merchandise_types_display(self, obj):
        """Affiche les types de marchandises acceptés"""
        if obj.accepted_merchandise_types:
            types = []
            for code, label in MerchandiseTypes.STANDARD:
                if code in obj.accepted_merchandise_types:
                    types.append(label)

            if obj.custom_merchandise_types:
                custom_types = [t.strip() for t in obj.custom_merchandise_types.split(',') if t.strip()]
                types.extend(custom_types)

            return ', '.join(types) if types else _("Aucun type spécifié")
        return _("Aucun type spécifié")
    accepted_merchandise_types_display.short_description = _("Types de marchandises acceptés")

    def transport_weekly_schedule_display(self, obj):
        """Affiche l'emploi du temps hebdomadaire"""
        if obj.transport_weekly_schedule and isinstance(obj.transport_weekly_schedule, dict):
            days_mapping = {
                'monday': _('Lundi'),
                'tuesday': _('Mardi'),
                'wednesday': _('Mercredi'),
                'thursday': _('Jeudi'),
                'friday': _('Vendredi'),
                'saturday': _('Samedi'),
                'sunday': _('Dimanche')
            }

            schedule_text = []
            for day_en, details in obj.transport_weekly_schedule.items():
                if details.get('available', False) and 'start' in details and 'end' in details:
                    day_fr = days_mapping.get(day_en, day_en.capitalize())
                    start = details['start'].replace(':', 'h')
                    end = details['end'].replace(':', 'h')
                    schedule_text.append(f"{day_fr}: {start}-{end}")

            return '<br>'.join(schedule_text) if schedule_text else _("Non défini")
        return _("Non défini")
    transport_weekly_schedule_display.short_description = _("Emploi du temps")
    transport_weekly_schedule_display.allow_tags = True

    def transport_is_available_display(self, obj):
        """Affiche la disponibilité avec une icône"""
        if obj.transport_is_available:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                _("Disponible")
            )
        return format_html(
            '<span style="color: red;">✗ {}</span>',
            _("Indisponible")
        )
    transport_is_available_display.short_description = _("Disponible")

    def transport_average_rating_display(self, obj):
        """Affiche la note moyenne avec des étoiles"""
        stars = '★' * int(obj.transport_average_rating)
        half_star = '½' if obj.transport_average_rating % 1 >= 0.5 else ''
        empty_stars = '☆' * (5 - int(obj.transport_average_rating) - (1 if half_star else 0))

        return format_html(
            '<span style="color: gold; font-size: 14px;">{}{}{}</span> '
            '<span>({:.1f}/5)</span>',
            stars, half_star, empty_stars, obj.transport_average_rating
        )
    transport_average_rating_display.short_description = _("Note")

    def approve_carriers(self, request, queryset):
        """Approuver les transporteurs sélectionnés"""
        updated = queryset.update(status=Carrier.Status.APPROVED)
        self.message_user(
            request,
            _("{} transporteurs approuvés avec succès.").format(updated),
            messages.SUCCESS
        )
    approve_carriers.short_description = _("Approuver les transporteurs sélectionnés")

    def reject_carriers(self, request, queryset):
        """Rejeter les transporteurs sélectionnés"""
        for carrier in queryset:
            carrier.status = Carrier.Status.REJECTED
            carrier.save()
        self.message_user(
            request,
            _("{} transporteurs rejetés.").format(queryset.count()),
            messages.WARNING
        )
    reject_carriers.short_description = _("Rejeter les transporteurs sélectionnés")

    def verify_documents(self, request, queryset):
        """Vérifier les documents des transporteurs"""
        for carrier in queryset:
            if carrier.verification_level < 3:
                carrier.verification_level = 3
                carrier.save()
        self.message_user(
            request,
            _("Documents vérifiés pour {} transporteurs.").format(queryset.count()),
            messages.SUCCESS
        )
    verify_documents.short_description = _("Vérifier les documents")


@admin.register(CarrierRoute)
class CarrierRouteAdmin(admin.ModelAdmin):
    """Admin pour les routes"""

    list_display = [
        'id', 'carrier_link', 'start_city', 'end_city',
        'departure_date', 'is_active', 'is_full'
    ]

    list_filter = ['is_active', 'is_full', 'frequency', 'departure_date']

    search_fields = [
        'carrier__user__username', 'start_city', 'end_city',
        'start_country', 'end_country'
    ]

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
        return format_html('<a href="{}">{}</a>', url, obj.carrier)
    carrier_link.short_description = _("Transporteur")


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    """Admin pour les missions"""

    list_display = [
        'mission_number', 'carrier_link', 'sender_link', 'status_display',
        'priority_display', 'preferred_pickup_date', 'agreed_price_display'
    ]

    list_filter = ['status', 'priority', 'preferred_pickup_date']

    search_fields = [
        'mission_number', 'carrier__user__username',
        'sender__username', 'recipient_name'
    ]

    readonly_fields = ['mission_number', 'created_at', 'updated_at']

    fieldsets = (
        (_("Informations générales"), {
            'fields': ('mission_number', 'carrier_link', 'sender_link', 'status', 'priority')
        }),
        (_("Expédition"), {
            'fields': (
                'sender_address', 'sender_phone',
                'recipient_name', 'recipient_address', 'recipient_phone'
            )
        }),
        (_("Marchandise"), {
            'fields': (
                'merchandise_type', 'custom_merchandise_type',
                'description', 'weight', 'length', 'width', 'height',
                'is_fragile', 'requires_special_handling'
            )
        }),
        (_("Organisation"), {
            'fields': ('collection_order', 'position_in_vehicle')
        }),
        (_("Dates"), {
            'fields': (
                'preferred_pickup_date', 'preferred_delivery_date',
                'actual_pickup_date', 'actual_delivery_date'
            )
        }),
        (_("Finances"), {
            'fields': ('agreed_price', 'currency')
        }),
        (_("Livraison"), {
            'fields': (
                'delivery_proof_photo', 'recipient_signature',
                'delivery_notes'
            )
        }),
        (_("Incidents"), {
            'fields': (
                'has_incident', 'incident_description',
                'incident_resolved', 'delay_reason', 'delay_duration'
            )
        }),
        (_("Suivi"), {
            'fields': ('current_location', 'last_location_update')
        }),
        (_("Métadonnées"), {
            'fields': ('created_at', 'updated_at', 'accepted_at', 'completed_at')
        }),
    )

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def sender_link(self, obj):
        """Lien vers l'expéditeur"""
        if obj.sender:
            url = reverse("admin:users_user_change", args=[obj.sender.id])
            return format_html('<a href="{}">{}</a>', url, obj.sender)
        return "-"
    sender_link.short_description = _("Expéditeur")

    def status_display(self, obj):
        """Affiche le statut avec couleur"""
        colors = {
            'PENDING': 'orange',
            'ACCEPTED': 'blue',
            'COLLECTING': 'purple',
            'IN_TRANSIT': 'teal',
            'DELIVERING': 'cyan',
            'DELIVERED': 'green',
            'CANCELLED': 'red',
            'PROBLEM': 'darkred',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = _("Statut")

    def priority_display(self, obj):
        """Affiche la priorité avec couleur"""
        colors = {
            'LOW': 'gray',
            'MEDIUM': 'blue',
            'HIGH': 'orange',
            'URGENT': 'red',
        }
        color = colors.get(obj.priority, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_display.short_description = _("Priorité")

    def agreed_price_display(self, obj):
        """Affiche le prix avec devise"""
        return f"{obj.agreed_price} {obj.currency}"
    agreed_price_display.short_description = _("Prix")


@admin.register(CollectionDay)
class CollectionDayAdmin(admin.ModelAdmin):
    """Admin pour les jours de collecte"""

    list_display = [
        'id', 'carrier_link', 'date', 'is_scheduled_display', 'is_completed_display',
        'planned_total_weight', 'planned_total_volume'
    ]

    list_filter = ['is_scheduled', 'is_completed', 'date']

    search_fields = ['carrier__user__username']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def is_scheduled_display(self, obj):
        """Affiche le statut de planification"""
        if obj.is_scheduled:
            return format_html('<span style="color: green;">✓ {}</span>', _("Planifié"))
        return format_html('<span style="color: orange;">✗ {}</span>', _("Non planifié"))
    is_scheduled_display.short_description = _("Planifié")

    def is_completed_display(self, obj):
        """Affiche le statut de complétion"""
        if obj.is_completed:
            return format_html('<span style="color: green;">✓ {}</span>', _("Terminé"))
        return format_html('<span style="color: blue;">○ {}</span>', _("En cours"))
    is_completed_display.short_description = _("Terminé")


@admin.register(CarrierDocument)
class CarrierDocumentAdmin(admin.ModelAdmin):
    """Admin pour les documents"""

    list_display = [
        'id', 'carrier_link', 'document_type', 'is_verified_display',
        'expiry_date_display', 'created_at'
    ]

    list_filter = ['document_type', 'is_verified', 'is_customs_document']

    search_fields = ['carrier__user__username', 'description']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def is_verified_display(self, obj):
        """Affiche l'état de vérification"""
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ {}</span>', _("Vérifié"))
        return format_html('<span style="color: orange;">○ {}</span>', _("En attente"))
    is_verified_display.short_description = _("Vérifié")

    def expiry_date_display(self, obj):
        """Affiche la date d'expiration avec couleur"""
        if obj.expiry_date:
            from django.utils import timezone
            today = timezone.now().date()

            if obj.expiry_date < today:
                return format_html(
                    '<span style="color: red; font-weight: bold;">{} ({})</span>',
                    obj.expiry_date, _("Expiré")
                )
            elif (obj.expiry_date - today).days <= 30:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">{} ({})</span>',
                    obj.expiry_date, _("Bientôt expiré")
                )
            else:
                return format_html(
                    '<span style="color: green;">{}</span>',
                    obj.expiry_date
                )
        return _("Pas d'expiration")
    expiry_date_display.short_description = _("Date d'expiration")


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    """Admin pour les transactions financières"""

    list_display = [
        'id', 'carrier_link', 'transaction_type_display', 'amount_display',
        'currency', 'transaction_date', 'is_completed_display'
    ]

    list_filter = ['transaction_type', 'is_completed', 'transaction_date']

    search_fields = [
        'carrier__user__username', 'receipt_number',
        'invoice_number', 'mission__mission_number'
    ]

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def transaction_type_display(self, obj):
        """Affiche le type de transaction avec couleur"""
        colors = {
            'PAYMENT': 'green',
            'EXPENSE': 'red',
            'REFUND': 'blue',
            'COMMISSION': 'purple',
            'BONUS': 'gold',
        }
        color = colors.get(obj.transaction_type, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_transaction_type_display()
        )
    transaction_type_display.short_description = _("Type")

    def amount_display(self, obj):
        """Affiche le montant avec couleur selon le type"""
        if obj.transaction_type == 'PAYMENT':
            color = 'green'
            prefix = '+'
        elif obj.transaction_type == 'EXPENSE':
            color = 'red'
            prefix = '-'
        else:
            color = 'blue'
            prefix = ''

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{} {}</span>',
            color, prefix, obj.amount, obj.currency
        )
    amount_display.short_description = _("Montant")

    def is_completed_display(self, obj):
        """Affiche l'état de complétion"""
        if obj.is_completed:
            return format_html('<span style="color: green;">✓ {}</span>', _("Terminé"))
        return format_html('<span style="color: orange;">○ {}</span>', _("En attente"))
    is_completed_display.short_description = _("Terminé")


@admin.register(CarrierReview)
class CarrierReviewAdmin(admin.ModelAdmin):
    """Admin pour les avis"""

    list_display = [
        'id', 'carrier_link', 'reviewer_link', 'rating_stars',
        'is_approved_display', 'is_visible_display', 'created_at'
    ]

    list_filter = ['is_approved', 'is_visible', 'rating', 'created_at']

    search_fields = [
        'carrier__user__username', 'reviewer__username',
        'title', 'comment'
    ]

    actions = ['approve_reviews', 'hide_reviews']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def reviewer_link(self, obj):
        """Lien vers le reviewer"""
        if obj.reviewer:
            url = reverse("admin:users_user_change", args=[obj.reviewer.id])
            return format_html('<a href="{}">{}</a>', url, obj.reviewer)
        return "-"
    reviewer_link.short_description = _("Auteur")

    def rating_stars(self, obj):
        """Affiche la note avec des étoiles"""
        stars = '★' * obj.rating
        empty_stars = '☆' * (5 - obj.rating)
        return format_html(
            '<span style="color: gold; font-size: 14px;">{}{}</span>',
            stars, empty_stars
        )
    rating_stars.short_description = _("Note")

    def is_approved_display(self, obj):
        """Affiche l'état d'approbation"""
        if obj.is_approved:
            return format_html('<span style="color: green;">✓ {}</span>', _("Approuvé"))
        return format_html('<span style="color: orange;">○ {}</span>', _("En attente"))
    is_approved_display.short_description = _("Approuvé")

    def is_visible_display(self, obj):
        """Affiche la visibilité"""
        if obj.is_visible:
            return format_html('<span style="color: green;">✓ {}</span>', _("Visible"))
        return format_html('<span style="color: red;">✗ {}</span>', _("Masqué"))
    is_visible_display.short_description = _("Visible")

    def approve_reviews(self, request, queryset):
        """Approuver les avis sélectionnés"""
        updated = queryset.update(is_approved=True)
        self.message_user(
            request,
            _("{} avis approuvés.").format(updated),
            messages.SUCCESS
        )
    approve_reviews.short_description = _("Approuver les avis")

    def hide_reviews(self, request, queryset):
        """Masquer les avis sélectionnés"""
        updated = queryset.update(is_visible=False)
        self.message_user(
            request,
            _("{} avis masqués.").format(updated),
            messages.WARNING
        )
    hide_reviews.short_description = _("Masquer les avis")


@admin.register(CarrierOffer)
class CarrierOfferAdmin(admin.ModelAdmin):
    """Admin pour les offres"""

    list_display = [
        'id', 'carrier_link', 'title', 'offer_type_display',
        'start_city', 'end_city', 'price_display', 'is_active_display',
        'is_booked_display', 'available_from'
    ]

    list_filter = ['offer_type', 'is_active', 'is_booked']

    search_fields = [
        'carrier__user__username', 'title',
        'start_city', 'end_city'
    ]

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def offer_type_display(self, obj):
        """Affiche le type d'offre"""
        colors = {
            'IMMEDIATE': 'green',
            'SCHEDULED': 'blue',
            'RECURRING': 'purple',
            'GROUPED': 'orange',
        }
        color = colors.get(obj.offer_type, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_offer_type_display()
        )
    offer_type_display.short_description = _("Type")

    def price_display(self, obj):
        """Affiche le prix"""
        return f"{obj.price} {obj.currency}"
    price_display.short_description = _("Prix")

    def is_active_display(self, obj):
        """Affiche l'état actif"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ {}</span>', _("Active"))
        return format_html('<span style="color: red;">✗ {}</span>', _("Inactive"))
    is_active_display.short_description = _("Active")

    def is_booked_display(self, obj):
        """Affiche l'état de réservation"""
        if obj.is_booked:
            return format_html('<span style="color: orange;">✓ {}</span>', _("Réservée"))
        return format_html('<span style="color: blue;">○ {}</span>', _("Disponible"))
    is_booked_display.short_description = _("Réservée")


@admin.register(CarrierAvailability)
class CarrierAvailabilityAdmin(admin.ModelAdmin):
    """Admin pour les disponibilités"""

    list_display = [
        'id', 'carrier_link', 'start_datetime',
        'end_datetime', 'is_booked_display'
    ]

    list_filter = ['is_booked', 'start_datetime']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def is_booked_display(self, obj):
        """Affiche l'état de réservation"""
        if obj.is_booked:
            return format_html('<span style="color: orange;">✓ {}</span>', _("Réservé"))
        return format_html('<span style="color: green;">○ {}</span>', _("Disponible"))
    is_booked_display.short_description = _("Réservé")


@admin.register(CarrierNotification)
class CarrierNotificationAdmin(admin.ModelAdmin):
    """Admin pour les notifications"""

    list_display = [
        'id', 'carrier_link', 'notification_type_display',
        'title', 'is_read_display', 'created_at'
    ]

    list_filter = ['notification_type', 'is_read', 'created_at']

    search_fields = ['carrier__user__username', 'title', 'message']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def notification_type_display(self, obj):
        """Affiche le type de notification"""
        colors = {
            'NEW_MISSION': 'green',
            'MISSION_UPDATE': 'blue',
            'PAYMENT_RECEIVED': 'gold',
            'REVIEW_RECEIVED': 'purple',
            'DOCUMENT_VERIFIED': 'teal',
            'STATUS_CHANGED': 'orange',
            'SYSTEM': 'gray',
            'COLLECTION_DAY': 'cyan',
            'EXPENSE_ALERT': 'red',
            'DOCUMENT_EXPIRY': 'darkred',
            'ROUTE_OPTIMIZED': 'lime',
            'NEW_OFFER': 'pink',
        }
        color = colors.get(obj.notification_type, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_notification_type_display()
        )
    notification_type_display.short_description = _("Type")

    def is_read_display(self, obj):
        """Affiche l'état de lecture"""
        if obj.is_read:
            return format_html('<span style="color: gray;">✓ {}</span>', _("Lu"))
        return format_html('<span style="color: blue; font-weight: bold;">● {}</span>', _("Non lu"))
    is_read_display.short_description = _("Lu")


@admin.register(CarrierStatistics)
class CarrierStatisticsAdmin(admin.ModelAdmin):
    """Admin pour les statistiques"""

    list_display = [
        'carrier_link', 'delivery_success_rate_display',
        'on_time_rate_display', 'satisfaction_rate_display'
    ]

    search_fields = ['carrier__user__username']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def delivery_success_rate_display(self, obj):
        """Affiche le taux de réussite"""
        if obj.delivery_success_rate >= 90:
            color = 'green'
        elif obj.delivery_success_rate >= 70:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, obj.delivery_success_rate
        )
    delivery_success_rate_display.short_description = _("Succès livraison")

    def on_time_rate_display(self, obj):
        """Affiche le taux de ponctualité"""
        if obj.on_time_rate >= 90:
            color = 'green'
        elif obj.on_time_rate >= 70:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, obj.on_time_rate
        )
    on_time_rate_display.short_description = _("Ponctualité")

    def satisfaction_rate_display(self, obj):
        """Affiche le taux de satisfaction"""
        if obj.satisfaction_rate >= 90:
            color = 'green'
        elif obj.satisfaction_rate >= 70:
            color = 'orange'
        else:
            color = 'red'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, obj.satisfaction_rate
        )
    satisfaction_rate_display.short_description = _("Satisfaction")


@admin.register(ExpenseReport)
class ExpenseReportAdmin(admin.ModelAdmin):
    """Admin pour les rapports de dépenses"""

    list_display = [
        'id', 'carrier_link', 'period_start', 'period_end',
        'total_income_display', 'total_expenses_display', 'net_profit_display',
        'is_approved_display'
    ]

    list_filter = ['is_approved', 'period_start']

    search_fields = ['carrier__user__username']

    def carrier_link(self, obj):
        """Lien vers le transporteur"""
        if obj.carrier:
            url = reverse("admin:carriers_carrier_change", args=[obj.carrier.id])
            return format_html('<a href="{}">{}</a>', url, obj.carrier)
        return "-"
    carrier_link.short_description = _("Transporteur")

    def total_income_display(self, obj):
        """Affiche le total des revenus"""
        return format_html(
            '<span style="color: green; font-weight: bold;">{:.2f} €</span>',
            obj.total_income
        )
    total_income_display.short_description = _("Revenus")

    def total_expenses_display(self, obj):
        """Affiche le total des dépenses"""
        return format_html(
            '<span style="color: red; font-weight: bold;">{:.2f} €</span>',
            obj.total_expenses
        )
    total_expenses_display.short_description = _("Dépenses")

    def net_profit_display(self, obj):
        """Affiche le bénéfice net"""
        if obj.net_profit >= 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">+{:.2f} €</span>',
                obj.net_profit
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">{:.2f} €</span>',
                obj.net_profit
            )
    net_profit_display.short_description = _("Bénéfice net")

    def is_approved_display(self, obj):
        """Affiche l'état d'approbation"""
        if obj.is_approved:
            return format_html('<span style="color: green;">✓ {}</span>', _("Approuvé"))
        return format_html('<span style="color: orange;">○ {}</span>', _("En attente"))
    is_approved_display.short_description = _("Approuvé")
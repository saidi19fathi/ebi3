# ~/ebi3/logistics/models.py

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Import des apps existantes
from ads.models import Ad
from carriers.models import Carrier  # CORRECTION: Carrier au lieu de CarrierProfile
from core.models import Country, City


class LogisticsOption(models.TextChoices):
    """Options logistiques disponibles"""
    P2P_DIRECT = 'P2P_DIRECT', _('Direct entre particuliers')
    WITH_CARRIER = 'WITH_CARRIER', _('Avec transporteur')
    WITH_EXPAT_CARRIER = 'WITH_EXPAT_CARRIER', _('Avec expatrié-transporteur')


class ReservationStatus(models.TextChoices):
    """Statuts d'une réservation"""
    PENDING = 'PENDING', _('En attente')
    CONFIRMED = 'CONFIRMED', _('Confirmée')
    PAYMENT_PENDING = 'PAYMENT_PENDING', _('Paiement en attente')
    PAID = 'PAID', _('Payée')
    IN_TRANSIT = 'IN_TRANSIT', _('En transit')
    DELIVERED = 'DELIVERED', _('Livrée')
    CANCELLED = 'CANCELLED', _('Annulée')
    DISPUTED = 'DISPUTED', _('En litige')
    REFUNDED = 'REFUNDED', _('Remboursée')


class Reservation(models.Model):
    """
    Réservation d'une annonce avec option logistique
    """
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name=_('Annonce')
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name=_('Acheteur')
    )
    carrier = models.ForeignKey(
        Carrier,  # CORRECTION: Carrier au lieu de CarrierProfile
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logistics_routes',
        verbose_name=_('Transporteur')
    )

    # Informations logistiques
    logistics_option = models.CharField(
        max_length=20,
        choices=LogisticsOption.choices,
        verbose_name=_('Option logistique')
    )
    pickup_address = models.TextField(
        verbose_name=_('Adresse de prise en charge'),
        blank=True
    )
    delivery_address = models.TextField(
        verbose_name=_('Adresse de livraison'),
        blank=True
    )

    # Dates
    pickup_date = models.DateField(
        verbose_name=_('Date de prise en charge'),
        null=True,
        blank=True
    )
    delivery_date = models.DateField(
        verbose_name=_('Date de livraison estimée'),
        null=True,
        blank=True
    )
    actual_delivery_date = models.DateField(
        verbose_name=_('Date de livraison réelle'),
        null=True,
        blank=True
    )

    # Prix et paiement
    price_agreed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Prix convenu'),
        validators=[MinValueValidator(0)]
    )
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Coût du transport'),
        default=0,
        validators=[MinValueValidator(0)]
    )
    insurance_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Coût assurance'),
        default=0,
        validators=[MinValueValidator(0)]
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Prix total'),
        validators=[MinValueValidator(0)]
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
        verbose_name=_('Statut')
    )

    # Suivi
    tracking_number = models.CharField(
        max_length=100,
        verbose_name=_('Numéro de suivi'),
        blank=True
    )

    # Paiement
    is_paid = models.BooleanField(
        default=False,
        verbose_name=_('Payé')
    )
    payment_method = models.CharField(
        max_length=50,
        verbose_name=_('Méthode de paiement'),
        blank=True
    )
    payment_date = models.DateTimeField(
        verbose_name=_('Date de paiement'),
        null=True,
        blank=True
    )
    payment_reference = models.CharField(
        max_length=100,
        verbose_name=_('Référence paiement'),
        blank=True
    )

    # Assurance
    requires_insurance = models.BooleanField(
        default=False,
        verbose_name=_('Assurance requise')
    )
    insurance_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Valeur assurée'),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    # Emballage
    requires_packaging = models.BooleanField(
        default=False,
        verbose_name=_('Emballage requis')
    )
    packaging_details = models.TextField(
        verbose_name=_('Détails emballage'),
        blank=True
    )

    # Notes
    buyer_notes = models.TextField(
        verbose_name=_('Notes acheteur'),
        blank=True
    )
    seller_notes = models.TextField(
        verbose_name=_('Notes vendeur'),
        blank=True
    )
    carrier_notes = models.TextField(
        verbose_name=_('Notes transporteur'),
        blank=True
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date de création')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Date de modification')
    )
    cancelled_at = models.DateTimeField(
        verbose_name=_('Date d\'annulation'),
        null=True,
        blank=True
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_reservations',
        verbose_name=_('Annulé par')
    )
    cancellation_reason = models.TextField(
        verbose_name=_('Raison annulation'),
        blank=True
    )

    class Meta:
        verbose_name = _('Réservation')
        verbose_name_plural = _('Réservations')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['ad', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Réservation #{self.id} - {self.ad.title}"

    def clean(self):
        """Validation personnalisée"""
        super().clean()

        # Vérifier que l'acheteur n'est pas le vendeur
        if self.buyer == self.ad.seller:
            raise ValidationError(_("Vous ne pouvez pas réserver votre propre annonce."))

        # Vérifier la date de livraison
        if self.delivery_date and self.pickup_date:
            if self.delivery_date < self.pickup_date:
                raise ValidationError(_("La date de livraison doit être après la date de prise en charge."))

        # Vérifier l'option logistique
        if self.logistics_option == LogisticsOption.WITH_CARRIER and not self.carrier:
            raise ValidationError(_("Une option avec transporteur nécessite un transporteur."))

        # Calcul du prix total
        self.total_price = self.price_agreed + self.shipping_cost + self.insurance_cost

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('logistics:reservation_detail', kwargs={'pk': self.pk})

    @property
    def can_be_cancelled(self):
        """Vérifie si la réservation peut être annulée"""
        cancellable_statuses = [
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.PAYMENT_PENDING
        ]
        return self.status in cancellable_statuses

    @property
    def is_active(self):
        """Vérifie si la réservation est active"""
        active_statuses = [
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.PAYMENT_PENDING,
            ReservationStatus.PAID,
            ReservationStatus.IN_TRANSIT
        ]
        return self.status in active_statuses

    @property
    def days_since_creation(self):
        """Nombre de jours depuis la création"""
        return (timezone.now() - self.created_at).days


class MissionStatus(models.TextChoices):
    """Statuts d'une mission de transport"""
    SCHEDULED = 'SCHEDULED', _('Planifiée')
    PICKUP_PENDING = 'PICKUP_PENDING', _('En attente de prise en charge')
    PICKED_UP = 'PICKED_UP', _('Pris en charge')
    IN_TRANSIT = 'IN_TRANSIT', _('En transit')
    AT_HUB = 'AT_HUB', _('Au centre de tri')
    OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('En cours de livraison')
    DELIVERY_PENDING = 'DELIVERY_PENDING', _('En attente de livraison')
    DELIVERED = 'DELIVERED', _('Livrée')
    CANCELLED = 'CANCELLED', _('Annulée')
    DELAYED = 'DELAYED', _('Retardée')


class Mission(models.Model):
    """
    Mission de transport pour une réservation
    """
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name='mission',
        verbose_name=_('Réservation')
    )
    carrier = models.ForeignKey(
        Carrier,  # CORRECTION: Carrier au lieu de CarrierProfile
        on_delete=models.CASCADE,
        related_name='missions',
        verbose_name=_('Transporteur')
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=MissionStatus.choices,
        default=MissionStatus.SCHEDULED,
        verbose_name=_('Statut')
    )

    # Localisation
    current_location = models.CharField(
        max_length=200,
        verbose_name=_('Localisation actuelle'),
        blank=True
    )
    latitude = models.FloatField(
        verbose_name=_('Latitude'),
        null=True,
        blank=True
    )
    longitude = models.FloatField(
        verbose_name=_('Longitude'),
        null=True,
        blank=True
    )

    # Dates
    scheduled_pickup = models.DateTimeField(
        verbose_name=_('Prise en charge planifiée'),
        null=True,
        blank=True
    )
    actual_pickup = models.DateTimeField(
        verbose_name=_('Prise en charge réelle'),
        null=True,
        blank=True
    )
    estimated_delivery = models.DateTimeField(
        verbose_name=_('Livraison estimée'),
        null=True,
        blank=True
    )
    actual_delivery = models.DateTimeField(
        verbose_name=_('Livraison réelle'),
        null=True,
        blank=True
    )

    # Distance
    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Distance (km)'),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    # Documents
    pickup_confirmation = models.FileField(
        upload_to='missions/pickup_confirmations/',
        verbose_name=_('Confirmation prise en charge'),
        null=True,
        blank=True
    )
    delivery_confirmation = models.FileField(
        upload_to='missions/delivery_confirmations/',
        verbose_name=_('Confirmation livraison'),
        null=True,
        blank=True
    )

    # Notes
    notes = models.TextField(
        verbose_name=_('Notes'),
        blank=True
    )
    delay_reason = models.TextField(
        verbose_name=_('Raison du retard'),
        blank=True
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date de création')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Date de modification')
    )

    class Meta:
        verbose_name = _('Mission')
        verbose_name_plural = _('Missions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['carrier', 'status']),
            models.Index(fields=['estimated_delivery']),
        ]

    def __str__(self):
        return f"Mission #{self.id} - {self.reservation.ad.title}"

    @property
    def is_delayed(self):
        """Vérifie si la mission est en retard"""
        if self.estimated_delivery and not self.actual_delivery:
            return timezone.now() > self.estimated_delivery
        return False

    @property
    def progress_percentage(self):
        """Pourcentage de progression de la mission"""
        status_progress = {
            MissionStatus.SCHEDULED: 10,
            MissionStatus.PICKUP_PENDING: 20,
            MissionStatus.PICKED_UP: 40,
            MissionStatus.IN_TRANSIT: 60,
            MissionStatus.AT_HUB: 70,
            MissionStatus.OUT_FOR_DELIVERY: 80,
            MissionStatus.DELIVERY_PENDING: 90,
            MissionStatus.DELIVERED: 100,
            MissionStatus.CANCELLED: 0,
            MissionStatus.DELAYED: 50,  # Réduit si retardé
        }
        return status_progress.get(self.status, 0)


class TrackingEventType(models.TextChoices):
    """Types d'événements de suivi"""
    PICKUP_SCHEDULED = 'PICKUP_SCHEDULED', _('Prise en charge planifiée')
    PICKUP_CONFIRMED = 'PICKUP_CONFIRMED', _('Prise en charge confirmée')
    PICKUP_COMPLETED = 'PICKUP_COMPLETED', _('Prise en charge effectuée')
    IN_TRANSIT = 'IN_TRANSIT', _('En transit')
    ARRIVED_AT_HUB = 'ARRIVED_AT_HUB', _('Arrivé au centre de tri')
    DEPARTED_FROM_HUB = 'DEPARTED_FROM_HUB', _('Départ du centre de tri')
    OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('En cours de livraison')
    DELIVERY_ATTEMPTED = 'DELIVERY_ATTEMPTED', _('Tentative de livraison')
    DELIVERY_RESCHEDULED = 'DELIVERY_RESCHEDULED', _('Livraison reprogrammée')
    DELIVERED = 'DELIVERED', _('Livré')
    DELAYED = 'DELAYED', _('Retardé')
    CUSTOMS_CLEARANCE = 'CUSTOMS_CLEARANCE', _('Dédouanement')
    CUSTOMS_HELD = 'CUSTOMS_HELD', _('Retenu en douane')
    ISSUE_REPORTED = 'ISSUE_REPORTED', _('Problème signalé')
    ISSUE_RESOLVED = 'ISSUE_RESOLVED', _('Problème résolu')


class TrackingEvent(models.Model):
    """
    Événement de suivi pour une mission
    """
    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name='tracking_events',
        verbose_name=_('Mission')
    )
    event_type = models.CharField(
        max_length=50,
        choices=TrackingEventType.choices,
        verbose_name=_('Type d\'événement')
    )
    description = models.TextField(
        verbose_name=_('Description')
    )
    location = models.CharField(
        max_length=200,
        verbose_name=_('Localisation'),
        blank=True
    )
    latitude = models.FloatField(
        verbose_name=_('Latitude'),
        null=True,
        blank=True
    )
    longitude = models.FloatField(
        verbose_name=_('Longitude'),
        null=True,
        blank=True
    )

    # Photos/Preuves
    photo = models.ImageField(
        upload_to='tracking/events/',
        verbose_name=_('Photo'),
        null=True,
        blank=True
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date de création')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Créé par')
    )

    class Meta:
        verbose_name = _('Événement de suivi')
        verbose_name_plural = _('Événements de suivi')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mission', 'created_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class RouteStatus(models.TextChoices):
    """Statuts d'une route"""
    ACTIVE = 'ACTIVE', _('Active')
    FULL = 'FULL', _('Complète')
    IN_TRANSIT = 'IN_TRANSIT', _('En transit')
    COMPLETED = 'COMPLETED', _('Terminée')
    CANCELLED = 'CANCELLED', _('Annulée')


class Route(models.Model):
    """
    Route publiée par un transporteur
    """
    carrier = models.ForeignKey(
        Carrier,  # CORRECTION: Carrier au lieu de CarrierProfile
        on_delete=models.CASCADE,
        related_name='routes',
        verbose_name=_('Transporteur')
    )

    # Départ
    start_city = models.CharField(
        max_length=100,
        verbose_name=_('Ville de départ')
    )
    start_country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='departure_routes',
        verbose_name=_('Pays de départ')
    )
    start_address = models.TextField(
        verbose_name=_('Adresse de départ'),
        blank=True
    )

    # Arrivée
    end_city = models.CharField(
        max_length=100,
        verbose_name=_('Ville d\'arrivée')
    )
    end_country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='arrival_routes',
        verbose_name=_('Pays d\'arrivée')
    )
    end_address = models.TextField(
        verbose_name=_('Adresse d\'arrivée'),
        blank=True
    )

    # Dates
    departure_date = models.DateField(
        verbose_name=_('Date de départ')
    )
    arrival_date = models.DateField(
        verbose_name=_('Date d\'arrivée')
    )

    # Capacités
    max_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name=_('Poids maximum (kg)'),
        validators=[MinValueValidator(0)]
    )
    max_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name=_('Volume maximum (m³)'),
        validators=[MinValueValidator(0)]
    )
    available_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name=_('Poids disponible (kg)'),
        validators=[MinValueValidator(0)]
    )
    available_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name=_('Volume disponible (m³)'),
        validators=[MinValueValidator(0)]
    )

    # Prix
    fixed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Prix fixe'),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Prix par kg'),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    price_per_m3 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Prix par m³'),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=RouteStatus.choices,
        default=RouteStatus.ACTIVE,
        verbose_name=_('Statut')
    )

    # Services inclus
    includes_insurance = models.BooleanField(
        default=False,
        verbose_name=_('Assurance incluse')
    )
    includes_packaging = models.BooleanField(
        default=False,
        verbose_name=_('Emballage inclus')
    )
    includes_loading = models.BooleanField(
        default=False,
        verbose_name=_('Chargement inclus')
    )
    includes_unloading = models.BooleanField(
        default=False,
        verbose_name=_('Déchargement inclus')
    )

    # Description
    description = models.TextField(
        verbose_name=_('Description'),
        blank=True
    )
    special_conditions = models.TextField(
        verbose_name=_('Conditions spéciales'),
        blank=True
    )

    # Métadonnées
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_('Mis en avant')
    )
    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Nombre de vues')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date de création')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Date de modification')
    )

    class Meta:
        verbose_name = _('Route')
        verbose_name_plural = _('Routes')
        ordering = ['departure_date', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['departure_date']),
            models.Index(fields=['carrier', 'status']),
            models.Index(fields=['start_country', 'end_country']),
        ]

    def __str__(self):
        return f"{self.start_city} → {self.end_city} ({self.departure_date})"

    def clean(self):
        """Validation personnalisée"""
        super().clean()

        # Vérifier les dates
        if self.arrival_date < self.departure_date:
            raise ValidationError(_("La date d'arrivée doit être après la date de départ."))

        # Vérifier la disponibilité
        if self.available_weight > self.max_weight:
            raise ValidationError(_("Le poids disponible ne peut pas dépasser le poids maximum."))
        if self.available_volume > self.max_volume:
            raise ValidationError(_("Le volume disponible ne peut pas dépasser le volume maximum."))

        # Mettre à jour le statut si complet
        if self.available_weight == 0 and self.available_volume == 0:
            self.status = RouteStatus.FULL
        elif self.status == RouteStatus.FULL and (self.available_weight > 0 or self.available_volume > 0):
            self.status = RouteStatus.ACTIVE

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        """Vérifie si la route est disponible"""
        return self.status == RouteStatus.ACTIVE and (
            self.available_weight > 0 or self.available_volume > 0
        )

    @property
    def days_until_departure(self):
        """Jours restants avant le départ"""
        delta = self.departure_date - timezone.now().date()
        return delta.days if delta.days > 0 else 0

    @property
    def calculate_price(self, weight=None, volume=None):
        """Calcule le prix en fonction du poids et/ou volume"""
        if self.fixed_price:
            return self.fixed_price

        price = 0
        if weight and self.price_per_kg:
            price += weight * self.price_per_kg
        if volume and self.price_per_m3:
            price += volume * self.price_per_m3

        return price


class TransportProposalStatus(models.TextChoices):
    """Statuts d'une proposition de transport"""
    PENDING = 'PENDING', _('En attente')
    ACCEPTED = 'ACCEPTED', _('Acceptée')
    REJECTED = 'REJECTED', _('Rejetée')
    EXPIRED = 'EXPIRED', _('Expirée')
    CANCELLED = 'CANCELLED', _('Annulée')


class TransportProposal(models.Model):
    """
    Proposition de transport pour une annonce
    """
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='transport_proposals',
        verbose_name=_('Annonce')
    )
    carrier = models.ForeignKey(
        Carrier,  # CORRECTION: Carrier au lieu de CarrierProfile
        on_delete=models.CASCADE,
        related_name='proposals',
        verbose_name=_('Transporteur')
    )

    # Détails de la proposition
    proposed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Prix proposé'),
        validators=[MinValueValidator(0)]
    )
    message = models.TextField(
        verbose_name=_('Message'),
        blank=True
    )

    # Dates
    estimated_pickup_date = models.DateField(
        verbose_name=_('Date de prise en charge estimée'),
        null=True,
        blank=True
    )
    estimated_delivery_date = models.DateField(
        verbose_name=_('Date de livraison estimée'),
        null=True,
        blank=True
    )

    # Services
    includes_insurance = models.BooleanField(
        default=False,
        verbose_name=_('Assurance incluse')
    )
    insurance_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Valeur assurée'),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    includes_packaging = models.BooleanField(
        default=False,
        verbose_name=_('Emballage inclus')
    )
    includes_loading = models.BooleanField(
        default=False,
        verbose_name=_('Chargement inclus')
    )
    includes_unloading = models.BooleanField(
        default=False,
        verbose_name=_('Déchargement inclus')
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=TransportProposalStatus.choices,
        default=TransportProposalStatus.PENDING,
        verbose_name=_('Statut')
    )

    # Expiration
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date de création')
    )
    expires_at = models.DateTimeField(
        verbose_name=_('Date d\'expiration')
    )

    # Réponse
    responded_at = models.DateTimeField(
        verbose_name=_('Date de réponse'),
        null=True,
        blank=True
    )
    response_message = models.TextField(
        verbose_name=_('Message de réponse'),
        blank=True
    )

    class Meta:
        verbose_name = _('Proposition de transport')
        verbose_name_plural = _('Propositions de transport')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['ad', 'status']),
            models.Index(fields=['carrier', 'status']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = ['ad', 'carrier']

    def __str__(self):
        return f"Proposition #{self.id} - {self.ad.title}"

    def clean(self):
        """Validation personnalisée"""
        super().clean()

        # Vérifier les dates
        if self.estimated_delivery_date and self.estimated_pickup_date:
            if self.estimated_delivery_date < self.estimated_pickup_date:
                raise ValidationError(_("La date de livraison doit être après la date de prise en charge."))

        # Définir l'expiration par défaut (7 jours)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)

    def save(self, *args, **kwargs):
        self.full_clean()

        # Mettre à jour le statut si expiré
        if self.expires_at and timezone.now() > self.expires_at:
            self.status = TransportProposalStatus.EXPIRED

        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Vérifie si la proposition est expirée"""
        return self.expires_at and timezone.now() > self.expires_at

    @property
    def can_be_accepted(self):
        """Vérifie si la proposition peut être acceptée"""
        return (self.status == TransportProposalStatus.PENDING and
                not self.is_expired)

    @property
    def days_until_expiry(self):
        """Jours restants avant expiration"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days if delta.days > 0 else 0


class LogisticsSettings(models.Model):
    """
    Paramètres généraux de la logistique
    """
    # Commissions
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        verbose_name=_('Taux de commission (%)'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Délais
    reservation_expiry_hours = models.PositiveIntegerField(
        default=48,
        verbose_name=_('Expiration réservation (heures)')
    )
    proposal_expiry_days = models.PositiveIntegerField(
        default=7,
        verbose_name=_('Expiration proposition (jours)')
    )

    # Paiement
    payment_hold_days = models.PositiveIntegerField(
        default=3,
        verbose_name=_('Rétention paiement (jours)')
    )
    auto_release_payment = models.BooleanField(
        default=True,
        verbose_name=_('Libération automatique paiement')
    )

    # Notifications
    notify_on_reservation = models.BooleanField(
        default=True,
        verbose_name=_('Notifier nouvelle réservation')
    )
    notify_on_status_change = models.BooleanField(
        default=True,
        verbose_name=_('Notifier changement statut')
    )
    notify_before_expiry = models.BooleanField(
        default=True,
        verbose_name=_('Notifier avant expiration')
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Date de création')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Date de modification')
    )

    class Meta:
        verbose_name = _('Paramètre logistique')
        verbose_name_plural = _('Paramètres logistiques')

    def __str__(self):
        return "Paramètres Logistiques"

    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'une seule instance
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Charge les paramètres ou crée des valeurs par défaut"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
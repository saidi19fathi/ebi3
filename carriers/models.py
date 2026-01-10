# ~/ebi3/carriers/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django_countries.fields import CountryField
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from phonenumber_field.modelfields import PhoneNumberField
from django.urls import reverse  # AJOUT IMPORT MANQUANT
import uuid
from users.models import User

class Carrier(models.Model):
    """Transporteur (professionnel ou particulier)"""

    class CarrierType(models.TextChoices):
        PROFESSIONAL = 'PROFESSIONAL', _('Professionnel')
        PERSONAL = 'PERSONAL', _('Particulier (Expatrié)')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        APPROVED = 'APPROVED', _('Approuvé')
        REJECTED = 'REJECTED', _('Rejeté')
        SUSPENDED = 'SUSPENDED', _('Suspendu')
        INACTIVE = 'INACTIVE', _('Inactif')

    class VehicleType(models.TextChoices):
        CAR = 'CAR', _('Voiture')
        VAN = 'VAN', _('Camionnette')
        TRUCK_SMALL = 'TRUCK_SMALL', _('Camion (3.5T)')
        TRUCK_MEDIUM = 'TRUCK_MEDIUM', _('Camion (7.5T)')
        TRUCK_LARGE = 'TRUCK_LARGE', _('Camion (19T+)')
        MOTORCYCLE = 'MOTORCYCLE', _('Moto')
        OTHER = 'OTHER', _('Autre')

    # Relation avec l'utilisateur
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='carrier_profile',
        verbose_name=_("Utilisateur")
    )

    # Type de transporteur
    carrier_type = models.CharField(
        max_length=20,
        choices=CarrierType.choices,
        verbose_name=_("Type de transporteur")
    )

    # Statut et vérification
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Statut")
    )

    verification_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Niveau de vérification"),
        help_text=_("De 0 (non vérifié) à 5 (entièrement vérifié)")
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Vérifié le")
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_("Raison du rejet")
    )

    # Informations professionnelles (pour les pros)
    company_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Nom de l'entreprise")
    )

    company_registration = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Numéro d'immatriculation")
    )

    tax_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Numéro fiscal/TVA")
    )

    company_address = models.TextField(
        blank=True,
        verbose_name=_("Adresse de l'entreprise")
    )

    # Documents
    registration_certificate = models.FileField(
        upload_to='carriers/documents/registration/',
        null=True,
        blank=True,
        verbose_name=_("Certificat d'immatriculation")
    )

    insurance_certificate = models.FileField(
        upload_to='carriers/documents/insurance/',
        null=True,
        blank=True,
        verbose_name=_("Certificat d'assurance")
    )

    operator_license = models.FileField(
        upload_to='carriers/documents/license/',
        null=True,
        blank=True,
        verbose_name=_("Licence d'exploitation")
    )

    # Véhicule
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        verbose_name=_("Type de véhicule")
    )

    vehicle_make = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Marque du véhicule")
    )

    vehicle_model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Modèle du véhicule")
    )

    vehicle_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Année du véhicule"),
        validators=[MinValueValidator(1990), MaxValueValidator(2100)]
    )

    vehicle_registration = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Plaque d'immatriculation")
    )

    # Capacités
    max_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=100,
        verbose_name=_("Poids maximum (kg)"),
        help_text=_("Charge utile maximale")
    )

    max_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=1,
        verbose_name=_("Volume maximum (m³)"),
        help_text=_("Volume utile maximum")
    )

    max_length = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1.5,
        verbose_name=_("Longueur maximum (m)")
    )

    max_width = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        verbose_name=_("Largeur maximum (m)")
    )

    max_height = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        verbose_name=_("Hauteur maximum (m)")
    )

    # Services proposés
    provides_packaging = models.BooleanField(
        default=False,
        verbose_name=_("Fournit l'emballage")
    )

    provides_insurance = models.BooleanField(
        default=False,
        verbose_name=_("Fournit l'assurance")
    )

    provides_loading = models.BooleanField(
        default=False,
        verbose_name=_("Fournit le chargement")
    )

    provides_unloading = models.BooleanField(
        default=False,
        verbose_name=_("Fournit le déchargement")
    )

    # Tarification
    base_price_per_km = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=1.0,
        verbose_name=_("Prix de base par km (€)")
    )

    min_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=10.0,
        verbose_name=_("Prix minimum (€)")
    )

    currency = models.CharField(
        max_length=3,
        default='EUR',
        choices=[
            ('EUR', '€'),
            ('USD', '$'),
            ('GBP', '£'),
            ('MAD', 'DH'),
            ('XOF', 'CFA'),
        ],
        verbose_name=_("Devise")
    )

    # Disponibilité
    is_available = models.BooleanField(
        default=True,
        verbose_name=_("Disponible pour des missions")
    )

    available_from = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Disponible à partir du")
    )

    available_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Disponible jusqu'au")
    )

    # Statistiques
    total_missions = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Total des missions")
    )

    completed_missions = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Missions complétées")
    )

    success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Taux de réussite (%)")
    )

    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Note moyenne")
    )

    total_reviews = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre total d'avis")
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Transporteur")
        verbose_name_plural = _("Transporteurs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'carrier_type']),
            models.Index(fields=['is_available', 'status']),
            models.Index(fields=['user', 'status']),
        ]
        permissions = [
            ('can_verify_carrier', 'Peut vérifier les transporteurs'),
            ('can_approve_carrier', 'Peut approuver les transporteurs'),
            ('can_view_carrier_stats', 'Peut voir les statistiques des transporteurs'),
        ]

    def __str__(self):
        if self.carrier_type == self.CarrierType.PROFESSIONAL and self.company_name:
            return f"{self.company_name} ({self.user.username})"
        return f"{self.user.username} ({self.get_carrier_type_display()})"


    def save(self, *args, **kwargs):
        if self.status == self.Status.APPROVED and not self.approved_at:
            self.approved_at = timezone.now()
            self.verified_at = timezone.now()
        if self.status == self.Status.APPROVED and self.verification_level < 3:
            self.verification_level = 3

        super().save(*args, **kwargs)
        self._update_user_role()

    def _update_user_role(self):
        try:
            user = self.user
            if self.carrier_type == self.CarrierType.PROFESSIONAL and user.role != User.Role.CARRIER:
                user.role = User.Role.CARRIER
                user.save(update_fields=['role'])
            elif self.carrier_type == self.CarrierType.PERSONAL and user.role != User.Role.CARRIER_PERSONAL:
                user.role = User.Role.CARRIER_PERSONAL
                user.save(update_fields=['role'])
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de la mise à jour du rôle utilisateur pour {self.user.username}: {e}")


    def get_absolute_url(self):
        # CORRECTION : Utilisation correcte de reverse avec kwargs
        return reverse('carriers:carrier_detail', kwargs={'username': self.user.username})

    def calculate_success_rate(self):
        """Calcule le taux de réussite"""
        if self.total_missions > 0:
            return (self.completed_missions / self.total_missions) * 100
        return 100.00

    def can_carry_item(self, weight, length, width, height):
        """Vérifie si le transporteur peut transporter un objet"""
        if weight > self.max_weight:
            return False

        volume = length * width * height
        if volume > self.max_volume:
            return False

        if length > self.max_length or width > self.max_width or height > self.max_height:
            return False

        return True

    def get_available_routes(self):
        """Retourne les routes disponibles"""
        return self.routes.filter(is_active=True)

    def is_fully_verified(self):
        """Vérifie si le transporteur est entièrement vérifié"""
        return self.verification_level >= 3 and self.status == self.Status.APPROVED

    def update_average_rating(self):
        """Met à jour la note moyenne du transporteur"""
        # CORRECTION : Méthode pour mettre à jour la note moyenne
        from django.db.models import Avg
        reviews = self.reviews.filter(is_approved=True, is_visible=True)
        if reviews.exists():
            avg = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
            self.average_rating = avg or 0.00
            self.total_reviews = reviews.count()
        else:
            self.average_rating = 0.00
            self.total_reviews = 0

        # Sauvegarder sans déclencher la méthode save complète pour éviter la récursion
        Carrier.objects.filter(pk=self.pk).update(
            average_rating=self.average_rating,
            total_reviews=self.total_reviews
        )


class CarrierRoute(gis_models.Model):
    """Route régulière d'un transporteur"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='carrier_routes',  # CORRECTION : Changé de 'carrier_routes' à 'routes' pour cohérence
        verbose_name=_("Transporteur")
    )

    # Points de départ et d'arrivée
    start_country = CountryField(
        verbose_name=_("Pays de départ")
    )

    start_city = models.CharField(
        max_length=100,
        verbose_name=_("Ville de départ")
    )

    start_location = gis_models.PointField(
        null=True,
        blank=True,
        verbose_name=_("Localisation de départ"),
        help_text=_("Coordonnées GPS du point de départ")
    )

    end_country = CountryField(
        verbose_name=_("Pays d'arrivée")
    )

    end_city = models.CharField(
        max_length=100,
        verbose_name=_("Ville d'arrivée")
    )

    end_location = gis_models.PointField(
        null=True,
        blank=True,
        verbose_name=_("Localisation d'arrivée"),
        help_text=_("Coordonnées GPS du point d'arrivée")
    )

    # Fréquence
    class Frequency(models.TextChoices):
        ONE_TIME = 'ONE_TIME', _('Ponctuel')
        WEEKLY = 'WEEKLY', _('Hebdomadaire')
        BIWEEKLY = 'BIWEEKLY', _('Bimensuel')
        MONTHLY = 'MONTHLY', _('Mensuel')
        REGULAR = 'REGULAR', _('Régulier')

    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.ONE_TIME,
        verbose_name=_("Fréquence")
    )

    # Dates
    departure_date = models.DateField(
        verbose_name=_("Date de départ")
    )

    arrival_date = models.DateField(
        verbose_name=_("Date d'arrivée")
    )

    # Capacités disponibles sur cette route
    available_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        verbose_name=_("Poids disponible (kg)")
    )

    available_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name=_("Volume disponible (m³)")
    )

    # Statut
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )

    is_full = models.BooleanField(
        default=False,
        verbose_name=_("Complet")
    )

    # Prix spécifique à cette route
    price_per_kg = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name=_("Prix par kg (€)")
    )

    price_per_m3 = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name=_("Prix par m³ (€)")
    )

    fixed_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Prix fixe (€)")
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Route de transporteur")
        verbose_name_plural = _("Routes de transporteurs")
        ordering = ['departure_date']
        indexes = [
            models.Index(fields=['start_country', 'end_country']),
            models.Index(fields=['departure_date', 'is_active']),
            models.Index(fields=['carrier', 'is_active']),
        ]

    def __str__(self):
        return f"{self.start_city} → {self.end_city} ({self.departure_date})"

    def save(self, *args, **kwargs):
        # Définir les prix par défaut si non spécifiés
        if not self.price_per_kg:
            self.price_per_kg = self.carrier.base_price_per_km * 0.1  # Exemple

        if not self.price_per_m3:
            self.price_per_m3 = self.carrier.base_price_per_km * 0.5  # Exemple

        # CORRECTION : Initialiser les capacités disponibles si non définies
        if self.available_weight == 0:
            self.available_weight = self.carrier.max_weight

        if self.available_volume == 0:
            self.available_volume = self.carrier.max_volume

        super().save(*args, **kwargs)

    def calculate_price(self, weight=None, volume=None):
        """Calcule le prix pour un envoi"""
        if self.fixed_price:
            return self.fixed_price

        price = self.carrier.min_price

        if weight and self.price_per_kg:
            price += weight * self.price_per_kg

        if volume and self.price_per_m3:
            price += volume * self.price_per_m3

        return max(price, self.carrier.min_price)

    def update_availability(self, used_weight, used_volume):
        """Met à jour la disponibilité après une réservation"""
        self.available_weight -= used_weight
        self.available_volume -= used_volume

        if self.available_weight <= 0 and self.available_volume <= 0:
            self.is_full = True

        self.save()

    def is_available_for_item(self, weight, volume):
        """Vérifie si la route peut accepter un nouvel objet"""
        if not self.is_active or self.is_full:
            return False

        if weight > self.available_weight or volume > self.available_volume:
            return False

        return True


class CarrierDocument(models.Model):
    """Document d'un transporteur"""

    class DocumentType(models.TextChoices):
        ID_CARD = 'ID_CARD', _("Carte d'identité")
        PASSPORT = 'PASSPORT', _("Passeport")
        DRIVER_LICENSE = 'DRIVER_LICENSE', _("Permis de conduire")
        VEHICLE_REGISTRATION = 'VEHICLE_REGISTRATION', _("Carte grise")
        INSURANCE = 'INSURANCE', _("Assurance")
        COMPANY_REGISTRATION = 'COMPANY_REGISTRATION', _("Immatriculation société")
        TAX_CERTIFICATE = 'TAX_CERTIFICATE', _("Certificat fiscal")
        OTHER = 'OTHER', _("Autre")

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_("Transporteur")
    )

    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        verbose_name=_("Type de document")
    )

    file = models.FileField(
        upload_to='carriers/documents/%Y/%m/%d/',
        verbose_name=_("Fichier")
    )

    thumbnail = models.ImageField(
        upload_to='carriers/documents/thumbnails/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Miniature")
    )

    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Description")
    )

    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Vérifié")
    )

    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents',
        verbose_name=_("Vérifié par")
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Vérifié le")
    )

    verification_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de vérification")
    )

    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date d'expiration")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Document de transporteur")
        verbose_name_plural = _("Documents de transporteurs")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.carrier}"

    def is_expired(self):
        """Vérifie si le document est expiré"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False


class CarrierReview(models.Model):
    """Avis sur un transporteur"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_("Transporteur")
    )

    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='carrier_reviews',
        verbose_name=_("Auteur")
    )

    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Note (1-5)")
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre")
    )

    comment = models.TextField(
        verbose_name=_("Commentaire")
    )

    # Caractéristiques évaluées
    communication = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
        verbose_name=_("Communication")
    )

    punctuality = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
        verbose_name=_("Ponctualité")
    )

    handling = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
        verbose_name=_("Manutention")
    )

    professionalism = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
        verbose_name=_("Professionalisme")
    )

    # Statut
    is_approved = models.BooleanField(
        default=False,
        verbose_name=_("Approuvé")
    )

    is_visible = models.BooleanField(
        default=True,
        verbose_name=_("Visible")
    )

    admin_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de l'administrateur")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Avis sur transporteur")
        verbose_name_plural = _("Avis sur transporteurs")
        ordering = ['-created_at']
        unique_together = ['carrier', 'reviewer']
        indexes = [
            models.Index(fields=['carrier', 'is_approved', 'is_visible']),
            models.Index(fields=['reviewer', 'created_at']),
        ]

    def __str__(self):
        return f"Avis de {self.reviewer.username} sur {self.carrier} ({self.rating}/5)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Mettre à jour la note moyenne du transporteur
        self.carrier.update_average_rating()

    def delete(self, *args, **kwargs):
        carrier = self.carrier
        super().delete(*args, **kwargs)
        # Mettre à jour la note moyenne du transporteur
        carrier.update_average_rating()


class CarrierAvailability(models.Model):
    """Disponibilité d'un transporteur"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='availabilities',
        verbose_name=_("Transporteur")
    )

    start_datetime = models.DateTimeField(
        verbose_name=_("Début de disponibilité")
    )

    end_datetime = models.DateTimeField(
        verbose_name=_("Fin de disponibilité")
    )

    location = gis_models.PointField(
        null=True,
        blank=True,
        verbose_name=_("Localisation")
    )

    available_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        verbose_name=_("Poids disponible (kg)")
    )

    available_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name=_("Volume disponible (m³)")
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )

    is_booked = models.BooleanField(
        default=False,
        verbose_name=_("Réservé")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Disponibilité de transporteur")
        verbose_name_plural = _("Disponibilités de transporteurs")
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['carrier', 'start_datetime', 'is_booked']),
        ]

    def __str__(self):
        return f"{self.carrier} - {self.start_datetime.strftime('%d/%m/%Y %H:%M')}"

    def is_currently_available(self):
        """Vérifie si la disponibilité est actuelle"""
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime and not self.is_booked

    def duration_hours(self):
        """Calcule la durée en heures"""
        duration = self.end_datetime - self.start_datetime
        return duration.total_seconds() / 3600

    def save(self, *args, **kwargs):
        # CORRECTION : Initialiser les capacités disponibles si non définies
        if self.available_weight == 0:
            self.available_weight = self.carrier.max_weight

        if self.available_volume == 0:
            self.available_volume = self.carrier.max_volume

        super().save(*args, **kwargs)


class CarrierNotification(models.Model):
    """Notification pour un transporteur"""

    class NotificationType(models.TextChoices):
        NEW_MISSION = 'NEW_MISSION', _('Nouvelle mission')
        MISSION_UPDATE = 'MISSION_UPDATE', _('Mise à jour de mission')
        PAYMENT_RECEIVED = 'PAYMENT_RECEIVED', _('Paiement reçu')
        REVIEW_RECEIVED = 'REVIEW_RECEIVED', _('Avis reçu')
        DOCUMENT_VERIFIED = 'DOCUMENT_VERIFIED', _('Document vérifié')
        STATUS_CHANGED = 'STATUS_CHANGED', _('Statut changé')
        SYSTEM = 'SYSTEM', _('Système')

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_("Transporteur")
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        verbose_name=_("Type de notification")
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre")
    )

    message = models.TextField(
        verbose_name=_("Message")
    )

    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("ID objet lié")
    )

    related_object_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Type d'objet lié")
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name=_("Lu")
    )

    is_important = models.BooleanField(
        default=False,
        verbose_name=_("Important")
    )

    action_url = models.URLField(
        blank=True,
        verbose_name=_("URL d'action")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification de transporteur")
        verbose_name_plural = _("Notifications de transporteurs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['carrier', 'is_read', 'created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.carrier}"

    def mark_as_read(self):
        """Marque la notification comme lue"""
        self.is_read = True
        self.save(update_fields=['is_read'])

# ~/ebi3/carriers/views.py

def carrier_detail(request, username):
    """
    Vue pour afficher le détail d'un transporteur
    """
    from django.db.models import Count, Avg

    carrier = get_object_or_404(
        Carrier.objects.select_related('user'),
        user__username=username,
        status=Carrier.Status.APPROVED
    )

    # Routes actives
    routes = carrier.carrier_routes.filter(is_active=True).order_by('departure_date')

    # CORRECTION : Utiliser 'reviewer' au lieu de 'author'
    reviews = carrier.reviews.filter(
        is_approved=True,
        is_visible=True
    ).select_related('reviewer').order_by('-created_at')[:10]

    # Calculer les statistiques d'avis
    review_stats = carrier.reviews.filter(
        is_approved=True,
        is_visible=True
    ).aggregate(
        total=Count('id'),
        avg_rating=Avg('rating'),
        avg_communication=Avg('communication'),
        avg_punctuality=Avg('punctuality'),
        avg_handling=Avg('handling'),
        avg_professionalism=Avg('professionalism')
    )

    # CORRECTION : Ajouter total_reviews au contexte
    review_stats['total_reviews'] = carrier.total_reviews

    # Récupérer les documents vérifiés
    verified_documents = carrier.documents.filter(is_verified=True)

    # Vérifier si l'utilisateur connecté peut laisser un avis
    can_review = False
    has_reviewed = False

    if request.user.is_authenticated and request.user != carrier.user:
        # Vérifier si l'utilisateur a déjà laissé un avis
        has_reviewed = carrier.reviews.filter(reviewer=request.user).exists()

        # Logique pour déterminer si l'utilisateur peut laisser un avis
        # (par exemple, s'il a eu une mission complétée avec ce transporteur)
        # Pour l'instant, on autorise tous les utilisateurs connectés qui n'ont pas encore laissé d'avis
        can_review = not has_reviewed

    context = {
        'carrier': carrier,
        'routes': routes,  # Note : dans le template vous utilisez 'active_routes', donc je vais changer
        'active_routes': routes,  # Ajout pour correspondre au template
        'reviews': reviews,
        'review_stats': review_stats,
        'verified_documents': verified_documents,
        'can_review': can_review,
        'has_reviewed': has_reviewed,
    }

    return render(request, 'carriers/carrier_detail.html', context)
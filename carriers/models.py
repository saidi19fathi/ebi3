# ~/ebi3/carriers/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django_countries.fields import CountryField
from django.contrib.gis.db import models as gis_models
from phonenumber_field.modelfields import PhoneNumberField
from django.urls import reverse
from django.db import transaction
import uuid
import logging
from users.models import User  # Utiliser votre modèle User existant
from decimal import Decimal
import os

# Configurer le logger
logger = logging.getLogger(__name__)

# Constantes pour les types de marchandises
class MerchandiseTypes:
    STANDARD = [
        ('DOCUMENTS', _('Documents')),
        ('ELECTRONICS', _('Électronique')),
        ('CLOTHING', _('Vêtements')),
        ('FOOD', _('Nourriture')),
        ('MEDICINE', _('Médicaments')),
        ('COSMETICS', _('Cosmétiques')),
        ('BOOKS', _('Livres')),
        ('TOOLS', _('Outils')),
        ('SPARE_PARTS', _('Pièces détachées')),
        ('FURNITURE', _('Meubles')),
        ('APPLIANCES', _('Appareils électroménagers')),
        ('ART', _('Objets d\'art')),
        ('MUSICAL_INSTRUMENTS', _('Instruments de musique')),
        ('SPORTS_EQUIPMENT', _('Équipement sportif')),
        ('TOYS', _('Jouets')),
        ('AUTO_PARTS', _('Pièces automobiles')),
        ('CONSTRUCTION_MATERIALS', _('Matériaux de construction')),
        ('AGRICULTURAL_PRODUCTS', _('Produits agricoles')),
        ('CHEMICALS', _('Produits chimiques (non dangereux)')),
        ('OTHER', _('Autre')),
    ]


class Carrier(models.Model):
    """Extension du modèle User pour les transporteurs (professionnels ou particuliers)"""

    class CarrierType(models.TextChoices):
        PROFESSIONAL = 'CARRIER', _('Transporteur Professionnel')
        PERSONAL = 'CARRIER_PERSONAL', _('Transporteur Particulier')

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

    # ========== CHAMPS CRITIQUES MANQUANTS - AJOUTÉS ==========
    # Champ pour contrôler l'affichage dans le frontend
    is_active_in_frontend = models.BooleanField(
        default=False,
        verbose_name=_("Actif dans le frontend"),
        help_text=_("Si activé, le transporteur apparaît dans les recherches frontend")
    )

    # Champ pour suivre qui a approuvé le transporteur
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_carriers',
        verbose_name=_("Approuvé par"),
        help_text=_("Administrateur qui a approuvé ce transporteur")
    )

    # ========== RELATIONS EXISTANTES ==========
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='carrier_profile',
        verbose_name=_("Utilisateur"),
        help_text=_("L'utilisateur auquel est associé ce profil transporteur")
    )

    carrier_type = models.CharField(
        max_length=20,
        choices=CarrierType.choices,
        verbose_name=_("Type de transporteur"),
        help_text=_("Note: doit correspondre au rôle dans le profil utilisateur")
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Statut de transporteur")
    )

    verification_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Niveau de vérification transporteur"),
        help_text=_("De 0 (non vérifié) à 5 (entièrement vérifié) - spécifique au transport")
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Vérifié le (transport)")
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_("Raison du rejet (transport)")
    )

    # === PHOTOS ET DOCUMENTS SPÉCIFIQUES AU TRANSPORT ===
    profile_photo = models.ImageField(
        upload_to='carriers/profile_photos/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Photo de profil transporteur"),
        help_text=_("Photo spécifique pour le profil transporteur")
    )

    id_front = models.ImageField(
        upload_to='carriers/ids/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Recto pièce d'identité (transport)"),
        help_text=_("Pour vérification spécifique transport")
    )

    id_back = models.ImageField(
        upload_to='carriers/ids/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Verso pièce d'identité (transport)")
    )

    # === INFORMATIONS PROFESSIONNELLES SPÉCIFIQUES ===
    transport_company_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Nom de l'entreprise de transport"),
        help_text=_("Spécifique à l'activité de transport")
    )

    transport_company_registration = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Numéro d'immatriculation transport"),
        help_text=_("Spécifique à l'activité de transport")
    )

    transport_tax_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Numéro fiscal transport")
    )

    transport_company_address = models.TextField(
        blank=True,
        verbose_name=_("Adresse de l'entreprise de transport"),
        help_text=_("Adresse spécifique pour l'activité de transport")
    )

    # Documents spécifiques au transport
    vehicle_registration_certificate = models.FileField(
        upload_to='carriers/documents/vehicle_registration/',
        null=True,
        blank=True,
        verbose_name=_("Certificat d'immatriculation véhicule")
    )

    transport_insurance_certificate = models.FileField(
        upload_to='carriers/documents/transport_insurance/',
        null=True,
        blank=True,
        verbose_name=_("Certificat d'assurance transport")
    )

    transport_operator_license = models.FileField(
        upload_to='carriers/documents/transport_license/',
        null=True,
        blank=True,
        verbose_name=_("Licence d'exploitation transport")
    )

    # === VÉHICULE ===
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

    # Photos du véhicule
    vehicle_photo_front = models.ImageField(
        upload_to='carriers/vehicles/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Photo avant du véhicule")
    )

    vehicle_photo_back = models.ImageField(
        upload_to='carriers/vehicles/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Photo arrière du véhicule")
    )

    vehicle_photo_side = models.ImageField(
        upload_to='carriers/vehicles/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Photo côté du véhicule")
    )

    # === CAPACITÉS DE CHARGEMENT ===
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

    # === ZONES DE COUVERTURE ===
    coverage_countries = CountryField(
        multiple=True,
        blank=True,
        verbose_name=_("Pays de couverture transport")
    )

    coverage_cities = models.TextField(
        blank=True,
        verbose_name=_("Villes de couverture (transport)"),
        help_text=_("Villes spécifiques pour le transport, séparées par des virgules")
    )

    # === TYPES DE MARCHANDISES ACCEPTÉES ===
    accepted_merchandise_types = models.JSONField(
        default=list,
        verbose_name=_("Types de marchandises acceptées"),
        help_text=_("Liste des types de marchandises acceptées pour le transport")
    )

    custom_merchandise_types = models.TextField(
        blank=True,
        verbose_name=_("Types de marchandises personnalisés"),
        help_text=_("Saisissez vos types personnalisés séparés par des virgules")
    )

    # === HORAIRES DE DISPONIBILITÉ TRANSPORT ===
    transport_weekly_schedule = models.JSONField(
        default=dict,
        verbose_name=_("Emploi du temps hebdomadaire transport"),
        help_text=_("Disponibilités spécifiques pour le transport")
    )

    transport_available_from = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Disponible à partir du (transport)")
    )

    transport_available_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Disponible jusqu'au (transport)")
    )

    # === SERVICES PROPOSÉS ===
    provides_packaging = models.BooleanField(
        default=False,
        verbose_name=_("Fournit l'emballage")
    )

    provides_insurance = models.BooleanField(
        default=False,
        verbose_name=_("Fournit l'assurance transport")
    )

    provides_loading = models.BooleanField(
        default=False,
        verbose_name=_("Fournit le chargement")
    )

    provides_unloading = models.BooleanField(
        default=False,
        verbose_name=_("Fournit le déchargement")
    )

    # === TARIFICATION ===
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
        verbose_name=_("Devise pour le transport")
    )

    # === DISPONIBILITÉ TRANSPORT ===
    transport_is_available = models.BooleanField(
        default=True,
        verbose_name=_("Disponible pour des missions de transport")
    )

    # === STATISTIQUES SPÉCIFIQUES AU TRANSPORT ===
    total_transport_missions = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Total des missions de transport")
    )

    completed_transport_missions = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Missions de transport complétées")
    )

    transport_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Taux de réussite transport (%)")
    )

    transport_average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Note moyenne transport")
    )

    transport_total_reviews = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre total d'avis transport")
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Profil Transporteur")
        verbose_name_plural = _("Profils Transporteurs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'carrier_type']),
            models.Index(fields=['transport_is_available', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['coverage_countries']),
            # Nouvel index pour le filtrage frontend
            models.Index(fields=['is_active_in_frontend', 'status', 'transport_is_available']),
        ]
        permissions = [
            ('can_verify_carrier', 'Peut vérifier les transporteurs'),
            ('can_approve_carrier', 'Peut approuver les transporteurs'),
            ('can_view_carrier_stats', 'Peut voir les statistiques des transporteurs'),
            ('can_activate_carrier_frontend', 'Peut activer/désactiver dans le frontend'),
        ]

    def __str__(self):
        if self.carrier_type == self.CarrierType.PROFESSIONAL and self.transport_company_name:
            return f"{self.transport_company_name} ({self.user.username})"
        return f"{self.user.username} ({self.get_carrier_type_display()})"

    def save(self, *args, **kwargs):
        """
        Méthode save() qui synchronise avec le modèle User
        """
        is_new = self._state.adding
        logger.debug(f"Sauvegarde du profil transporteur: user={self.user.username}")

        # Synchroniser le rôle utilisateur
        if self.carrier_type == self.CarrierType.PROFESSIONAL:
            expected_role = User.Role.CARRIER
        else:
            expected_role = User.Role.CARRIER_PERSONAL

        # Mettre à jour le rôle de l'utilisateur si nécessaire
        if self.user.role != expected_role:
            self.user.role = expected_role
            self.user.save(update_fields=['role'])
            logger.debug(f"Rôle utilisateur mis à jour pour {self.user.username}: {expected_role}")

        # Mettre à jour la disponibilité de l'utilisateur
        if self.user.is_available != self.transport_is_available:
            self.user.is_available = self.transport_is_available
            self.user.save(update_fields=['is_available'])

        # Mettre à jour les dates d'approbation et vérification
        if self.status == self.Status.APPROVED:
            if not self.approved_at:
                self.approved_at = timezone.now()

            if not self.verified_at:
                self.verified_at = timezone.now()

            if self.verification_level < 3:
                self.verification_level = 3

            # Mettre à jour le statut de vérification de l'utilisateur
            if not self.user.is_verified:
                self.user.is_verified = True
                self.user.save(update_fields=['is_verified'])

        # IMPORTANT: Si le statut est APPROVED, activer automatiquement dans le frontend
        if self.status == self.Status.APPROVED and not self.is_active_in_frontend:
            self.is_active_in_frontend = True
            logger.info(f"Transporteur {self.user.username} automatiquement activé dans le frontend")

        # Sauvegarder l'objet Carrier
        try:
            super().save(*args, **kwargs)
            logger.info(f"Profil transporteur sauvegardé: id={self.id}, user={self.user.username}, "
                       f"status={self.status}, frontend_active={self.is_active_in_frontend}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du profil transporteur: {e}")
            raise

    def get_absolute_url(self):
        """URL pour accéder à la page de détail du transporteur"""
        return reverse('carriers:carrier_detail', kwargs={'username': self.user.username})

    def get_all_accepted_merchandise_types(self):
        """Retourne tous les types de marchandises acceptés"""
        standard_types = [code for code, _ in MerchandiseTypes.STANDARD]
        accepted = self.accepted_merchandise_types or []

        # Ajouter les types personnalisés
        if self.custom_merchandise_types:
            custom_types = [t.strip() for t in self.custom_merchandise_types.split(',') if t.strip()]
            accepted.extend(custom_types)

        return list(set(accepted))  # Supprimer les doublons

    def calculate_success_rate(self):
        """Calcule le taux de réussite"""
        if self.total_transport_missions > 0:
            rate = (self.completed_transport_missions / self.total_transport_missions) * 100
            self.transport_success_rate = min(rate, 100.00)
            self.save(update_fields=['transport_success_rate'])
        return self.transport_success_rate

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

    def is_fully_verified(self):
        """Vérifie si le transporteur est entièrement vérifié"""
        return self.verification_level >= 3 and self.status == self.Status.APPROVED

    def update_average_rating(self):
        """Met à jour la note moyenne du transporteur"""
        from django.db.models import Avg

        reviews = self.reviews.filter(is_approved=True, is_visible=True)

        if reviews.exists():
            avg = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
            self.transport_average_rating = avg or 0.00
            self.transport_total_reviews = reviews.count()
        else:
            self.transport_average_rating = 0.00
            self.transport_total_reviews = 0

        try:
            Carrier.objects.filter(pk=self.pk).update(
                transport_average_rating=self.transport_average_rating,
                transport_total_reviews=self.transport_total_reviews
            )
            logger.debug(f"Note moyenne mise à jour pour {self.user.username}: {self.transport_average_rating}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la note moyenne "
                        f"pour {self.user.username}: {e}")

    def is_available_at(self, date_time):
        """Vérifie la disponibilité à une date/heure donnée"""
        if not self.transport_is_available:
            return False

        if self.transport_available_from and date_time.date() < self.transport_available_from:
            return False

        if self.transport_available_until and date_time.date() > self.transport_available_until:
            return False

        # Vérifier l'emploi du temps hebdomadaire
        if self.transport_weekly_schedule:
            day_name = date_time.strftime('%A').lower()
            if day_name in self.transport_weekly_schedule:
                schedule = self.transport_weekly_schedule[day_name]
                if schedule.get('start') and schedule.get('end'):
                    current_time = date_time.strftime('%H:%M')
                    if current_time < schedule['start'] or current_time > schedule['end']:
                        return False

        return True

    # ========== MÉTHODES AJOUTÉES POUR LA GESTION FRONTEND ==========
    def approve_and_activate(self, approved_by_user):
        """Approuve et active le transporteur dans le frontend"""
        self.status = self.Status.APPROVED
        self.is_active_in_frontend = True
        self.approved_at = timezone.now()
        self.approved_by = approved_by_user
        self.verification_level = max(self.verification_level, 3)

        # Mettre à jour l'utilisateur associé
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])

        self.save()

        logger.info(f"Transporteur {self.user.username} approuvé et activé par {approved_by_user.username}")
        return True

    def deactivate_from_frontend(self):
        """Désactive le transporteur du frontend"""
        self.is_active_in_frontend = False
        self.save(update_fields=['is_active_in_frontend'])
        logger.info(f"Transporteur {self.user.username} désactivé du frontend")
        return True

    def reactivate_to_frontend(self):
        """Réactive le transporteur dans le frontend"""
        if self.status == self.Status.APPROVED:
            self.is_active_in_frontend = True
            self.save(update_fields=['is_active_in_frontend'])
            logger.info(f"Transporteur {self.user.username} réactivé dans le frontend")
            return True
        return False

    def can_appear_in_frontend(self):
        """Vérifie si le transporteur peut apparaître dans le frontend"""
        return (
            self.status == self.Status.APPROVED and
            self.is_active_in_frontend and
            self.transport_is_available and
            self.verification_level >= 1
        )

    def get_frontend_status(self):
        """Retourne le statut pour le frontend"""
        if not self.status == self.Status.APPROVED:
            return "pending"
        elif not self.is_active_in_frontend:
            return "inactive"
        elif not self.transport_is_available:
            return "unavailable"
        else:
            return "active"


    def get_rating_for_display(self):
        """Retourne la note pour l'affichage, garantie d'être un float"""
        try:
            return float(self.transport_average_rating or 0)
        except (ValueError, TypeError):
            return 0.0


    @property
    def transport_average_rating_display(self):
        """Retourne la note moyenne formatée pour l'affichage"""
        if self.transport_average_rating:
            return f"{self.transport_average_rating:.1f}/5"
        return "Non noté"

    # OU si le problème est dans format_html, corrigez-le :
    def get_stars_display(self):
        """Retourne les étoiles pour l'affichage"""
        from django.utils.html import format_html
        rating = float(self.transport_average_rating or 0)
        stars = '★' * int(rating)
        half_star = '½' if rating % 1 >= 0.5 else ''
        empty_stars = '☆' * (5 - int(rating) - (1 if half_star else 0))

        # Correction : utiliser des nombres, pas des SafeString
        return format_html(
            '<span style="color: gold;">{}</span>'
            '<span style="color: gold;">{}</span>'
            '<span style="color: lightgray;">{}</span>'
            '<span> ({:.1f}/5)</span>',
            stars, half_star, empty_stars, rating
        )


class CarrierRoute(gis_models.Model):
    """Route régulière d'un transporteur"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='carrier_routes',
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

    # Coûts par pays (péages, taxes) - Pour calculateur de frais
    toll_costs = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name=_("Coûts de péages (€)")
    )

    tax_costs = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name=_("Coûts de taxes (€)")
    )

    fuel_costs = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name=_("Coûts de carburant (€)")
    )

    # Estimation temps de transit
    estimated_transit_time = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_("Temps de transit estimé")
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
        if not self.price_per_kg and self.carrier:
            self.price_per_kg = self.carrier.base_price_per_km * 0.1

        if not self.price_per_m3 and self.carrier:
            self.price_per_m3 = self.carrier.base_price_per_km * 0.5

        # Initialiser les capacités disponibles si non définies
        if self.available_weight == 0 and self.carrier:
            self.available_weight = self.carrier.max_weight

        if self.available_volume == 0 and self.carrier:
            self.available_volume = self.carrier.max_volume

        super().save(*args, **kwargs)

    def calculate_price(self, weight=None, volume=None):
        """Calcule le prix pour un envoi"""
        if self.fixed_price:
            return self.fixed_price

        price = self.carrier.min_price if self.carrier else 10.0

        if weight and self.price_per_kg:
            price += weight * self.price_per_kg

        if volume and self.price_per_m3:
            price += volume * self.price_per_m3

        # Ajouter les coûts fixes
        price += self.toll_costs + self.tax_costs + self.fuel_costs

        return max(price, self.carrier.min_price if self.carrier else 10.0)

    def calculate_profitability(self, weight, volume):
        """Calcule la rentabilité pour un envoi"""
        revenue = self.calculate_price(weight, volume)
        costs = self.toll_costs + self.tax_costs + self.fuel_costs
        profit = revenue - costs
        margin = (profit / revenue * 100) if revenue > 0 else 0

        return {
            'revenue': revenue,
            'costs': costs,
            'profit': profit,
            'margin': margin
        }

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


class Mission(models.Model):
    """Mission de livraison"""

    class MissionStatus(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        ACCEPTED = 'ACCEPTED', _('Acceptée')
        COLLECTING = 'COLLECTING', _('En collecte')
        IN_TRANSIT = 'IN_TRANSIT', _('En transit')
        DELIVERING = 'DELIVERING', _('En livraison')
        DELIVERED = 'DELIVERED', _('Livrée')
        CANCELLED = 'CANCELLED', _('Annulée')
        PROBLEM = 'PROBLEM', _('Problème')

    class PriorityLevel(models.TextChoices):
        LOW = 'LOW', _('Basse')
        MEDIUM = 'MEDIUM', _('Moyenne')
        HIGH = 'HIGH', _('Haute')
        URGENT = 'URGENT', _('Urgente')

    # Identification
    mission_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_("Numéro de mission")
    )

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='carrier_missions',
        verbose_name=_("Transporteur")
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=MissionStatus.choices,
        default=MissionStatus.PENDING,
        verbose_name=_("Statut")
    )

    priority = models.CharField(
        max_length=20,
        choices=PriorityLevel.choices,
        default=PriorityLevel.MEDIUM,
        verbose_name=_("Priorité")
    )

    # Informations d'expédition
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_missions',
        verbose_name=_("Expéditeur")
    )

    sender_address = models.TextField(
        verbose_name=_("Adresse de l'expéditeur")
    )

    sender_phone = PhoneNumberField(
        verbose_name=_("Téléphone expéditeur")
    )

    recipient_name = models.CharField(
        max_length=200,
        verbose_name=_("Nom du destinataire")
    )

    recipient_address = models.TextField(
        verbose_name=_("Adresse du destinataire")
    )

    recipient_phone = PhoneNumberField(
        verbose_name=_("Téléphone destinataire")
    )

    # Marchandise
    merchandise_type = models.CharField(
        max_length=50,
        verbose_name=_("Type de marchandise")
    )

    custom_merchandise_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Type personnalisé")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        verbose_name=_("Poids (kg)")
    )

    length = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Longueur (m)")
    )

    width = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Largeur (m)")
    )

    height = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Hauteur (m)")
    )

    @property
    def volume(self):
        """Calcule le volume"""
        return self.length * self.width * self.height

    # Dates
    preferred_pickup_date = models.DateField(
        verbose_name=_("Date de collecte préférée")
    )

    preferred_delivery_date = models.DateField(
        verbose_name=_("Date de livraison préférée")
    )

    actual_pickup_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date de collecte réelle")
    )

    actual_delivery_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date de livraison réelle")
    )

    # Prix
    agreed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Prix convenu (€)")
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

    # Preuve de livraison
    delivery_proof_photo = models.ImageField(
        upload_to='missions/delivery_proofs/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Photo preuve de livraison")
    )

    recipient_signature = models.ImageField(
        upload_to='missions/signatures/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Signature du destinataire")
    )

    delivery_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de livraison")
    )

    # Incidents/retards
    has_incident = models.BooleanField(
        default=False,
        verbose_name=_("A un incident")
    )

    incident_description = models.TextField(
        blank=True,
        verbose_name=_("Description de l'incident")
    )

    incident_resolved = models.BooleanField(
        default=False,
        verbose_name=_("Incident résolu")
    )

    delay_reason = models.TextField(
        blank=True,
        verbose_name=_("Raison du retard")
    )

    delay_duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_("Durée du retard")
    )

    # Organisation du stock (Nouveau)
    collection_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre de collecte"),
        help_text=_("Ordre dans lequel collecter cet objet")
    )

    position_in_vehicle = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Position dans le véhicule"),
        help_text=_("Ex: Arrière gauche, dessus, etc.")
    )

    is_fragile = models.BooleanField(
        default=False,
        verbose_name=_("Fragile")
    )

    requires_special_handling = models.BooleanField(
        default=False,
        verbose_name=_("Nécessite une manipulation spéciale")
    )

    # Suivi GPS
    current_location = gis_models.PointField(
        null=True,
        blank=True,
        verbose_name=_("Localisation actuelle")
    )

    last_location_update = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dernière mise à jour de localisation")
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Mission")
        verbose_name_plural = _("Missions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mission_number']),
            models.Index(fields=['carrier', 'status']),
            models.Index(fields=['sender', 'status']),
            models.Index(fields=['status', 'preferred_pickup_date']),
            models.Index(fields=['collection_order']),
        ]

    def __str__(self):
        return f"Mission {self.mission_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Générer un numéro de mission unique
        if not self.mission_number:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_mission = Mission.objects.filter(
                mission_number__startswith=f'MIS{date_str}'
            ).order_by('-mission_number').first()

            if last_mission:
                last_num = int(last_mission.mission_number[-4:])
                new_num = last_num + 1
            else:
                new_num = 1

            self.mission_number = f"MIS{date_str}{new_num:04d}"

        # Mettre à jour les dates de statut
        if self.status == self.MissionStatus.ACCEPTED and not self.accepted_at:
            self.accepted_at = timezone.now()

        if self.status == self.MissionStatus.DELIVERED and not self.completed_at:
            self.completed_at = timezone.now()

            # Mettre à jour les statistiques du transporteur
            self.carrier.completed_transport_missions += 1
            self.carrier.total_transport_missions += 1
            self.carrier.save(update_fields=['completed_transport_missions', 'total_transport_missions'])

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """URL pour accéder à la page de détail de la mission"""
        return reverse('carriers:mission_detail', kwargs={'pk': self.pk})

    def can_be_accepted(self):
        """Vérifie si la mission peut être acceptée"""
        return self.status == self.MissionStatus.PENDING

    def accept(self):
        """Accepte la mission"""
        if self.can_be_accepted():
            self.status = self.MissionStatus.ACCEPTED
            self.accepted_at = timezone.now()
            self.save()

            # Créer une notification
            CarrierNotification.objects.create(
                carrier=self.carrier,
                notification_type=CarrierNotification.NotificationType.MISSION_UPDATE,
                title=_("Mission acceptée"),
                message=_("Vous avez accepté la mission {}").format(self.mission_number),
                related_object_id=self.id,
                related_object_type='mission'
            )
            return True
        return False

    def mark_as_collecting(self):
        """Marque la mission comme en cours de collecte"""
        self.status = self.MissionStatus.COLLECTING
        self.save()

    def mark_as_in_transit(self):
        """Marque la mission comme en transit"""
        self.status = self.MissionStatus.IN_TRANSIT
        self.save()

    def mark_as_delivering(self):
        """Marque la mission comme en cours de livraison"""
        self.status = self.MissionStatus.DELIVERING
        self.save()

    def mark_as_delivered(self, proof_photo=None, signature=None, notes=''):
        """Marque la mission comme livrée"""
        self.status = self.MissionStatus.DELIVERED
        self.actual_delivery_date = timezone.now()

        if proof_photo:
            self.delivery_proof_photo = proof_photo
        if signature:
            self.recipient_signature = signature

        self.delivery_notes = notes
        self.save()

    def add_delay(self, reason, duration):
        """Ajoute un retard à la mission"""
        self.delay_reason = reason
        self.delay_duration = duration
        self.save()

    def calculate_estimated_arrival(self):
        """Calcule l'heure d'arrivée estimée"""
        if self.actual_pickup_date and self.carrier.routes.exists():
            route = self.carrier.routes.first()
            if route.estimated_transit_time:
                return self.actual_pickup_date + route.estimated_transit_time
        return None


class CollectionDay(models.Model):
    """Jour de collecte organisé pour un transporteur"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='collection_days',
        verbose_name=_("Transporteur")
    )

    date = models.DateField(
        verbose_name=_("Date de collecte")
    )

    start_time = models.TimeField(
        verbose_name=_("Heure de début")
    )

    end_time = models.TimeField(
        verbose_name=_("Heure de fin")
    )

    # Statut
    is_scheduled = models.BooleanField(
        default=False,
        verbose_name=_("Planifié")
    )

    is_completed = models.BooleanField(
        default=False,
        verbose_name=_("Terminé")
    )

    # Capacités planifiées
    planned_total_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        verbose_name=_("Poids total planifié (kg)")
    )

    planned_total_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name=_("Volume total planifié (m³)")
    )

    # Capacités réelles
    actual_total_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        verbose_name=_("Poids total réel (kg)")
    )

    actual_total_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name=_("Volume total réel (m³)")
    )

    # Organisation
    collection_route = models.JSONField(
        default=list,
        verbose_name=_("Itinéraire de collecte"),
        help_text=_("Liste ordonnée des adresses à collecter")
    )

    optimized_route = models.JSONField(
        default=list,
        verbose_name=_("Itinéraire optimisé"),
        help_text=_("Itinéraire optimisé pour la collecte")
    )

    estimated_distance = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name=_("Distance estimée (km)")
    )

    estimated_duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_("Durée estimée")
    )

    # Notes
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Jour de collecte")
        verbose_name_plural = _("Jours de collecte")
        ordering = ['date', 'start_time']
        unique_together = ['carrier', 'date']
        indexes = [
            models.Index(fields=['carrier', 'date', 'is_completed']),
        ]

    def __str__(self):
        return f"Collecte {self.date} - {self.carrier}"

    @property
    def missions(self):
        """Retourne les missions associées à ce jour de collecte"""
        return Mission.objects.filter(
            carrier=self.carrier,
            preferred_pickup_date=self.date,
            status__in=[
                Mission.MissionStatus.ACCEPTED,
                Mission.MissionStatus.COLLECTING
            ]
        ).order_by('collection_order')

    def calculate_planning(self):
        """Calcule la planification pour ce jour"""
        missions = self.missions

        total_weight = sum(mission.weight for mission in missions)
        total_volume = sum(mission.volume for mission in missions)

        self.planned_total_weight = total_weight
        self.planned_total_volume = total_volume

        # Vérifier si la capacité du véhicule est suffisante
        capacity_ok = (
            total_weight <= self.carrier.max_weight and
            total_volume <= self.carrier.max_volume
        )

        return {
            'total_missions': missions.count(),
            'total_weight': total_weight,
            'total_volume': total_volume,
            'capacity_ok': capacity_ok,
            'remaining_weight': self.carrier.max_weight - total_weight,
            'remaining_volume': self.carrier.max_volume - total_volume
        }

    def generate_collection_list(self):
        """Génère la liste des objets à collecter"""
        missions = self.missions

        collection_list = []
        for mission in missions:
            collection_list.append({
                'mission_number': mission.mission_number,
                'order': mission.collection_order,
                'sender': mission.sender.get_full_name() or mission.sender.username,
                'address': mission.sender_address,
                'phone': mission.sender_phone,
                'merchandise': mission.merchandise_type,
                'description': mission.description,
                'weight': mission.weight,
                'dimensions': f"{mission.length}x{mission.width}x{mission.height}m",
                'volume': mission.volume,
                'fragile': mission.is_fragile,
                'special_handling': mission.requires_special_handling,
                'position': mission.position_in_vehicle,
                'notes': mission.delivery_notes
            })

        return collection_list

    def optimize_route(self):
        """Optimise l'itinéraire de collecte"""
        missions = self.missions

        if not missions:
            return []

        # Simple optimisation par ordre de collection
        # Dans une version réelle, on utiliserait un service comme Google Maps API
        sorted_missions = sorted(missions, key=lambda m: m.collection_order)

        route = []
        for mission in sorted_missions:
            route.append({
                'mission_id': mission.id,
                'address': mission.sender_address,
                'order': mission.collection_order
            })

        self.optimized_route = route
        self.save()

        return route

    def start_collection(self):
        """Démarre la collecte"""
        self.is_scheduled = True

        # Mettre à jour le statut des missions
        missions = self.missions
        for mission in missions:
            mission.mark_as_collecting()

        self.save()

    def complete_collection(self, actual_weight, actual_volume):
        """Termine la collecte"""
        self.is_completed = True
        self.actual_total_weight = actual_weight
        self.actual_total_volume = actual_volume
        self.save()


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
        CUSTOMS_DOCUMENT = 'CUSTOMS_DOCUMENT', _("Document douanier")
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

    # Documents douaniers spécifiques
    is_customs_document = models.BooleanField(
        default=False,
        verbose_name=_("Document douanier")
    )

    customs_country = CountryField(
        blank=True,
        verbose_name=_("Pays concerné")
    )

    customs_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Type de document douanier")
    )

    # Assistant déclarations en ligne
    declaration_data = models.JSONField(
        default=dict,
        verbose_name=_("Données de déclaration"),
        help_text=_("Données pour le générateur de formulaires")
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

    # Rappels pour renouvellements
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name=_("Rappel envoyé")
    )

    reminder_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date de rappel")
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

    def needs_renewal(self):
        """Vérifie si le document a besoin d'être renouvelé"""
        if self.expiry_date:
            from datetime import timedelta
            renewal_date = self.expiry_date - timedelta(days=30)
            return timezone.now().date() >= renewal_date
        return False

    def generate_customs_form(self):
        """Génère un formulaire douanier"""
        if self.is_customs_document and self.declaration_data:
            # Dans une version réelle, on générerait un PDF
            return {
                'type': self.customs_type,
                'country': self.customs_country,
                'data': self.declaration_data,
                'carrier': self.carrier.user.get_full_name(),
                'date': timezone.now().date()
            }
        return None


class FinancialTransaction(models.Model):
    """Transaction financière"""

    class TransactionType(models.TextChoices):
        PAYMENT = 'PAYMENT', _('Paiement')
        EXPENSE = 'EXPENSE', _('Dépense')
        REFUND = 'REFUND', _('Remboursement')
        COMMISSION = 'COMMISSION', _('Commission')
        BONUS = 'BONUS', _('Bonus')

    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', _('Espèces')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Virement bancaire')
        CARD = 'CARD', _('Carte bancaire')
        MOBILE_MONEY = 'MOBILE_MONEY', _('Mobile money')
        PAYPAL = 'PAYPAY', _('PayPal')
        STRIPE = 'STRIPE', _('Stripe')
        OTHER = 'OTHER', _('Autre')

    class ExpenseCategory(models.TextChoices):
        FUEL = 'FUEL', _('Carburant')
        TOLL = 'TOLL', _('Péages')
        MAINTENANCE = 'MAINTENANCE', _('Entretien')
        INSURANCE = 'INSURANCE', _('Assurance')
        PARKING = 'PARKING', _('Parking')
        MEALS = 'MEALS', _('Repas')
        ACCOMMODATION = 'ACCOMMODATION', _('Hébergement')
        OTHER = 'OTHER', _('Autre')

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_("Transporteur")
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        verbose_name=_("Type de transaction")
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Montant")
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

    # Pour les paiements
    mission = models.ForeignKey(
        Mission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Mission")
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        verbose_name=_("Méthode de paiement")
    )

    is_prepaid = models.BooleanField(
        default=False,
        verbose_name=_("Prépaiement")
    )

    # Pour les dépenses
    expense_category = models.CharField(
        max_length=20,
        choices=ExpenseCategory.choices,
        blank=True,
        verbose_name=_("Catégorie de dépense")
    )

    expense_description = models.TextField(
        blank=True,
        verbose_name=_("Description de la dépense")
    )

    expense_receipt = models.FileField(
        upload_to='carriers/expenses/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Reçu de dépense")
    )

    # Reçus électroniques
    receipt_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Numéro de reçu")
    )

    receipt_file = models.FileField(
        upload_to='carriers/receipts/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Fichier reçu")
    )

    # Facturation automatique
    invoice_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Numéro de facture")
    )

    invoice_file = models.FileField(
        upload_to='carriers/invoices/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Fichier facture")
    )

    # Historique des paiements
    transaction_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Date de transaction")
    )

    is_completed = models.BooleanField(
        default=True,
        verbose_name=_("Terminé")
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Transaction financière")
        verbose_name_plural = _("Transactions financières")
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['carrier', 'transaction_type', 'transaction_date']),
            models.Index(fields=['mission', 'transaction_type']),
            models.Index(fields=['transaction_date', 'is_completed']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} {self.currency} - {self.carrier}"

    def save(self, *args, **kwargs):
        # Générer un numéro de reçu
        if not self.receipt_number and self.transaction_type == self.TransactionType.PAYMENT:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_receipt = FinancialTransaction.objects.filter(
                receipt_number__startswith=f'RCV{date_str}'
            ).order_by('-receipt_number').first()

            if last_receipt:
                last_num = int(last_receipt.receipt_number[-4:])
                new_num = last_num + 1
            else:
                new_num = 1

            self.receipt_number = f"RCV{date_str}{new_num:04d}"

        # Générer un numéro de facture
        if not self.invoice_number and self.transaction_type == self.TransactionType.PAYMENT:
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_invoice = FinancialTransaction.objects.filter(
                invoice_number__startswith=f'INV{date_str}'
            ).order_by('-invoice_number').first()

            if last_invoice:
                last_num = int(last_invoice.invoice_number[-4:])
                new_num = last_num + 1
            else:
                new_num = 1

            self.invoice_number = f"INV{date_str}{new_num:04d}"

        super().save(*args, **kwargs)

    def generate_receipt(self):
        """Génère un reçu électronique"""
        # Dans une version réelle, on générerait un PDF
        return {
            'receipt_number': self.receipt_number,
            'date': self.transaction_date,
            'carrier': self.carrier.user.get_full_name(),
            'amount': self.amount,
            'currency': self.currency,
            'mission': self.mission.mission_number if self.mission else None,
            'payment_method': self.get_payment_method_display()
        }

    def generate_invoice(self):
        """Génère une facture"""
        # Dans une version réelle, on générerait un PDF
        return {
            'invoice_number': self.invoice_number,
            'date': self.transaction_date,
            'carrier': self.carrier.user.get_full_name(),
            'company_info': {
                'name': self.carrier.company_name,
                'tax_id': self.carrier.tax_id,
                'address': self.carrier.company_address
            },
            'amount': self.amount,
            'currency': self.currency,
            'mission': self.mission.mission_number if self.mission else None,
            'description': f"Mission {self.mission.mission_number}" if self.mission else "Service de transport"
        }


class ExpenseReport(models.Model):
    """Rapport de dépenses pour comptabilité"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='expense_reports',
        verbose_name=_("Transporteur")
    )

    period_start = models.DateField(
        verbose_name=_("Début de période")
    )

    period_end = models.DateField(
        verbose_name=_("Fin de période")
    )

    total_expenses = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Total des dépenses")
    )

    total_income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Total des revenus")
    )

    net_profit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Bénéfice net")
    )

    report_file = models.FileField(
        upload_to='carriers/expense_reports/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Fichier rapport")
    )

    is_approved = models.BooleanField(
        default=False,
        verbose_name=_("Approuvé")
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Approuvé par")
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Approuvé le")
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Rapport de dépenses")
        verbose_name_plural = _("Rapports de dépenses")
        ordering = ['-period_end']
        unique_together = ['carrier', 'period_start', 'period_end']

    def __str__(self):
        return f"Rapport {self.period_start} au {self.period_end} - {self.carrier}"

    def calculate_totals(self):
        """Calcule les totaux pour la période"""
        from django.db.models import Sum

        expenses = FinancialTransaction.objects.filter(
            carrier=self.carrier,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            transaction_date__range=[self.period_start, self.period_end],
            is_completed=True
        ).aggregate(total=Sum('amount'))['total'] or 0

        income = FinancialTransaction.objects.filter(
            carrier=self.carrier,
            transaction_type=FinancialTransaction.TransactionType.PAYMENT,
            transaction_date__range=[self.period_start, self.period_end],
            is_completed=True
        ).aggregate(total=Sum('amount'))['total'] or 0

        self.total_expenses = expenses
        self.total_income = income
        self.net_profit = income - expenses
        self.save()

        return {
            'expenses': expenses,
            'income': income,
            'profit': income - expenses
        }

    def generate_report(self):
        """Génère un rapport détaillé"""
        expenses = FinancialTransaction.objects.filter(
            carrier=self.carrier,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            transaction_date__range=[self.period_start, self.period_end],
            is_completed=True
        ).select_related('mission')

        income = FinancialTransaction.objects.filter(
            carrier=self.carrier,
            transaction_type=FinancialTransaction.TransactionType.PAYMENT,
            transaction_date__range=[self.period_start, self.period_end],
            is_completed=True
        ).select_related('mission')

        # Group by category
        expenses_by_category = {}
        for expense in expenses:
            category = expense.get_expense_category_display()
            if category not in expenses_by_category:
                expenses_by_category[category] = 0
            expenses_by_category[category] += expense.amount

        return {
            'period': {
                'start': self.period_start,
                'end': self.period_end
            },
            'carrier': {
                'name': self.carrier.user.get_full_name(),
                'company': self.carrier.company_name
            },
            'summary': {
                'total_income': self.total_income,
                'total_expenses': self.total_expenses,
                'net_profit': self.net_profit
            },
            'expenses_by_category': expenses_by_category,
            'detailed_expenses': [
                {
                    'date': e.transaction_date,
                    'category': e.get_expense_category_display(),
                    'description': e.expense_description,
                    'amount': e.amount,
                    'mission': e.mission.mission_number if e.mission else None
                }
                for e in expenses
            ],
            'detailed_income': [
                {
                    'date': i.transaction_date,
                    'mission': i.mission.mission_number if i.mission else None,
                    'payment_method': i.get_payment_method_display(),
                    'amount': i.amount
                }
                for i in income
            ]
        }


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

    # Badges de fiabilité
    recommended = models.BooleanField(
        default=False,
        verbose_name=_("Recommandé")
    )

    on_time = models.BooleanField(
        default=False,
        verbose_name=_("À l'heure")
    )

    careful = models.BooleanField(
        default=False,
        verbose_name=_("Soigneux")
    )

    good_communication = models.BooleanField(
        default=False,
        verbose_name=_("Bon communicateur")
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

    # Réponse aux avis
    carrier_response = models.TextField(
        blank=True,
        verbose_name=_("Réponse du transporteur")
    )

    response_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date de réponse")
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
            models.Index(fields=['rating', 'created_at']),
        ]

    def __str__(self):
        return f"Avis de {self.reviewer.username} sur {self.carrier} ({self.rating}/5)"

    def save(self, *args, **kwargs):
        # Mettre à jour les badges
        self.recommended = self.rating >= 4
        self.on_time = self.punctuality >= 4
        self.careful = self.handling >= 4
        self.good_communication = self.communication >= 4

        super().save(*args, **kwargs)

        # Mettre à jour la note moyenne du transporteur
        if self.carrier:
            self.carrier.update_average_rating()

    def delete(self, *args, **kwargs):
        carrier = self.carrier
        super().delete(*args, **kwargs)
        # Mettre à jour la note moyenne du transporteur
        if carrier:
            carrier.update_average_rating()

    def add_response(self, response_text):
        """Ajoute une réponse du transporteur"""
        self.carrier_response = response_text
        self.response_date = timezone.now()
        self.save()

class CarrierStatistics(models.Model):
    """Statistiques de performance détaillées"""

    carrier = models.OneToOneField(
        Carrier,
        on_delete=models.CASCADE,
        related_name='statistics',
        verbose_name=_("Transporteur")
    )

    # Taux de réussite par catégorie
    delivery_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Taux de livraison réussie (%)")
    )

    on_time_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Taux de ponctualité (%)")
    )

    satisfaction_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Taux de satisfaction (%)")
    )

    # Classement par zone
    zone_rankings = models.JSONField(
        default=dict,
        verbose_name=_("Classements par zone"),
        help_text=_("Format: {'zone': 'rank', ...}")
    )

    # Évolutions
    monthly_stats = models.JSONField(
        default=dict,
        verbose_name=_("Statistiques mensuelles"),
        help_text=_("Format: {'YYYY-MM': {'missions': X, 'revenue': Y}, ...}")
    )

    # Détails
    total_distance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Distance totale parcourue (km)")
    )

    total_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Heures totales de travail")
    )

    avg_delivery_time = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_("Temps moyen de livraison")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Statistique de transporteur")
        verbose_name_plural = _("Statistiques de transporteurs")

    def __str__(self):
        return f"Statistiques de {self.carrier}"

    def calculate_all_stats(self):
        """Calcule toutes les statistiques"""
        missions = self.carrier.missions.all()

        if not missions.exists():
            return

        completed_missions = missions.filter(status=Mission.MissionStatus.DELIVERED)

        # Taux de livraison réussie
        if missions.exists():
            self.delivery_success_rate = (completed_missions.count() / missions.count()) * 100

        # Taux de ponctualité
        on_time_missions = completed_missions.filter(
            actual_delivery_date__lte=models.F('preferred_delivery_date')
        )
        if completed_missions.exists():
            self.on_time_rate = (on_time_missions.count() / completed_missions.count()) * 100

        # Taux de satisfaction
        reviews = self.carrier.reviews.filter(is_approved=True, is_visible=True)
        if reviews.exists():
            avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.satisfaction_rate = (avg_rating / 5) * 100

        # Mettre à jour les statistiques mensuelles
        self.update_monthly_stats()

        self.save()

    def update_monthly_stats(self):
        """Met à jour les statistiques mensuelles"""
        from django.db.models import Sum, Count
        from datetime import datetime

        current_month = datetime.now().strftime('%Y-%m')

        monthly_data = self.monthly_stats or {}

        # Calculer pour le mois en cours
        current_month_start = datetime.now().replace(day=1)
        next_month_start = current_month_start.replace(month=current_month_start.month + 1)

        month_missions = self.carrier.missions.filter(
            created_at__gte=current_month_start,
            created_at__lt=next_month_start
        )

        month_revenue = FinancialTransaction.objects.filter(
            carrier=self.carrier,
            transaction_type=FinancialTransaction.TransactionType.PAYMENT,
            transaction_date__gte=current_month_start,
            transaction_date__lt=next_month_start,
            is_completed=True
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_data[current_month] = {
            'missions': month_missions.count(),
            'completed_missions': month_missions.filter(status=Mission.MissionStatus.DELIVERED).count(),
            'revenue': float(month_revenue),
            'distance': 0,  # À calculer avec le suivi GPS
            'hours': 0      # À calculer avec le temps de travail
        }

        self.monthly_stats = monthly_data
        self.save()


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
        # Initialiser les capacités disponibles si non définies
        if self.available_weight == 0 and self.carrier:
            self.available_weight = self.carrier.max_weight

        if self.available_volume == 0 and self.carrier:
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
        # Nouvelles notifications
        COLLECTION_DAY = 'COLLECTION_DAY', _('Jour de collecte')
        EXPENSE_ALERT = 'EXPENSE_ALERT', _('Alerte dépense')
        DOCUMENT_EXPIRY = 'DOCUMENT_EXPIRY', _('Document expiré')
        ROUTE_OPTIMIZED = 'ROUTE_OPTIMIZED', _('Itinéraire optimisé')
        NEW_OFFER = 'NEW_OFFER', _('Nouvelle offre')

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

    # Pour les alertes
    alert_level = models.CharField(
        max_length=20,
        choices=[
            ('INFO', _('Information')),
            ('WARNING', _('Avertissement')),
            ('URGENT', _('Urgent')),
        ],
        default='INFO',
        verbose_name=_("Niveau d'alerte")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification de transporteur")
        verbose_name_plural = _("Notifications de transporteurs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['carrier', 'is_read', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.title} - {self.carrier}"

    def mark_as_read(self):
        """Marque la notification comme lue"""
        self.is_read = True
        self.save(update_fields=['is_read'])


# === MODÈLES POUR LA MARKETPLACE ===

# === MODÈLES POUR LA MARKETPLACE ===

class CarrierOffer(models.Model):
    """Offre de service d'un transporteur"""

    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.CASCADE,
        related_name='offers',
        verbose_name=_("Transporteur")
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre de l'offre")
    )

    description = models.TextField(
        verbose_name=_("Description")
    )

    # Type d'offre
    offer_type = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', _('Immédiate')),
            ('SCHEDULED', _('Planifiée')),
            ('RECURRING', _('Récurrente')),
            ('GROUPED', _('Groupée')),
        ],
        default='IMMEDIATE',
        verbose_name=_("Type d'offre")
    )

    # Zone de service
    start_country = CountryField(
        verbose_name=_("Pays de départ")
    )

    start_city = models.CharField(
        max_length=100,
        verbose_name=_("Ville de départ")
    )

    end_country = CountryField(
        verbose_name=_("Pays d'arrivée")
    )

    end_city = models.CharField(
        max_length=100,
        verbose_name=_("Ville d'arrivée")
    )

    # Disponibilité
    available_from = models.DateTimeField(
        verbose_name=_("Disponible à partir du")
    )

    available_until = models.DateTimeField(
        verbose_name=_("Disponible jusqu'au")
    )

    # Prix
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Prix")
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

    # Capacités
    available_weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        verbose_name=_("Poids disponible (kg)")
    )

    available_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name=_("Volume disponible (m³)")
    )

    # Statut
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )

    is_booked = models.BooleanField(
        default=False,
        verbose_name=_("Réservée")
    )

    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre de vues")
    )

    inquiries_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre de demandes")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Offre de transporteur")
        verbose_name_plural = _("Offres de transporteurs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['carrier', 'is_active', 'available_from']),
            models.Index(fields=['start_country', 'end_country', 'is_active']),
            models.Index(fields=['offer_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.title} - {self.carrier}"

    def increment_views(self):
        """Incrémente le compteur de vues"""
        self.views_count += 1
        self.save(update_fields=['views_count'])

    def increment_inquiries(self):
        """Incrémente le compteur de demandes"""
        self.inquiries_count += 1
        self.save(update_fields=['inquiries_count'])

    def book(self):
        """Réserve l'offre"""
        self.is_booked = True
        self.save(update_fields=['is_booked'])

    def is_available(self):
        """Vérifie si l'offre est disponible"""
        now = timezone.now()
        return (
            self.is_active and
            not self.is_booked and
            self.available_from <= now <= self.available_until
        )


class CarrierSearch(models.Model):
    """Recherche sauvegardée pour les transporteurs"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='carrier_searches',
        verbose_name=_("Utilisateur")
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("Nom de la recherche")
    )

    # Critères de recherche
    search_criteria = models.JSONField(
        default=dict,
        verbose_name=_("Critères de recherche")
    )

    # Alertes
    alerts_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Alertes activées")
    )

    alert_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', _('Quotidien')),
            ('WEEKLY', _('Hebdomadaire')),
            ('IMMEDIATE', _('Immédiat')),
        ],
        default='DAILY',
        verbose_name=_("Fréquence des alertes")
    )

    last_alert_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dernière alerte envoyée")
    )

    # Résultats
    last_results_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre de résultats précédent")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Recherche de transporteur")
        verbose_name_plural = _("Recherches de transporteurs")
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'alerts_enabled']),
        ]

    def __str__(self):
        return f"{self.name} - {self.user}"

    def execute_search(self):
        """Exécute la recherche et retourne les résultats"""
        from django.db.models import Q

        # Construire la requête à partir des critères
        query = Q(status=Carrier.Status.APPROVED, is_available=True)

        criteria = self.search_criteria

        # Filtre par pays
        if criteria.get('start_country'):
            query &= Q(routes__start_country=criteria['start_country'])

        if criteria.get('end_country'):
            query &= Q(routes__end_country=criteria['end_country'])

        # Filtre par ville
        if criteria.get('start_city'):
            query &= Q(routes__start_city__icontains=criteria['start_city'])

        if criteria.get('end_city'):
            query &= Q(routes__end_city__icontains=criteria['end_city'])

        # Filtre par date
        if criteria.get('departure_date'):
            query &= Q(routes__departure_date=criteria['departure_date'])

        # Filtre par capacité
        if criteria.get('max_weight'):
            query &= Q(max_weight__gte=criteria['max_weight'])

        if criteria.get('max_volume'):
            query &= Q(max_volume__gte=criteria['max_volume'])

        # Filtre par type de véhicule
        if criteria.get('vehicle_types'):
            query &= Q(vehicle_type__in=criteria['vehicle_types'])

        # Filtre par note minimum
        if criteria.get('min_rating'):
            query &= Q(average_rating__gte=criteria['min_rating'])

        # Exécuter la requête
        results = Carrier.objects.filter(query).distinct()

        return results

    def check_new_results(self):
        """Vérifie s'il y a de nouveaux résultats"""
        current_results = self.execute_search()
        current_count = current_results.count()

        if current_count > self.last_results_count:
            new_count = current_count - self.last_results_count
            self.last_results_count = current_count
            self.save(update_fields=['last_results_count'])

            return {
                'has_new': True,
                'new_count': new_count,
                'total_count': current_count
            }

        return {
            'has_new': False,
            'new_count': 0,
            'total_count': current_count
        }
# ~/ebi3/colis/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import os
import uuid
from mptt.models import MPTTModel, TreeForeignKey
from django_countries.fields import CountryField

# Validateurs personnalisés
def validate_file_size(value):
    """Validateur pour la taille maximale des fichiers (10MB)"""
    filesize = value.size
    max_size = 10 * 1024 * 1024  # 10MB
    if filesize > max_size:
        raise ValidationError(
            _(f'La taille du fichier ne doit pas dépasser {max_size / (1024 * 1024):.0f}MB')
        )

class PackageCategory(MPTTModel):
    """Catégories de colis (hiérarchique)"""
    name = models.CharField(
        max_length=200,
        verbose_name=_("Nom de la catégorie"),
        db_index=True
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("Version URL-friendly du nom")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Description détaillée de la catégorie")
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_("Catégorie parente"),
        help_text=_("Sélectionnez une catégorie parente si applicable")
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Icône FontAwesome"),
        help_text=_("Exemple: fa-box, fa-couch, fa-tshirt")
    )
    image = models.ImageField(
        upload_to='colis/categories/',
        null=True,
        blank=True,
        verbose_name=_("Image de la catégorie")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Désactiver pour cacher la catégorie")
    )
    show_in_menu = models.BooleanField(
        default=True,
        verbose_name=_("Afficher dans le menu")
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage"),
        help_text=_("Plus le nombre est bas, plus c'est prioritaire")
    )
    requires_dimensions = models.BooleanField(
        default=True,
        verbose_name=_("Requiert dimensions"),
        help_text=_("Les colis de cette catégorie doivent avoir des dimensions")
    )
    requires_weight = models.BooleanField(
        default=True,
        verbose_name=_("Requiert poids"),
        help_text=_("Les colis de cette catégorie doivent avoir un poids")
    )
    meta_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Titre SEO")
    )
    meta_description = models.TextField(
        blank=True,
        verbose_name=_("Description SEO")
    )
    package_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre de colis")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['display_order', 'name']

    class Meta:
        verbose_name = _("Catégorie de colis")
        verbose_name_plural = _("Catégories de colis")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['parent', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('colis:category_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_full_path(self):
        ancestors = self.get_ancestors(include_self=True)
        return " > ".join([cat.name for cat in ancestors])

    def update_package_count(self):
        """Met à jour le compteur de colis"""
        count = self.packages.filter(status=Package.Status.AVAILABLE).count()
        PackageCategory.objects.filter(pk=self.pk).update(package_count=count)


class Package(models.Model):
    """Modèle principal pour un colis (équivalent Cocolis)"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Brouillon')
        AVAILABLE = 'AVAILABLE', _('Disponible')
        RESERVED = 'RESERVED', _('Réservé')
        IN_TRANSIT = 'IN_TRANSIT', _('En transit')
        DELIVERED = 'DELIVERED', _('Livré')
        CANCELLED = 'CANCELLED', _('Annulé')
        EXPIRED = 'EXPIRED', _('Expiré')

    class PackageType(models.TextChoices):
        SMALL_PACKAGE = 'SMALL_PACKAGE', _('Petit colis (< 30kg)')
        MEDIUM_PACKAGE = 'MEDIUM_PACKAGE', _('Colis moyen (30-100kg)')
        LARGE_PACKAGE = 'LARGE_PACKAGE', _('Gros colis (100-500kg)')
        FURNITURE = 'FURNITURE', _('Meuble')
        PALLET = 'PALLET', _('Palette')
        VEHICLE_PART = 'VEHICLE_PART', _('Pièce auto')
        OTHER = 'OTHER', _('Autre')

    class PriceType(models.TextChoices):
        FIXED = 'FIXED', _('Prix fixe')
        NEGOTIABLE = 'NEGOTIABLE', _('Prix négociable')
        AUCTION = 'AUCTION', _('Mise aux enchères')

    # Informations de base
    sender = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='sent_packages',
        verbose_name=_("Expéditeur")
    )
    category = TreeForeignKey(
        PackageCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='packages',
        verbose_name=_("Catégorie")
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre du colis"),
        db_index=True
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        db_index=True,
        verbose_name=_("Slug")
    )
    description = models.TextField(
        verbose_name=_("Description détaillée"),
        help_text=_("Décrivez votre colis en détail")
    )
    package_type = models.CharField(
        max_length=20,
        choices=PackageType.choices,
        verbose_name=_("Type de colis")
    )

    # Dimensions et poids
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        verbose_name=_("Poids (kg)"),
        help_text=_("Poids en kilogrammes")
    )
    length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Longueur (cm)")
    )
    width = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Largeur (cm)")
    )
    height = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Hauteur (cm)")
    )
    volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("Volume (L)")
    )

    # Origine et destination
    pickup_country = CountryField(
        verbose_name=_("Pays de départ"),
        help_text=_("Pays où se trouve le colis")
    )
    pickup_city = models.CharField(
        max_length=100,
        verbose_name=_("Ville de départ")
    )
    pickup_address = models.TextField(
        blank=True,
        verbose_name=_("Adresse de départ")
    )
    pickup_postal_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Code postal départ")
    )
    pickup_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude départ")
    )
    pickup_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude départ")
    )

    delivery_country = CountryField(
        verbose_name=_("Pays de destination"),
        help_text=_("Pays où le colis doit être livré")
    )
    delivery_city = models.CharField(
        max_length=100,
        verbose_name=_("Ville de destination")
    )
    delivery_address = models.TextField(
        blank=True,
        verbose_name=_("Adresse de destination")
    )
    delivery_postal_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Code postal destination")
    )
    delivery_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude destination")
    )
    delivery_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude destination")
    )

    # Dates
    pickup_date = models.DateField(
        verbose_name=_("Date de départ souhaitée"),
        help_text=_("Date à laquelle le colis est disponible")
    )
    delivery_date = models.DateField(
        verbose_name=_("Date de livraison souhaitée"),
        help_text=_("Date limite de livraison")
    )
    flexible_dates = models.BooleanField(
        default=False,
        verbose_name=_("Dates flexibles"),
        help_text=_("Accepte des dates différentes de celles demandées")
    )

    # Prix
    price_type = models.CharField(
        max_length=20,
        choices=PriceType.choices,
        default=PriceType.NEGOTIABLE,
        verbose_name=_("Type de prix")
    )
    asking_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Prix demandé"),
        help_text=_("Prix en devise de départ")
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
    estimated_distance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Distance estimée (km)")
    )

    # Options et caractéristiques
    is_fragile = models.BooleanField(
        default=False,
        verbose_name=_("Fragile")
    )
    requires_insurance = models.BooleanField(
        default=False,
        verbose_name=_("Requiert assurance")
    )
    insurance_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Valeur à assurer")
    )
    requires_packaging = models.BooleanField(
        default=False,
        verbose_name=_("Requiert emballage")
    )
    requires_loading_help = models.BooleanField(
        default=False,
        verbose_name=_("Requiert aide au chargement")
    )
    requires_unloading_help = models.BooleanField(
        default=False,
        verbose_name=_("Requiert aide au déchargement")
    )

    # Statut et métadonnées
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Statut"),
        db_index=True
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Colis en vedette")
    )
    featured_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("En vedette jusqu'au")
    )

    # SEO
    meta_keywords = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Mots-clés SEO")
    )
    meta_description = models.TextField(
        blank=True,
        verbose_name=_("Description SEO")
    )

    # Statistiques
    view_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre de vues")
    )
    offer_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre d'offres")
    )
    favorite_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre de favoris")
    )

    # Limites de publication
    free_images_allowed = models.PositiveIntegerField(
        default=5,
        verbose_name=_("Nombre de photos gratuites")
    )
    paid_images_used = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Photos payantes utilisées")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    reserved_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Colis")
        verbose_name_plural = _("Colis")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['sender', 'status']),
            models.Index(fields=['pickup_country', 'delivery_country']),
            models.Index(fields=['pickup_date', 'delivery_date']),
            models.Index(fields=['package_type', 'status']),
            models.Index(fields=['asking_price', 'status']),
        ]
        permissions = [
            ('can_feature_package', 'Peut mettre en vedette un colis'),
            ('can_moderate_package', 'Peut modérer les colis'),
        ]

    def __str__(self):
        return f"{self.title} - {self.sender.username}"

    def save(self, *args, **kwargs):
        # Génération automatique du slug
        if not self.slug:
            base_slug = slugify(self.title)
            self.slug = base_slug
            counter = 1
            while Package.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        # Calcul automatique du volume
        if self.length and self.width and self.height:
            self.volume = (self.length * self.width * self.height) / 1000

        # Mise à jour des dates de statut
        if self.status == self.Status.AVAILABLE and not self.published_at:
            self.published_at = timezone.now()

        if self.status == self.Status.RESERVED and not self.reserved_at:
            self.reserved_at = timezone.now()

        if self.status == self.Status.DELIVERED and not self.delivered_at:
            self.delivered_at = timezone.now()

        # Vérification d'expiration
        if self.delivery_date and self.delivery_date < timezone.now().date():
            if self.status == self.Status.AVAILABLE:
                self.status = self.Status.EXPIRED
                self.expired_at = timezone.now()

        super().save(*args, **kwargs)

        # Mise à jour du compteur de catégorie
        if self.category:
            self.category.update_package_count()

    def get_absolute_url(self):
        return reverse('colis:package_detail', kwargs={'slug': self.slug})

    def get_price_with_currency(self):
        return f"{self.asking_price} {self.get_currency_display()}"

    def calculate_free_images_remaining(self):
        return max(0, self.free_images_allowed - self.images.filter(is_paid=False).count())

    def is_available_for_offers(self):
        return self.status == self.Status.AVAILABLE

    def can_be_reserved(self, user):
        """Vérifie si un utilisateur peut réserver ce colis"""
        if user == self.sender:
            return False
        if self.status != self.Status.AVAILABLE:
            return False
        return True

    def get_estimated_price_range(self):
        """Retourne une fourchette de prix estimée basée sur la distance et le volume"""
        # Logique simplifiée - à améliorer avec des algorithmes réels
        if self.estimated_distance and self.volume:
            base_price_per_km = 0.5  # € par km
            base_price_per_volume = 10  # € par m³

            estimated_price = (
                self.estimated_distance * base_price_per_km +
                float(self.volume) / 1000 * base_price_per_volume
            )

            return {
                'min': round(estimated_price * 0.8, 2),
                'max': round(estimated_price * 1.2, 2),
                'average': round(estimated_price, 2)
            }
        return None

    def get_distance_display(self):
        """Affiche la distance de manière lisible"""
        if self.estimated_distance:
            if self.estimated_distance < 1:
                return f"{self.estimated_distance * 1000:.0f} m"
            return f"{self.estimated_distance:.1f} km"
        return _("Distance non calculée")


def package_image_upload_path(instance, filename):
    """Chemin de sauvegarde pour les images de colis"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"colis/{instance.package.sender.username}/{instance.package.slug}/images/{filename}"


class PackageImage(models.Model):
    """Images associées à un colis"""
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_("Colis")
    )
    image = models.ImageField(
        upload_to=package_image_upload_path,
        verbose_name=_("Image"),
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_file_size,
        ]
    )
    thumbnail = models.ImageField(
        upload_to='colis/thumbnails/',
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("Miniature")
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Légende")
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Image principale")
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Image de colis")
        verbose_name_plural = _("Images de colis")
        ordering = ['is_primary', 'display_order', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['package'],
                condition=models.Q(is_primary=True),
                name='unique_primary_image_per_package'
            )
        ]

    def __str__(self):
        return f"Image pour {self.package.title}"

    def save(self, *args, **kwargs):
        if not self.package.images.exists() and not self.is_primary:
            self.is_primary = True
        if self.is_primary:
            PackageImage.objects.filter(package=self.package, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class TransportOffer(models.Model):
    """Offre de transport pour un colis (comme Cocolis)"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        ACCEPTED = 'ACCEPTED', _('Acceptée')
        REJECTED = 'REJECTED', _('Rejetée')
        CANCELLED = 'CANCELLED', _('Annulée')
        EXPIRED = 'EXPIRED', _('Expirée')

    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='transport_offers',
        verbose_name=_("Colis")
    )
    carrier = models.ForeignKey(
        'carriers.Carrier',
        on_delete=models.CASCADE,
        related_name='transport_offers',
        verbose_name=_("Transporteur")
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Prix proposé")
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
    proposed_pickup_date = models.DateField(
        verbose_name=_("Date de départ proposée")
    )
    proposed_delivery_date = models.DateField(
        verbose_name=_("Date de livraison proposée")
    )
    message = models.TextField(
        blank=True,
        verbose_name=_("Message au vendeur"),
        help_text=_("Expliquez pourquoi vous êtes le bon transporteur")
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Statut")
    )

    # Informations supplémentaires
    provides_insurance = models.BooleanField(
        default=False,
        verbose_name=_("Fournit assurance")
    )
    insurance_coverage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Couverture d'assurance")
    )
    provides_packaging = models.BooleanField(
        default=False,
        verbose_name=_("Fournit emballage")
    )
    provides_loading = models.BooleanField(
        default=False,
        verbose_name=_("Fournit chargement")
    )
    provides_unloading = models.BooleanField(
        default=False,
        verbose_name=_("Fournit déchargement")
    )

    # Suivi
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_("Raison du refus")
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Accepté le")
    )
    expires_at = models.DateTimeField(
        verbose_name=_("Expire le"),
        help_text=_("Date d'expiration de l'offre")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Offre de transport")
        verbose_name_plural = _("Offres de transport")
        ordering = ['-created_at']
        unique_together = ['package', 'carrier']
        indexes = [
            models.Index(fields=['package', 'status']),
            models.Index(fields=['carrier', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f"Offre #{self.id} pour {self.package.title}"

    def save(self, *args, **kwargs):
        # Définir la date d'expiration par défaut (72h)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=72)

        # Mettre à jour le compteur d'offres du colis
        if not self.pk:  # Nouvelle offre
            super().save(*args, **kwargs)
            self.package.offer_count = self.package.transport_offers.count()
            self.package.save(update_fields=['offer_count'])
        else:
            super().save(*args, **kwargs)

        # Si l'offre est acceptée, marquer le colis comme réservé
        if self.status == self.Status.ACCEPTED and not self.accepted_at:
            self.accepted_at = timezone.now()
            self.package.status = Package.Status.RESERVED
            self.package.reserved_at = timezone.now()
            self.package.save(update_fields=['status', 'reserved_at'])

            # Rejeter automatiquement les autres offres en attente
            TransportOffer.objects.filter(
                package=self.package,
                status=self.Status.PENDING
            ).exclude(pk=self.pk).update(
                status=self.Status.REJECTED,
                rejection_reason=_("Une autre offre a été acceptée")
            )

    def is_expired(self):
        """Vérifie si l'offre a expiré"""
        return timezone.now() > self.expires_at

    def can_be_accepted(self):
        """Vérifie si l'offre peut être acceptée"""
        return (
            self.status == self.Status.PENDING and
            not self.is_expired() and
            self.package.status == Package.Status.AVAILABLE
        )


class PackageView(models.Model):
    """Suivi des vues de colis pour les statistiques"""
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='views_tracking',
        verbose_name=_("Colis")
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_views',
        verbose_name=_("Utilisateur")
    )
    session_key = models.CharField(
        max_length=40,
        db_index=True,
        verbose_name=_("Clé de session")
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("Adresse IP")
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_("User Agent")
    )
    referer = models.URLField(
        blank=True,
        verbose_name=_("Referer")
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Vue de colis")
        verbose_name_plural = _("Vues de colis")
        indexes = [
            models.Index(fields=['package', 'viewed_at']),
            models.Index(fields=['session_key', 'package']),
            models.Index(fields=['user', 'viewed_at']),
        ]

    def __str__(self):
        return f"Vue de {self.package.title} à {self.viewed_at}"


class PackageFavorite(models.Model):
    """Favoris des colis"""
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='package_favorites',
        verbose_name=_("Utilisateur")
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name=_("Colis")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Colis favori")
        verbose_name_plural = _("Colis favoris")
        unique_together = ['user', 'package']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} aime {self.package.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.package.favorite_count = self.package.favorited_by.count()
        self.package.save(update_fields=['favorite_count'])

    def delete(self, *args, **kwargs):
        package = self.package
        super().delete(*args, **kwargs)
        package.favorite_count = package.favorited_by.count()
        package.save(update_fields=['favorite_count'])


class PackageReport(models.Model):
    """Signalement de colis inappropriés"""

    class ReportReason(models.TextChoices):
        SPAM = 'SPAM', _('Spam ou publicité')
        FRAUD = 'FRAUD', _('Fraude ou arnaque')
        INAPPROPRIATE = 'INAPPROPRIATE', _('Contenu inapproprié')
        WRONG_CATEGORY = 'WRONG_CATEGORY', _('Mauvaise catégorie')
        PROHIBITED = 'PROHIBITED', _('Article prohibé')
        DUPLICATE = 'DUPLICATE', _('Colis en double')
        OTHER = 'OTHER', _('Autre')

    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name=_("Colis")
    )
    reporter = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='package_reports',
        verbose_name=_("Signaleur")
    )
    reason = models.CharField(
        max_length=20,
        choices=ReportReason.choices,
        verbose_name=_("Raison du signalement")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description détaillée")
    )
    evidence = models.FileField(
        upload_to='colis/reports/',
        null=True,
        blank=True,
        verbose_name=_("Preuve")
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', _('En attente')),
            ('IN_REVIEW', _('En revue')),
            ('RESOLVED', _('Résolu')),
            ('DISMISSED', _('Rejeté')),
        ],
        default='PENDING',
        verbose_name=_("Statut")
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de l'administrateur")
    )
    resolved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_package_reports',
        verbose_name=_("Résolu par")
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Résolu le")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Signalement de colis")
        verbose_name_plural = _("Signalements de colis")
        ordering = ['-created_at']

    def __str__(self):
        return f"Signalement de {self.package.title}"
# ~/ebi3/ads/models.py
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


# ~/ebi3/ads/models.py - Version corrigée de la classe AdImage
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
import os


# Validateurs personnalisés
def validate_file_size(value):
    """Validateur pour la taille maximale des fichiers (10MB)"""
    filesize = value.size
    max_size = 10 * 1024 * 1024  # 10MB
    if filesize > max_size:
        raise ValidationError(
            _(f'La taille du fichier ne doit pas dépasser {max_size / (1024 * 1024):.0f}MB')
        )

def validate_video_size(value):
    """Validateur pour la taille maximale des vidéos (100MB)"""
    filesize = value.size
    max_size = 100 * 1024 * 1024  # 100MB
    if filesize > max_size:
        raise ValidationError(
            _(f'La taille de la vidéo ne doit pas dépasser {max_size / (1024 * 1024):.0f}MB')
        )


class Category(MPTTModel):
    name = models.CharField(
        max_length=200,
        verbose_name=_("Nom de la catégorie"),
        db_index=True
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("URL-friendly version du nom")
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
        help_text=_("Exemple: fa-mobile, fa-car, fa-home")
    )
    image = models.ImageField(
        upload_to='categories/',
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
        default=False,
        verbose_name=_("Requiert dimensions"),
        help_text=_("Les annonces de cette catégorie doivent avoir des dimensions")
    )
    requires_weight = models.BooleanField(
        default=True,
        verbose_name=_("Requiert poids"),
        help_text=_("Les annonces de cette catégorie doivent avoir un poids")
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
    ad_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre d'annonces")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['display_order', 'name']

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['parent', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('ads:category_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_full_path(self):
        ancestors = self.get_ancestors(include_self=True)
        return " > ".join([cat.name for cat in ancestors])

    def update_ad_count(self):
        """Met à jour le compteur d'annonces sans import circulaire"""
        from .models import Ad  # Import local pour éviter les problèmes
        count = self.ads.filter(status=Ad.Status.ACTIVE).count()
        # Mise à jour directe en base pour éviter la récursion
        Category.objects.filter(pk=self.pk).update(ad_count=count)

# Dans ~/ebi3/ads/models.py, classe AdImage

def save(self, *args, **kwargs):
    super().save(*args, **kwargs)

    # Générer la miniature si elle n'existe pas
    if self.image and not self.thumbnail:
        img = Image.open(self.image.path)

        # Calculer les dimensions de la miniature (200x200)
        img.thumbnail((200, 200))

        # Préparer le nom du fichier thumbnail
        thumb_name, thumb_extension = os.path.splitext(self.image.name)
        thumb_extension = thumb_extension.lower()
        thumb_filename = thumb_name + '_thumb' + thumb_extension

        # Sauvegarder la miniature
        if thumb_extension in ['.jpg', '.jpeg']:
            FTYPE = 'JPEG'
        elif thumb_extension == '.gif':
            FTYPE = 'GIF'
        elif thumb_extension == '.png':
            FTYPE = 'PNG'
        else:
            FTYPE = 'JPEG'  # Par défaut

        temp_thumb = BytesIO()
        img.save(temp_thumb, FTYPE)
        temp_thumb.seek(0)

        # Sauvegarder dans le champ thumbnail
        self.thumbnail.save(
            thumb_filename,
            ContentFile(temp_thumb.read()),
            save=False
        )
        temp_thumb.close()

        super().save(*args, **kwargs)


class Ad(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Brouillon')
        PENDING = 'PENDING', _('En attente de validation')
        ACTIVE = 'ACTIVE', _('Active')
        RESERVED = 'RESERVED', _('Réservée')
        SOLD = 'SOLD', _('Vendue')
        EXPIRED = 'EXPIRED', _('Expirée')
        REJECTED = 'REJECTED', _('Rejetée')
        ARCHIVED = 'ARCHIVED', _('Archivée')

    class Condition(models.TextChoices):
        NEW = 'NEW', _('Neuf')
        LIKE_NEW = 'LIKE_NEW', _('Comme neuf')
        GOOD = 'GOOD', _('Bon état')
        FAIR = 'FAIR', _('État correct')
        POOR = 'POOR', _('Mauvais état')
        FOR_PARTS = 'FOR_PARTS', _('Pour pièces')

    class LogisticsOption(models.TextChoices):
        P2P_DIRECT = 'P2P_DIRECT', _('Vente directe (P2P)')
        WITH_CARRIER = 'WITH_CARRIER', _('Avec transporteur')
        WITH_EXPAT_CARRIER = 'WITH_EXPAT_CARRIER', _('Avec expatrié-transporteur')

    seller = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='ads',
        verbose_name=_("Vendeur")
    )
    category = TreeForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ads',
        verbose_name=_("Catégorie")
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre de l'annonce"),
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
        help_text=_("Décrivez votre objet en détail")
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD,
        verbose_name=_("État de l'objet")
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Prix"),
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
    is_negotiable = models.BooleanField(
        default=False,
        verbose_name=_("Prix négociable")
    )
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_("Poids (kg)"),
        help_text=_("Poids en kilogrammes")
    )
    length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Longueur (cm)")
    )
    width = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Largeur (cm)")
    )
    height = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
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
    country_from = CountryField(
        verbose_name=_("Pays de départ"),
        help_text=_("Pays où se trouve l'objet")
    )
    city_from = models.CharField(
        max_length=100,
        verbose_name=_("Ville de départ")
    )
    address_from = models.TextField(
        blank=True,
        verbose_name=_("Adresse de départ")
    )
    latitude_from = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude départ")
    )
    longitude_from = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude départ")
    )
    country_to = CountryField(
        verbose_name=_("Pays de destination"),
        help_text=_("Pays où l'objet doit être livré")
    )
    city_to = models.CharField(
        max_length=100,
        verbose_name=_("Ville de destination")
    )
    address_to = models.TextField(
        blank=True,
        verbose_name=_("Adresse de destination")
    )
    latitude_to = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude destination")
    )
    longitude_to = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude destination")
    )
    logistics_option = models.CharField(
        max_length=20,
        choices=LogisticsOption.choices,
        default=LogisticsOption.P2P_DIRECT,
        verbose_name=_("Option logistique")
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
        verbose_name=_("Valeur assurée")
    )
    fragile_item = models.BooleanField(
        default=False,
        verbose_name=_("Objet fragile")
    )
    requires_packaging = models.BooleanField(
        default=False,
        verbose_name=_("Requiert emballage")
    )
    available_from = models.DateField(
        verbose_name=_("Disponible à partir du"),
        help_text=_("Date à partir de laquelle l'objet est disponible"),
        default=timezone.now,  # ✅ Référence, pas appel
    )
    available_until = models.DateField(  # ⚠️ CORRIGÉ : virgule manquante ajoutée
        verbose_name=_("Disponible jusqu'au"),
        help_text=_("Date limite de disponibilité"),
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Statut"),
        db_index=True
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Annonce en vedette")
    )
    featured_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("En vedette jusqu'au")
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_("Raison du rejet")
    )
    meta_keywords = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Mots-clés SEO")
    )
    meta_description = models.TextField(
        blank=True,
        verbose_name=_("Description SEO")
    )
    view_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre de vues")
    )
    favorite_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre de favoris")
    )
    inquiry_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name=_("Nombre de demandes")
    )
    free_images_allowed = models.PositiveIntegerField(
        default=3,
        verbose_name=_("Nombre de photos gratuites")
    )
    paid_images_used = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Photos payantes utilisées")
    )
    videos_allowed = models.BooleanField(
        default=False,
        verbose_name=_("Vidéos autorisées")
    )
    videos_used = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Vidéos utilisées")
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Annonce")
        verbose_name_plural = _("Annonces")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['country_from', 'country_to']),
            models.Index(fields=['price', 'status']),
            models.Index(fields=['category', 'status']),
        ]
        permissions = [
            ('can_feature_ad', 'Peut mettre en vedette une annonce'),
            ('can_moderate_ad', 'Peut modérer les annonces'),
            ('can_view_statistics', 'Peut voir les statistiques'),
        ]

    def __str__(self):
        return f"{self.title} - {self.seller.username}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            self.slug = base_slug
            counter = 1
            while Ad.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        if self.length and self.width and self.height:
            self.volume = (self.length * self.width * self.height) / 1000

        if self.status == self.Status.ACTIVE and not self.published_at:
            self.published_at = timezone.now()

        if self.available_until and self.available_until < timezone.now().date():
            if self.status == self.Status.ACTIVE:
                self.status = self.Status.EXPIRED
                self.expired_at = timezone.now()

        super().save(*args, **kwargs)

        if self.category:
            self.category.update_ad_count()

    def get_absolute_url(self):
        return reverse('ads:ad_detail', kwargs={'slug': self.slug})

    def get_price_with_currency(self):
        return f"{self.price} {self.get_currency_display()}"

    def calculate_total_images(self):
        return self.images.count()

    def calculate_free_images_remaining(self):
        return max(0, self.free_images_allowed - self.images.filter(is_paid=False).count())

    def is_available_for_carrier(self):
        return self.status == self.Status.ACTIVE and self.logistics_option in [
            self.LogisticsOption.WITH_CARRIER,
            self.LogisticsOption.WITH_EXPAT_CARRIER
        ]

    def can_be_reserved(self, user):
        if user == self.seller:
            return False
        if self.status != self.Status.ACTIVE:
            return False
        return True


def ad_image_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"ads/{instance.ad.seller.username}/{instance.ad.slug}/images/{filename}"

class AdImage(models.Model):
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_("Annonce")
    )
    image = models.ImageField(
        upload_to=ad_image_upload_path,
        verbose_name=_("Image"),
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_file_size,
        ]
    )
    thumbnail = models.ImageField(
        upload_to='ads/thumbnails/',
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
    is_paid = models.BooleanField(
        default=False,
        verbose_name=_("Image payante")
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('FREE', _('Gratuite')),
            ('PAID', _('Payée')),
            ('PENDING', _('En attente')),
            ('FAILED', _('Échouée')),
        ],
        default='FREE',
        verbose_name=_("Statut du paiement")
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Référence de paiement")
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Image d'annonce")
        verbose_name_plural = _("Images d'annonces")
        ordering = ['is_primary', 'display_order', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['ad'],
                condition=models.Q(is_primary=True),
                name='unique_primary_image_per_ad'
            )
        ]

    def __str__(self):
        return f"Image pour {self.ad.title}"

    def save(self, *args, **kwargs):
        # Gérer l'image principale
        if not self.ad.images.exists() and not self.is_primary:
            self.is_primary = True

        if self.is_primary:
            AdImage.objects.filter(ad=self.ad, is_primary=True).exclude(pk=self.pk).update(is_primary=False)

        # Sauvegarder d'abord pour avoir un ID
        is_new = self._state.adding

        if is_new:
            # Pour une nouvelle image, sauvegarder d'abord sans thumbnail
            super().save(*args, **kwargs)

        # Générer la miniature si l'image existe et qu'on n'a pas de thumbnail
        if self.image and (is_new or not self.thumbnail):
            try:
                # Ouvrir l'image originale
                img = Image.open(self.image.path)

                # Convertir en RGB si nécessaire
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                # Calculer les dimensions de la miniature (200x200)
                img.thumbnail((200, 200), Image.Resampling.LANCZOS)

                # Préparer le nom du fichier thumbnail
                thumb_name, thumb_extension = os.path.splitext(self.image.name)
                thumb_extension = thumb_extension.lower()

                # Déterminer le format
                if thumb_extension in ['.jpg', '.jpeg']:
                    format = 'JPEG'
                    thumb_extension = '.jpg'
                elif thumb_extension == '.png':
                    format = 'PNG'
                elif thumb_extension == '.webp':
                    format = 'WEBP'
                elif thumb_extension == '.gif':
                    format = 'GIF'
                else:
                    format = 'JPEG'
                    thumb_extension = '.jpg'

                thumb_filename = f"{thumb_name}_thumb{thumb_extension}"

                # Sauvegarder la miniature
                temp_thumb = BytesIO()
                img.save(temp_thumb, format, quality=85)
                temp_thumb.seek(0)

                # Sauvegarder dans le champ thumbnail
                if self.thumbnail:
                    self.thumbnail.delete(save=False)

                self.thumbnail.save(
                    thumb_filename,
                    ContentFile(temp_thumb.read()),
                    save=False
                )
                temp_thumb.close()

            except Exception as e:
                # En cas d'erreur, on laisse thumbnail vide
                print(f"Erreur lors de la création de la miniature: {e}")
                # Ne pas bloquer la sauvegarde si la miniature échoue

        # Sauvegarder avec les modifications
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Supprime aussi les fichiers physiques"""
        if self.image:
            # Ne pas supprimer l'image si d'autres images y font référence
            # (dans le cas où plusieurs AdImage partagent le même fichier)
            pass
        if self.thumbnail:
            self.thumbnail.delete(save=False)
        super().delete(*args, **kwargs)

    @property
    def thumbnail_url(self):
        """Retourne l'URL de la miniature ou de l'image si pas de miniature"""
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail.url
        elif self.image and hasattr(self.image, 'url'):
            return self.image.url
        return ''

def ad_video_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"ads/{instance.ad.seller.username}/{instance.ad.slug}/videos/{filename}"


class AdVideo(models.Model):
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='videos',
        verbose_name=_("Annonce")
    )
    video = models.FileField(
        upload_to=ad_video_upload_path,
        verbose_name=_("Vidéo"),
        validators=[
            FileExtensionValidator(['mp4', 'avi', 'mov', 'wmv', 'webm']),
            validate_video_size,
        ]
    )
    thumbnail = models.ImageField(
        upload_to='ads/video_thumbnails/',
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("Miniature vidéo")
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Légende")
    )
    duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name=_("Durée")
    )
    is_paid = models.BooleanField(
        default=True,
        verbose_name=_("Vidéo payante")
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PAID', _('Payée')),
            ('PENDING', _('En attente')),
            ('FAILED', _('Échouée')),
        ],
        default='PENDING',
        verbose_name=_("Statut du paiement")
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Référence de paiement")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Vidéo d'annonce")
        verbose_name_plural = _("Vidéos d'annonces")

    def __str__(self):
        return f"Vidéo pour {self.ad.title}"


class Favorite(models.Model):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name=_("Utilisateur")
    )
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name=_("Annonce")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Favori")
        verbose_name_plural = _("Favoris")
        unique_together = ['user', 'ad']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} aime {self.ad.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.ad.favorite_count = self.ad.favorited_by.count()
        self.ad.save(update_fields=['favorite_count'])

    def delete(self, *args, **kwargs):
        ad = self.ad
        super().delete(*args, **kwargs)
        ad.favorite_count = ad.favorited_by.count()
        ad.save(update_fields=['favorite_count'])


class AdView(models.Model):
    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='views_tracking',
        verbose_name=_("Annonce")
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ad_views',
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
        verbose_name = _("Vue d'annonce")
        verbose_name_plural = _("Vues d'annonces")
        indexes = [
            models.Index(fields=['ad', 'viewed_at']),
            models.Index(fields=['session_key', 'ad']),
            models.Index(fields=['user', 'viewed_at']),
        ]

    def __str__(self):
        return f"Vue de {self.ad.title} à {self.viewed_at}"


class AdReport(models.Model):
    class ReportReason(models.TextChoices):
        SPAM = 'SPAM', _('Spam ou publicité')
        FRAUD = 'FRAUD', _('Fraude ou arnaque')
        INAPPROPRIATE = 'INAPPROPRIATE', _('Contenu inapproprié')
        WRONG_CATEGORY = 'WRONG_CATEGORY', _('Mauvaise catégorie')
        PROHIBITED = 'PROHIBITED', _('Article prohibé')
        DUPLICATE = 'DUPLICATE', _('Annonce en double')
        OTHER = 'OTHER', _('Autre')

    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name=_("Annonce")
    )
    reporter = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='ad_reports',
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
        upload_to='reports/',
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
        related_name='resolved_ad_reports',
        verbose_name=_("Résolu par")
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Résolu le")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Signalement d'annonce")
        verbose_name_plural = _("Signalements d'annonces")
        ordering = ['-created_at']

    def __str__(self):
        return f"Signalement de {self.ad.title}"
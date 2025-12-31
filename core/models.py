# ~/ebi3/core/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
import json

# SUPPRIMER cette ligne problématique (importation circulaire)
# from core.models import Country, City

class SiteSetting(models.Model):
    """Paramètres globaux du site"""

    class SettingType(models.TextChoices):
        STRING = 'STRING', _('Chaîne de caractères')
        INTEGER = 'INTEGER', _('Nombre entier')
        BOOLEAN = 'BOOLEAN', _('Booléen')
        JSON = 'JSON', _('JSON')
        TEXT = 'TEXT', _('Texte long')
        EMAIL = 'EMAIL', _('Email')
        URL = 'URL', _('URL')

    key = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Clé"),
        help_text=_("Identifiant unique du paramètre")
    )

    name = models.CharField(
        max_length=200,
        verbose_name=_("Nom affiché")
    )

    value = models.TextField(
        verbose_name=_("Valeur"),
        help_text=_("Valeur du paramètre")
    )

    setting_type = models.CharField(
        max_length=20,
        choices=SettingType.choices,
        default=SettingType.STRING,
        verbose_name=_("Type de paramètre")
    )

    group = models.CharField(
        max_length=50,
        default='general',
        verbose_name=_("Groupe"),
        help_text=_("Groupe de paramètres")
    )

    is_public = models.BooleanField(
        default=False,
        verbose_name=_("Public"),
        help_text=_("Peut être accédé dans les templates")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Description détaillée du paramètre")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Paramètre du site")
        verbose_name_plural = _("Paramètres du site")
        ordering = ['group', 'key']

    def __str__(self):
        return f"{self.name} ({self.key})"

    def get_value(self):
        """Retourne la valeur convertie selon le type"""
        if self.setting_type == self.SettingType.BOOLEAN:
            return self.value.lower() in ('true', '1', 'yes', 'y', 't')
        elif self.setting_type == self.SettingType.INTEGER:
            try:
                return int(self.value)
            except ValueError:
                return 0
        elif self.setting_type == self.SettingType.JSON:
            try:
                return json.loads(self.value)
            except json.JSONDecodeError:
                return {}
        else:
            return self.value

    @classmethod
    def get_setting(cls, key, default=None):
        """Récupère un paramètre avec cache"""
        cache_key = f'site_setting_{key}'
        value = cache.get(cache_key)

        if value is None:
            try:
                setting = cls.objects.get(key=key)
                value = setting.get_value()
                cache.set(cache_key, value, 3600)  # Cache pour 1 heure
            except cls.DoesNotExist:
                value = default
                cache.set(cache_key, value, 300)  # Cache court pour les valeurs par défaut

        return value

    @classmethod
    def set_setting(cls, key, value, setting_type='STRING'):
        """Définit un paramètre"""
        setting, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'name': key.replace('_', ' ').title(),
                'value': str(value),
                'setting_type': setting_type,
            }
        )

        if not created:
            setting.value = str(value)
            setting.setting_type = setting_type
            setting.save()

        # Invalider le cache
        cache.delete(f'site_setting_{key}')
        return setting


class Page(models.Model):
    """Pages statiques du site"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Brouillon')
        PUBLISHED = 'PUBLISHED', _('Publié')
        HIDDEN = 'HIDDEN', _('Caché')

    title = models.CharField(
        max_length=200,
        verbose_name=_("Titre")
    )

    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("URL de la page")
    )

    content = models.TextField(
        verbose_name=_("Contenu"),
        help_text=_("Contenu de la page (HTML autorisé)")
    )

    language = models.CharField(
        max_length=10,
        choices=[
            ('all', _('Toutes les langues')),
            ('ar', 'العربية'),
            ('fr', 'Français'),
            ('en', 'English'),
            ('de', 'Deutsch'),
            ('it', 'Italiano'),
            ('es', 'Español'),
            ('pt', 'Português'),
            ('pl', 'Polski'),
        ],
        default='all',
        verbose_name=_("Langue")
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Statut")
    )

    show_in_footer = models.BooleanField(
        default=False,
        verbose_name=_("Afficher dans le pied de page")
    )

    show_in_menu = models.BooleanField(
        default=False,
        verbose_name=_("Afficher dans le menu")
    )

    menu_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre dans le menu")
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

    meta_keywords = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Mots-clés SEO")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        ordering = ['menu_order', 'title']
        indexes = [
            models.Index(fields=['slug', 'status']),
            models.Index(fields=['language', 'status']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        # Générer le slug s'il n'existe pas
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:page', kwargs={'slug': self.slug})


class Country(models.Model):
    """Pays supportés avec informations spécifiques"""

    code = models.CharField(
        max_length=2,
        unique=True,
        verbose_name=_("Code ISO")
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("Nom")
    )

    name_ar = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nom en arabe")
    )

    name_fr = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nom en français")
    )

    name_en = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nom en anglais")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif"),
        help_text=_("Le pays est-il disponible sur la plateforme ?")
    )

    is_departure = models.BooleanField(
        default=True,
        verbose_name=_("Pays de départ"),
        help_text=_("Peut être un pays de départ")
    )

    is_destination = models.BooleanField(
        default=True,
        verbose_name=_("Pays de destination"),
        help_text=_("Peut être un pays de destination")
    )

    currency_code = models.CharField(
        max_length=3,
        default='EUR',
        verbose_name=_("Code devise")
    )

    currency_symbol = models.CharField(
        max_length=10,
        default='€',
        verbose_name=_("Symbole devise")
    )

    phone_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_("Indicatif téléphonique")
    )

    flag = models.ImageField(
        upload_to='flags/',
        null=True,
        blank=True,
        verbose_name=_("Drapeau")
    )

    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Pays")
        verbose_name_plural = _("Pays")
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_name(self, language=None):
        """Retourne le nom dans la langue spécifiée"""
        if language == 'ar' and self.name_ar:
            return self.name_ar
        elif language == 'fr' and self.name_fr:
            return self.name_fr
        elif language == 'en' and self.name_en:
            return self.name_en
        return self.name


class City(models.Model):
    """Villes supportées avec géolocalisation"""

    name = models.CharField(
        max_length=100,
        verbose_name=_("Nom de la ville")
    )

    name_ar = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nom en arabe")
    )

    name_fr = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nom en français")
    )

    name_en = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nom en anglais")
    )

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='cities',
        verbose_name=_("Pays")
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitude")
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitude")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )

    population = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Population")
    )

    timezone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Fuseau horaire")
    )

    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Ville")
        verbose_name_plural = _("Villes")
        ordering = ['country', 'display_order', 'name']
        unique_together = ['name', 'country']
        indexes = [
            models.Index(fields=['country', 'is_active']),
            models.Index(fields=['name', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name}, {self.country.name}"

    def get_name(self, language=None):
        """Retourne le nom dans la langue spécifiée"""
        if language == 'ar' and self.name_ar:
            return self.name_ar
        elif language == 'fr' and self.name_fr:
            return self.name_fr
        elif language == 'en' and self.name_en:
            return self.name_en
        return self.name


class FAQ(models.Model):
    """FAQ du site"""

    class Category(models.TextChoices):
        GENERAL = 'GENERAL', _('Général')
        ACCOUNT = 'ACCOUNT', _('Compte')
        ADS = 'ADS', _('Annonces')
        PAYMENTS = 'PAYMENTS', _('Paiements')
        LOGISTICS = 'LOGISTICS', _('Logistique')
        LEGAL = 'LEGAL', _('Légal')

    question = models.CharField(
        max_length=500,
        verbose_name=_("Question")
    )

    answer = models.TextField(
        verbose_name=_("Réponse")
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL,
        verbose_name=_("Catégorie")
    )

    language = models.CharField(
        max_length=10,
        choices=[
            ('ar', 'العربية'),
            ('fr', 'Français'),
            ('en', 'English'),
            ('de', 'Deutsch'),
            ('it', 'Italiano'),
            ('es', 'Español'),
            ('pt', 'Português'),
            ('pl', 'Polski'),
        ],
        default='fr',
        verbose_name=_("Langue")
    )

    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQs")
        ordering = ['category', 'display_order', 'question']
        indexes = [
            models.Index(fields=['category', 'language', 'is_active']),
        ]

    def __str__(self):
        return f"{self.question[:50]}..."


class NewsletterSubscriber(models.Model):
    """Abonnés à la newsletter"""

    email = models.EmailField(
        unique=True,
        verbose_name=_("Email")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )

    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Abonné newsletter")
        verbose_name_plural = _("Abonnés newsletter")
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email

    def unsubscribe(self):
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save()


class ContactMessage(models.Model):
    """Messages de contact"""

    class Status(models.TextChoices):
        NEW = 'NEW', _('Nouveau')
        IN_PROGRESS = 'IN_PROGRESS', _('En cours')
        RESOLVED = 'RESOLVED', _('Résolu')
        SPAM = 'SPAM', _('Spam')

    name = models.CharField(
        max_length=100,
        verbose_name=_("Nom")
    )

    email = models.EmailField(
        verbose_name=_("Email")
    )

    subject = models.CharField(
        max_length=200,
        verbose_name=_("Sujet")
    )

    message = models.TextField(
        verbose_name=_("Message")
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name=_("Statut")
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

    admin_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de l'administrateur")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Message de contact")
        verbose_name_plural = _("Messages de contact")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} - {self.email}"
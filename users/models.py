# ~/ebi3/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django_countries.fields import CountryField

class User(AbstractUser):
    """Modèle utilisateur personnalisé pour la plateforme ebi3"""

    # Rôles disponibles
    class Role(models.TextChoices):
        BUYER = 'BUYER', _('Acheteur')
        SELLER = 'SELLER', _('Vendeur')
        CARRIER = 'CARRIER', _('Transporteur Professionnel')
        CARRIER_PERSONAL = 'CARRIER_PERSONAL', _('Transporteur Particulier')
        ADMIN = 'ADMIN', _('Administrateur')
        MODERATOR = 'MODERATOR', _('Modérateur')

    # Champs supplémentaires
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.BUYER,
        verbose_name=_("Rôle")
    )

    phone = PhoneNumberField(
        verbose_name=_("Numéro de téléphone"),
        null=True,
        blank=True
    )

    country = CountryField(
        verbose_name=_("Pays"),
        blank=True,
        null=True
    )

    city = models.CharField(
        max_length=100,
        verbose_name=_("Ville"),
        blank=True
    )

    address = models.TextField(
        verbose_name=_("Adresse"),
        blank=True
    )

    # Vérification et statuts
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Compte vérifié")
    )

    kyc_verified = models.BooleanField(
        default=False,
        verbose_name=_("KYC vérifié")
    )

    email_verified = models.BooleanField(
        default=False,
        verbose_name=_("Email vérifié")
    )

    phone_verified = models.BooleanField(
        default=False,
        verbose_name=_("Téléphone vérifié")
    )

    kyc_submitted = models.BooleanField(
        default=False,
        verbose_name=_("KYC soumis")
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Date de mise à jour")
    )

    # Préférences
    preferred_language = models.CharField(
        max_length=10,
        default='fr',
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
        verbose_name=_("Langue préférée")
    )

    # Pour transporteurs
    is_available = models.BooleanField(
        default=True,
        verbose_name=_("Disponible pour des missions")
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Note moyenne")
    )

    total_reviews = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre total d'avis")
    )

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def is_carrier(self):
        """Vérifie si l'utilisateur est un transporteur"""
        return self.role in [self.Role.CARRIER, self.Role.CARRIER_PERSONAL]

    def is_seller(self):
        """Vérifie si l'utilisateur est un vendeur"""
        return self.role == self.Role.SELLER

    def is_buyer(self):
        """Vérifie si l'utilisateur est un acheteur"""
        return self.role == self.Role.BUYER

# ~/ebi3/users/models.py (suite)
class UserProfile(models.Model):
    """Profil étendu pour les utilisateurs"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_("Utilisateur")
    )

    # Informations personnelles
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date de naissance")
    )

    gender = models.CharField(
        max_length=10,
        choices=[
            ('M', _('Masculin')),
            ('F', _('Féminin')),
            ('O', _('Autre')),
        ],
        blank=True,
        verbose_name=_("Genre")
    )

    # Pour transporteurs professionnels
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
        verbose_name=_("Numéro fiscal")
    )

    # Documents pour vérification
    id_document = models.FileField(
        upload_to='documents/id/',
        null=True,
        blank=True,
        verbose_name=_("Document d'identité")
    )

    proof_of_address = models.FileField(
        upload_to='documents/address/',
        null=True,
        blank=True,
        verbose_name=_("Justificatif de domicile")
    )

    company_registration_doc = models.FileField(
        upload_to='documents/company/',
        null=True,
        blank=True,
        verbose_name=_("Document d'immatriculation")
    )

    # Pour expatriés
    country_of_origin = CountryField(
        verbose_name=_("Pays d'origine"),
        blank=True,
        null=True
    )

    country_of_residence = CountryField(
        verbose_name=_("Pays de résidence"),
        blank=True,
        null=True
    )

    is_expatriate = models.BooleanField(
        default=False,
        verbose_name=_("Est un expatrié")
    )

    # Statistiques
    total_ads = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre total d'annonces")
    )

    successful_transactions = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Transactions réussies")
    )

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Date de mise à jour")
    )

    class Meta:
        verbose_name = _("Profil utilisateur")
        verbose_name_plural = _("Profils utilisateurs")

    def __str__(self):
        return f"Profil de {self.user.username}"


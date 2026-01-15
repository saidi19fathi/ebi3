# ~/ebi3/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django_countries import countries
from phonenumber_field.formfields import PhoneNumberField
from datetime import datetime
import logging
import os

from .models import User, UserProfile
from carriers.models import Carrier, MerchandiseTypes

logger = logging.getLogger(__name__)

class CarrierRegistrationForm(UserCreationForm):
    """
    FORMULAIRE UNIFIÉ D'INSCRIPTION TRANSPORTEUR
    Crée à la fois : User + UserProfile + Carrier
    """

    # ========== CHAMPS UTILISATEUR ==========
    email = forms.EmailField(
        label=_("Email *"),
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('votre@email.com'),
            'autocomplete': 'email'
        })
    )

    phone = PhoneNumberField(
        label=_("Téléphone *"),
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('+212612345678'),
            'autocomplete': 'tel'
        })
    )

    first_name = forms.CharField(
        label=_("Prénom *"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('Votre prénom'),
            'autocomplete': 'given-name'
        })
    )

    last_name = forms.CharField(
        label=_("Nom *"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('Votre nom'),
            'autocomplete': 'family-name'
        })
    )

    country = forms.ChoiceField(
        label=_("Pays *"),
        required=True,
        choices=[('', _('Sélectionnez votre pays'))] + list(countries),
        widget=forms.Select(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'country'
        })
    )

    city = forms.CharField(
        label=_("Ville"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Votre ville'),
            'autocomplete': 'address-level2'
        })
    )

    address = forms.CharField(
        label=_("Adresse"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Votre adresse complète'),
            'autocomplete': 'street-address'
        })
    )

    preferred_language = forms.ChoiceField(
        label=_("Langue préférée"),
        choices=User._meta.get_field('preferred_language').choices,
        initial='fr',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    # ========== TYPE DE TRANSPORTEUR ==========
    carrier_type = forms.ChoiceField(
        label=_("Type de transporteur *"),
        choices=Carrier.CarrierType.choices,
        widget=forms.Select(attrs={
            'class': 'form-control form-control-lg',
            'id': 'id_carrier_type'
        })
    )

    # ========== CHAMPS ENTREPRISE (PROFESSIONNEL) ==========
    transport_company_name = forms.CharField(
        label=_("Nom de l'entreprise"),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom de votre entreprise de transport'),
            'id': 'id_company_name'
        })
    )

    transport_company_registration = forms.CharField(
        label=_("Numéro d'immatriculation"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Numéro d'immatriculation de l'entreprise")
        })
    )

    transport_tax_id = forms.CharField(
        label=_("Numéro fiscal"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Numéro fiscal/TVA')
        })
    )

    transport_company_address = forms.CharField(
        label=_("Adresse de l'entreprise"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Adresse complète de l\'entreprise')
        })
    )

    # ========== VÉHICULE ==========
    vehicle_type = forms.ChoiceField(
        label=_("Type de véhicule *"),
        choices=Carrier.VehicleType.choices,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_vehicle_type'
        })
    )

    vehicle_make = forms.CharField(
        label=_("Marque du véhicule"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ex: Renault, Mercedes, etc.')
        })
    )

    vehicle_model = forms.CharField(
        label=_("Modèle du véhicule"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Modèle du véhicule')
        })
    )

    vehicle_year = forms.IntegerField(
        label=_("Année du véhicule"),
        required=False,
        min_value=1990,
        max_value=datetime.now().year + 1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ex: 2023')
        })
    )

    vehicle_registration = forms.CharField(
        label=_("Plaque d'immatriculation"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Plaque d\'immatriculation')
        })
    )

    # ========== CAPACITÉS ==========
    max_weight = forms.DecimalField(
        label=_("Poids maximum (kg) *"),
        min_value=0.001,
        max_digits=8,
        decimal_places=3,
        initial=1000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001',
            'placeholder': _('Ex: 1500 pour 1.5 tonnes')
        })
    )

    max_volume = forms.DecimalField(
        label=_("Volume maximum (m³) *"),
        min_value=0.001,
        max_digits=10,
        decimal_places=3,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001',
            'placeholder': _('Ex: 10 pour 10 mètres cubes')
        })
    )

    max_length = forms.DecimalField(
        label=_("Longueur maximum (m)"),
        min_value=0.01,
        max_digits=6,
        decimal_places=2,
        required=False,
        initial=1.5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )

    max_width = forms.DecimalField(
        label=_("Largeur maximum (m)"),
        min_value=0.01,
        max_digits=6,
        decimal_places=2,
        required=False,
        initial=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )

    max_height = forms.DecimalField(
        label=_("Hauteur maximum (m)"),
        min_value=0.01,
        max_digits=6,
        decimal_places=2,
        required=False,
        initial=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )

    # ========== SERVICES PROPOSÉS ==========
    provides_packaging = forms.BooleanField(
        label=_("Fournit l'emballage"),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    provides_insurance = forms.BooleanField(
        label=_("Fournit l'assurance transport"),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    provides_loading = forms.BooleanField(
        label=_("Fournit le chargement"),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    provides_unloading = forms.BooleanField(
        label=_("Fournit le déchargement"),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    # ========== TARIFICATION ==========
    base_price_per_km = forms.DecimalField(
        label=_("Prix de base par km (€) *"),
        min_value=0,
        max_digits=8,
        decimal_places=4,
        initial=1.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.0001',
            'placeholder': _('Ex: 1.50 pour 1.50€/km')
        })
    )

    min_price = forms.DecimalField(
        label=_("Prix minimum (€) *"),
        min_value=0,
        max_digits=8,
        decimal_places=2,
        initial=10.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': _('Ex: 10 pour 10€ minimum')
        })
    )

    currency = forms.ChoiceField(
        label=_("Devise *"),
        choices=Carrier._meta.get_field('currency').choices,
        initial='EUR',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    # ========== ZONES DE COUVERTURE ==========
    coverage_cities = forms.CharField(
        label=_("Villes de couverture"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Paris, Lyon, Marseille... (séparées par des virgules)')
        })
    )

    # ========== TYPES DE MARCHANDISES ==========
    accepted_merchandise_types = forms.MultipleChoiceField(
        label=_("Types de marchandises acceptées"),
        choices=MerchandiseTypes.STANDARD,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input merchandise-checkbox'
        })
    )

    custom_merchandise_types = forms.CharField(
        label=_("Autres types de marchandises"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Séparez par des virgules'),
            'id': 'id_custom_merchandise_types'
        })
    )

    # ========== PHOTOS ET DOCUMENTS ==========
    profile_photo = forms.ImageField(
        label=_("Photo de profil"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )

    id_front = forms.ImageField(
        label=_("Recto pièce d'identité *"),
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'id_id_front'
        })
    )

    id_back = forms.ImageField(
        label=_("Verso pièce d'identité"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'id_id_back'
        })
    )

    # ========== CONDITIONS ==========
    rgpd_consent = forms.BooleanField(
        label=_("J'accepte la politique de confidentialité *"),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_rgpd_consent'
        })
    )

    terms_accepted = forms.BooleanField(
        label=_("J'accepte les conditions générales d'utilisation *"),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_terms_accepted'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': _("Nom d'utilisateur"),
                'autocomplete': 'username'
            }),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': _('Mot de passe sécurisé'),
                'autocomplete': 'new-password'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': _('Confirmez le mot de passe'),
                'autocomplete': 'new-password'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Réorganiser l'ordre des champs
        self.fields['username'].required = True
        self.fields['username'].label = _("Nom d'utilisateur *")

        # Définir un ordre personnalisé pour les champs
        self.order_fields([
            'first_name', 'last_name', 'email', 'username',
            'password1', 'password2', 'phone', 'country',
            'city', 'address', 'preferred_language',
            'carrier_type', 'transport_company_name',
            'transport_company_registration', 'transport_tax_id',
            'transport_company_address', 'vehicle_type',
            'vehicle_make', 'vehicle_model', 'vehicle_year',
            'vehicle_registration', 'max_weight', 'max_volume',
            'max_length', 'max_width', 'max_height',
            'provides_packaging', 'provides_insurance',
            'provides_loading', 'provides_unloading',
            'base_price_per_km', 'min_price', 'currency',
            'coverage_cities', 'accepted_merchandise_types',
            'custom_merchandise_types', 'profile_photo',
            'id_front', 'id_back', 'rgpd_consent', 'terms_accepted'
        ])

        # Masquer certains champs initialement
        self.fields['custom_merchandise_types'].widget.attrs['style'] = 'display: none;'

        # Ajouter du JavaScript pour gérer l'affichage conditionnel
        self.fields['carrier_type'].widget.attrs['onchange'] = 'toggleCompanyFields()'
        self.fields['accepted_merchandise_types'].widget.attrs['onchange'] = 'toggleCustomMerchandise()'

    def clean(self):
        """Validation croisée des données"""
        cleaned_data = super().clean()

        # Validation du type de transporteur
        carrier_type = cleaned_data.get('carrier_type')

        if carrier_type == Carrier.CarrierType.PROFESSIONAL:
            company_name = cleaned_data.get('transport_company_name', '').strip()
            if not company_name:
                self.add_error('transport_company_name',
                    _("Le nom de l'entreprise est obligatoire pour les transporteurs professionnels"))

        # Validation type de véhicule vs capacités
        vehicle_type = cleaned_data.get('vehicle_type')
        max_weight = cleaned_data.get('max_weight', 0)
        max_volume = cleaned_data.get('max_volume', 0)

        if vehicle_type and max_weight and max_volume:
            vehicle_limits = {
                'CAR': {'max_weight': 500, 'max_volume': 2},
                'VAN': {'max_weight': 1500, 'max_volume': 10},
                'TRUCK_SMALL': {'max_weight': 3500, 'max_volume': 30},
                'TRUCK_MEDIUM': {'max_weight': 7500, 'max_volume': 50},
                'TRUCK_LARGE': {'max_weight': 20000, 'max_volume': 100},
                'MOTORCYCLE': {'max_weight': 50, 'max_volume': 0.5},
                'OTHER': {'max_weight': 10000, 'max_volume': 50},
            }

            if vehicle_type in vehicle_limits:
                limits = vehicle_limits[vehicle_type]
                if max_weight > limits['max_weight']:
                    self.add_error('max_weight',
                        _("Ce poids dépasse la capacité typique d'un {} (max: {} kg)").format(
                            dict(Carrier.VehicleType.choices)[vehicle_type],
                            limits['max_weight']
                        ))
                if max_volume > limits['max_volume']:
                    self.add_error('max_volume',
                        _("Ce volume dépasse la capacité typique d'un {} (max: {} m³)").format(
                            dict(Carrier.VehicleType.choices)[vehicle_type],
                            limits['max_volume']
                        ))

        # Validation des photos
        id_front = cleaned_data.get('id_front')
        if id_front:
            # Vérifier la taille du fichier (max 5MB)
            if id_front.size > 5 * 1024 * 1024:
                self.add_error('id_front', _("La photo est trop volumineuse. Taille max: 5MB"))

            # Vérifier le type de fichier
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(id_front.name)[1].lower()
            if ext not in valid_extensions:
                self.add_error('id_front', _("Format de fichier non supporté. Formats acceptés: JPG, PNG, GIF"))

        return cleaned_data

    def clean_email(self):
        """Validation unique de l'email"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("Un compte avec cet email existe déjà"))
        return email

    def clean_phone(self):
        """Validation unique du téléphone"""
        phone = self.cleaned_data.get('phone')
        if User.objects.filter(phone=phone).exists():
            raise ValidationError(_("Un compte avec ce numéro de téléphone existe déjà"))
        return phone


    def save(self, commit=True):
        """
        Crée l'utilisateur, son profil et le profil transporteur
        """
        try:
            # ========== CRÉATION DE L'UTILISATEUR ==========
            carrier_type = self.cleaned_data['carrier_type']

            # Déterminer le rôle
            if carrier_type == Carrier.CarrierType.PROFESSIONAL:
                user_role = User.Role.CARRIER
            else:
                user_role = User.Role.CARRIER_PERSONAL

            # Créer l'utilisateur avec UserCreationForm
            user = super().save(commit=False)
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.phone = self.cleaned_data['phone']
            user.country = self.cleaned_data['country']
            user.city = self.cleaned_data.get('city', '')
            user.address = self.cleaned_data.get('address', '')
            user.preferred_language = self.cleaned_data.get('preferred_language', 'fr')
            user.role = user_role
            user.is_available = True
            user.is_verified = False
            user.kyc_verified = False
            user.email_verified = False
            user.phone_verified = False

            if commit:
                user.save()
                logger.info(f"Utilisateur créé: {user.username}")

            # ========== CRÉATION DU PROFIL UTILISATEUR ==========
            try:
                profile, created = UserProfile.objects.get_or_create(user=user)

                if carrier_type == Carrier.CarrierType.PROFESSIONAL:
                    profile.company_name = self.cleaned_data.get('transport_company_name', '')
                    profile.company_registration = self.cleaned_data.get('transport_company_registration', '')
                    profile.tax_id = self.cleaned_data.get('transport_tax_id', '')

                profile.save()
                logger.info(f"UserProfile {'créé' if created else 'mis à jour'} pour {user.username}")

            except Exception as e:
                logger.error(f"Erreur UserProfile pour {user.username}: {e}")

            # ========== CRÉATION DU PROFIL TRANSPORTEUR ==========
            try:
                # Vérifier si un profil transporteur existe déjà
                if hasattr(user, 'carrier_profile'):
                    carrier = user.carrier_profile
                    logger.warning(f"Profil transporteur existant pour {user.username}, mise à jour")
                    created_carrier = False
                else:
                    carrier = Carrier(user=user)
                    created_carrier = True

                # Remplir les champs de base
                carrier.carrier_type = carrier_type
                carrier.vehicle_type = self.cleaned_data['vehicle_type']
                carrier.vehicle_make = self.cleaned_data.get('vehicle_make', '')
                carrier.vehicle_model = self.cleaned_data.get('vehicle_model', '')
                carrier.vehicle_year = self.cleaned_data.get('vehicle_year')
                carrier.vehicle_registration = self.cleaned_data.get('vehicle_registration', '')
                carrier.max_weight = self.cleaned_data['max_weight']
                carrier.max_volume = self.cleaned_data['max_volume']
                carrier.max_length = self.cleaned_data.get('max_length', 1.5)
                carrier.max_width = self.cleaned_data.get('max_width', 1.0)
                carrier.max_height = self.cleaned_data.get('max_height', 1.0)
                carrier.provides_packaging = self.cleaned_data.get('provides_packaging', False)
                carrier.provides_insurance = self.cleaned_data.get('provides_insurance', False)
                carrier.provides_loading = self.cleaned_data.get('provides_loading', False)
                carrier.provides_unloading = self.cleaned_data.get('provides_unloading', False)
                carrier.base_price_per_km = self.cleaned_data['base_price_per_km']
                carrier.min_price = self.cleaned_data['min_price']
                carrier.currency = self.cleaned_data['currency']
                carrier.coverage_cities = self.cleaned_data.get('coverage_cities', '')
                carrier.transport_is_available = True
                carrier.status = Carrier.Status.PENDING
                carrier.verification_level = 0

                # Champs entreprise pour professionnels
                if carrier_type == Carrier.CarrierType.PROFESSIONAL:
                    carrier.transport_company_name = self.cleaned_data.get('transport_company_name', '')
                    carrier.transport_company_registration = self.cleaned_data.get('transport_company_registration', '')
                    carrier.transport_tax_id = self.cleaned_data.get('transport_tax_id', '')
                    carrier.transport_company_address = self.cleaned_data.get('transport_company_address', '')

                # Types de marchandises
                accepted_types = self.cleaned_data.get('accepted_merchandise_types', [])
                if accepted_types:
                    carrier.accepted_merchandise_types = accepted_types

                custom_types = self.cleaned_data.get('custom_merchandise_types', '')
                if custom_types:
                    carrier.custom_merchandise_types = custom_types

                # IMPORTANT: Traitement des fichiers images
                if self.cleaned_data.get('profile_photo'):
                    carrier.profile_photo = self.cleaned_data['profile_photo']
                    logger.info(f"Photo de profil enregistrée pour {user.username}")

                if self.cleaned_data.get('id_front'):
                    carrier.id_front = self.cleaned_data['id_front']
                    logger.info(f"ID front enregistrée pour {user.username}")

                if self.cleaned_data.get('id_back'):
                    carrier.id_back = self.cleaned_data['id_back']
                    logger.info(f"ID back enregistrée pour {user.username}")

                # Sauvegarder le carrier avec commit=True
                if commit:
                    carrier.save()

                    if created_carrier:
                        logger.info(f"Carrier créé avec succès: {user.username} (ID: {carrier.id})")
                    else:
                        logger.info(f"Carrier mis à jour: {user.username} (ID: {carrier.id})")

            except Exception as e:
                logger.error(f"Erreur lors de la création du Carrier pour {user.username}: {e}", exc_info=True)
                # Si le Carrier échoue, on peut quand même garder l'utilisateur
                raise ValidationError(_(
                    f"Erreur lors de la création du profil transporteur: {str(e)}"
                ))

            return user

        except Exception as e:
            logger.error(f"Erreur générale lors de la création du transporteur: {e}", exc_info=True)
            raise ValidationError(_(
                f"Erreur lors de l'inscription: {str(e)}. "
                "Veuillez réessayer ou contacter le support."
            ))
# Les autres formulaires existants restent inchangés
class CustomUserCreationForm(UserCreationForm):
    """Formulaire pour créer un nouvel utilisateur avec des champs supplémentaires"""

    phone = forms.CharField(
        label=_("Numéro de téléphone"),
        required=True,
        help_text=_("Format international : +212612345678 (recommandé) ou 00212612345678"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("+212612345678"),
            'title': _("Entrez votre numéro au format international")
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'phone',
                 'country', 'city', 'preferred_language')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'preferred_language': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_phone(self):
        """Valide et formate le numéro de téléphone"""
        phone = self.cleaned_data.get('phone')

        if phone:
            try:
                # Nettoyer le numéro : supprimer les espaces, tirets, etc.
                phone = phone.strip().replace(' ', '').replace('-', '').replace('.', '')

                # Convertir les formats locaux en format international
                if phone.startswith('0'):
                    # L'utilisateur a entré un format local (ex: 0612345678)
                    country = self.cleaned_data.get('country')

                    if country:
                        # Mapper les codes pays
                        country_codes = {
                            'MA': '212',  # Maroc
                            'FR': '33',   # France
                            'BE': '32',   # Belgique
                            'TN': '216',  # Tunisie
                            'DZ': '213',  # Algérie
                            'SN': '221',  # Sénégal
                            'CI': '225',  # Côte d'Ivoire
                            'CM': '237',  # Cameroun
                            'US': '1',    # États-Unis
                            'GB': '44',   # Royaume-Uni
                            'DE': '49',   # Allemagne
                            'ES': '34',   # Espagne
                            'IT': '39',   # Italie
                            'PT': '351',  # Portugal
                        }

                        code = country_codes.get(country, '')
                        if code:
                            # Enlever le 0 initial et ajouter le code pays
                            phone = f"+{code}{phone[1:]}"

                # Convertir 00 en + si présent (format 00212...)
                elif phone.startswith('00'):
                    phone = '+' + phone[2:]

                # S'assurer que le numéro commence par +
                if not phone.startswith('+'):
                    phone = '+' + phone

                # Validation de la longueur minimale
                if len(phone) < 10:
                    raise forms.ValidationError(
                        _("Numéro de téléphone trop court. Format attendu : +212612345678")
                    )

                # Validation que le numéro ne contient que des chiffres après le +
                if not phone[1:].isdigit():
                    raise forms.ValidationError(
                        _("Le numéro de téléphone ne doit contenir que des chiffres après le +")
                    )

                return phone

            except Exception as e:
                raise forms.ValidationError(
                    _("Saisissez un numéro de téléphone valide. Format: +212612345678 ou 0612345678")
                )

        return phone

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Améliorer les champs existants
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _("Choisissez un nom d'utilisateur")
        })
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _("votre@email.com")
        })
        self.fields['country'].widget.attrs.update({
            'class': 'form-control'
        })
        self.fields['city'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _("Votre ville")
        })
        self.fields['city'].required = False

        # Rendre le pays obligatoire pour aider à la validation du téléphone
        self.fields['country'].required = True

        # Ajouter une aide pour le format du téléphone
        self.fields['phone'].help_text += _(
            "<br><small class='text-muted'>Exemples: +212612345678 (Maroc), +33612345678 (France), +32456123456 (Belgique)</small>"
        )

class CustomUserChangeForm(UserChangeForm):
    """Formulaire pour modifier un utilisateur existant"""

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'phone',
                 'country', 'city', 'address', 'preferred_language',
                 'is_verified', 'kyc_verified', 'is_active')


class LoginForm(forms.Form):
    """Formulaire de connexion"""
    username = forms.CharField(
        label=_("Nom d'utilisateur ou Email"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Entrez votre nom d'utilisateur ou email")
        })
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _("Entrez votre mot de passe")
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        label=_("Se souvenir de moi"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class UserProfileForm(forms.ModelForm):
    """Formulaire pour le profil utilisateur étendu"""
    class Meta:
        model = UserProfile
        fields = [
            'date_of_birth', 'gender', 'company_name',
            'company_registration', 'tax_id', 'country_of_origin',
            'country_of_residence', 'is_expatriate'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }

class PasswordResetRequestForm(forms.Form):
    """Formulaire pour demander une réinitialisation de mot de passe"""
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _("Entrez votre email")
        })
    )

class PasswordResetConfirmForm(forms.Form):
    """Formulaire pour confirmer la réinitialisation du mot de passe"""
    new_password1 = forms.CharField(
        label=_("Nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label=_("Confirmer le nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

class KYCVerificationForm(forms.ModelForm):
    """Formulaire pour la vérification KYC"""
    id_document = forms.FileField(
        label=_("Document d'identité"),
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    proof_of_address = forms.FileField(
        label=_("Justificatif de domicile"),
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    selfie_with_id = forms.FileField(
        label=_("Selfie avec document d'identité"),
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.role == User.Role.CARRIER:
            self.fields['company_registration_doc'] = forms.FileField(
                label=_("Document d'immatriculation"),
                required=True,
                widget=forms.FileInput(attrs={'class': 'form-control'})
            )
# ~/ebi3/carriers/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
import json
from datetime import datetime, timedelta
from phonenumber_field.formfields import PhoneNumberField
import logging

from .models import (
    Carrier, CarrierRoute, CarrierDocument, Mission,
    CollectionDay, FinancialTransaction, CarrierReview,
    CarrierOffer, CarrierAvailability, MerchandiseTypes
)
from users.models import User, UserProfile

logger = logging.getLogger(__name__)


class CarrierRegistrationForm(forms.ModelForm):
    """Formulaire d'inscription pour les transporteurs - Intégration avec User existant"""

    # ========== INFORMATIONS UTILISATEUR ==========
    email = forms.EmailField(
        label=_("Email"),
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('votre@email.com')
        })
    )

    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Mot de passe sécurisé')
        })
    )

    password_confirm = forms.CharField(
        label=_("Confirmer le mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Répétez le mot de passe')
        })
    )

    first_name = forms.CharField(
        label=_("Prénom"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Votre prénom')
        })
    )

    last_name = forms.CharField(
        label=_("Nom"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Votre nom')
        })
    )

    phone = PhoneNumberField(
        label=_("Téléphone"),
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('+33 6 12 34 56 78')
        })
    )

    # Champs User supplémentaires
    country = forms.ChoiceField(
        label=_("Pays"),
        required=False,
        choices=[('', _('Sélectionnez un pays'))],  # Seront remplis dynamiquement
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    city = forms.CharField(
        label=_("Ville"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Votre ville')
        })
    )

    address = forms.CharField(
        label=_("Adresse"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Votre adresse complète')
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

    # ========== PHOTOS ET DOCUMENTS ==========
    profile_photo = forms.ImageField(
        label=_("Photo de profil"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    id_front = forms.ImageField(
        label=_("Recto pièce d'identité"),
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    id_back = forms.ImageField(
        label=_("Verso pièce d'identité"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    # ========== TYPES DE MARCHANDISES ACCEPTÉES ==========
    accepted_merchandise_types = forms.MultipleChoiceField(
        label=_("Types de marchandises acceptées"),
        choices=MerchandiseTypes.STANDARD,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )

    custom_merchandise_types = forms.CharField(
        label=_("Autres types de marchandises"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Séparez par des virgules')
        }),
        help_text=_("Saisissez vos types personnalisés séparés par des virgules")
    )

    # ========== HORAIRES HEBDOMADAIRES ==========
    transport_weekly_schedule = forms.CharField(
        label=_("Horaires hebdomadaires"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _("Exemple: Lundi: 8h-18h, Mardi: 9h-17h, Mercredi: 8h-12h")
        }),
        help_text=_("Indiquez vos horaires de disponibilité par jour")
    )

    # ========== CONFORMITÉ ==========
    rgpd_consent = forms.BooleanField(
        label=_("J'accepte la politique de confidentialité"),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    terms_accepted = forms.BooleanField(
        label=_("J'accepte les conditions générales d'utilisation"),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = Carrier
        fields = [
            'carrier_type', 'transport_company_name', 'transport_company_registration',
            'transport_tax_id', 'transport_company_address', 'vehicle_type',
            'vehicle_make', 'vehicle_model', 'vehicle_year',
            'vehicle_registration', 'max_weight', 'max_volume',
            'max_length', 'max_width', 'max_height',
            'provides_packaging', 'provides_insurance',
            'provides_loading', 'provides_unloading',
            'base_price_per_km', 'min_price', 'currency',
            'coverage_cities'
        ]
        widgets = {
            'carrier_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_carrier_type'
            }),
            'transport_company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Nom de votre entreprise de transport')
            }),
            'transport_company_registration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Numéro d\'immatriculation')
            }),
            'vehicle_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_vehicle_type'
            }),
            'vehicle_make': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ex: Renault, Mercedes, etc.')
            }),
            'vehicle_model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Modèle du véhicule')
            }),
            'max_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0.001'
            }),
            'max_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0.001'
            }),
            'coverage_cities': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Paris, Lyon, Marseille... (séparés par des virgules)')
            }),
            'base_price_per_km': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0'
            }),
            'min_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'provides_packaging': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'provides_insurance': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'provides_loading': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'provides_unloading': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'max_weight': _("Poids maximum (kg)"),
            'max_volume': _("Volume maximum (m³)"),
            'transport_company_name': _("Nom de l'entreprise"),
            'coverage_cities': _("Villes de couverture"),
        }
        help_texts = {
            'base_price_per_km': _("Prix de base par kilomètre (utilisé pour le calcul des tarifs)"),
            'min_price': _("Prix minimum pour une mission"),
            'coverage_cities': _("Listez les villes où vous opérez, séparées par des virgules"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamiquement charger les choix de pays pour User.country
        from django_countries import countries
        country_choices = [('', _('Sélectionnez un pays'))] + list(countries)
        self.fields['country'].choices = country_choices

        # Masquer les champs de l'entreprise si c'est un transporteur particulier
        self.fields['transport_company_name'].required = False
        self.fields['transport_company_registration'].required = False
        self.fields['transport_tax_id'].required = False

    def clean_password_confirm(self):
        """Valider que les mots de passe correspondent"""
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise ValidationError(_("Les mots de passe ne correspondent pas"))

        return password_confirm

    def clean_email(self):
        """Valider l'email unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("Un compte avec cet email existe déjà"))
        return email

    def clean_phone(self):
        """Valider le numéro de téléphone"""
        phone = self.cleaned_data.get('phone')
        if User.objects.filter(phone=phone).exists():
            raise ValidationError(_("Un compte avec ce numéro de téléphone existe déjà"))
        return phone

    def clean(self):
        """Validations croisées"""
        cleaned_data = super().clean()

        # Vérifier la cohérence des dimensions
        max_weight = cleaned_data.get('max_weight')
        max_volume = cleaned_data.get('max_volume')

        if max_weight and max_weight < 0.001:
            self.add_error('max_weight',
                _("Le poids minimum doit être d'au moins 0.001 kg"))

        if max_volume and max_volume < 0.001:
            self.add_error('max_volume',
                _("Le volume minimum doit être d'au moins 0.001 m³"))

        # Vérifier les champs obligatoires pour les professionnels
        carrier_type = cleaned_data.get('carrier_type')

        if carrier_type == Carrier.CarrierType.PROFESSIONAL:
            company_name = cleaned_data.get('transport_company_name', '').strip()
            if not company_name:
                self.add_error('transport_company_name',
                    _("Le nom de l'entreprise est obligatoire pour les transporteurs professionnels"))

        # Validation supplémentaire : type de véhicule vs capacités
        vehicle_type = cleaned_data.get('vehicle_type')
        max_weight = cleaned_data.get('max_weight', 0)
        max_volume = cleaned_data.get('max_volume', 0)

        if vehicle_type and max_weight and max_volume:
            # Vérifier que les capacités sont réalistes pour le type de véhicule
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

        return cleaned_data

    def parse_weekly_schedule(self, schedule_text):
        """Convertir le texte des horaires en format JSON"""
        if not schedule_text:
            return {}

        schedule = {}
        days_mapping = {
            'lundi': 'monday',
            'mardi': 'tuesday',
            'mercredi': 'wednesday',
            'jeudi': 'thursday',
            'vendredi': 'friday',
            'samedi': 'saturday',
            'dimanche': 'sunday'
        }

        try:
            # Exemple de format: "Lundi: 8h-18h, Mardi: 9h-17h"
            entries = schedule_text.split(',')
            for entry in entries:
                entry = entry.strip()
                if ':' in entry:
                    day_part, time_part = entry.split(':', 1)
                    day_fr = day_part.strip().lower()

                    if day_fr in days_mapping:
                        day_en = days_mapping[day_fr]
                        # Extraire les heures (format: "8h-18h")
                        times = time_part.strip().split('-')
                        if len(times) == 2:
                            start_time = times[0].strip().replace('h', ':').replace('H', ':')
                            end_time = times[1].strip().replace('h', ':').replace('H', ':')

                            # Ajouter :00 si pas de minutes
                            if ':' not in start_time:
                                start_time += ':00'
                            if ':' not in end_time:
                                end_time += ':00'

                            schedule[day_en] = {
                                'start': start_time,
                                'end': end_time,
                                'available': True
                            }
        except Exception as e:
            logger.warning(f"Erreur parsing horaires: {e}")
            # Retourner un format vide en cas d'erreur

        return schedule

    def save(self, commit=True):
        """
        Crée d'abord un User, puis un Carrier associé
        Gestion robuste des erreurs
        """
        user = None
        try:
            # ========== CRÉATION DE L'UTILISATEUR ==========
            carrier_type = self.cleaned_data['carrier_type']

            # Déterminer le rôle User correspondant
            if carrier_type == Carrier.CarrierType.PROFESSIONAL:
                user_role = User.Role.CARRIER
            else:
                user_role = User.Role.CARRIER_PERSONAL

            # Données pour créer l'utilisateur
            user_data = {
                'email': self.cleaned_data['email'],
                'username': self.cleaned_data['email'],  # Email comme username
                'first_name': self.cleaned_data['first_name'],
                'last_name': self.cleaned_data['last_name'],
                'phone': self.cleaned_data['phone'],
                'role': user_role,
                'country': self.cleaned_data.get('country'),
                'city': self.cleaned_data.get('city'),
                'address': self.cleaned_data.get('address'),
                'preferred_language': self.cleaned_data.get('preferred_language', 'fr'),
                'is_available': True,  # Disponible par défaut
            }

            # Créer l'utilisateur
            user = User(**user_data)
            user.set_password(self.cleaned_data['password'])

            # Activer le compte (sera vérifié plus tard par admin)
            user.is_active = True
            user.save()

            # Créer le UserProfile associé
            try:
                UserProfile.objects.create(user=user)
            except Exception as e:
                logger.warning(f"UserProfile non créé pour {user.username}: {e}")
                # Continuer sans UserProfile, il pourra être créé plus tard

            # ========== CRÉATION DU TRANSPORTEUR ==========
            # Récupérer l'instance Carrier du formulaire
            carrier = super().save(commit=False)
            carrier.user = user

            # Gérer les photos
            if self.cleaned_data.get('profile_photo'):
                carrier.profile_photo = self.cleaned_data['profile_photo']

            if self.cleaned_data.get('id_front'):
                carrier.id_front = self.cleaned_data['id_front']

            if self.cleaned_data.get('id_back'):
                carrier.id_back = self.cleaned_data['id_back']

            # Gérer les types de marchandises
            accepted_types = self.cleaned_data.get('accepted_merchandise_types', [])
            carrier.accepted_merchandise_types = accepted_types

            custom_types = self.cleaned_data.get('custom_merchandise_types', '')
            if custom_types:
                carrier.custom_merchandise_types = custom_types

            # Gérer les horaires hebdomadaires
            schedule_text = self.cleaned_data.get('transport_weekly_schedule', '')
            if schedule_text:
                carrier.transport_weekly_schedule = self.parse_weekly_schedule(schedule_text)

            # Conformité
            carrier.rgpd_consent = self.cleaned_data['rgpd_consent']
            carrier.terms_accepted = self.cleaned_data['terms_accepted']

            # Par défaut, disponible pour le transport
            carrier.transport_is_available = True

            # Initialiser les statistiques
            carrier.transport_success_rate = 100.00

            # Sauvegarder si commit=True
            if commit:
                carrier.save()

            logger.info(f"Transporteur créé avec succès: {user.username}")

            return carrier

        except Exception as e:
            logger.error(f"Erreur lors de l'inscription transporteur: {e}")

            # Nettoyage en cas d'erreur
            if user and user.pk:
                user.delete()

            raise ValidationError(_(
                "Erreur lors de l'inscription. Veuillez réessayer. "
                "Si le problème persiste, contactez le support."
            ))


class CarrierProfileForm(forms.ModelForm):
    """Formulaire de mise à jour du profil transporteur - Intégration avec User"""

    # ========== INFORMATIONS UTILISATEUR ==========
    first_name = forms.CharField(
        label=_("Prénom"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )

    last_name = forms.CharField(
        label=_("Nom"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )

    phone = PhoneNumberField(
        label=_("Téléphone"),
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )

    email = forms.EmailField(
        label=_("Email"),
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'  # Email non modifiable
        })
    )

    country = forms.ChoiceField(
        label=_("Pays"),
        required=False,
        choices=[('', _('Sélectionnez un pays'))],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    city = forms.CharField(
        label=_("Ville"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )

    address = forms.CharField(
        label=_("Adresse"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2
        })
    )

    # ========== PHOTOS ==========
    profile_photo = forms.ImageField(
        label=_("Photo de profil"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    # ========== ZONES DE COUVERTURE ==========
    coverage_cities = forms.CharField(
        label=_("Villes de couverture"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Paris, Lyon, Marseille...')
        })
    )

    # ========== HORAIRES DE DISPONIBILITÉ ==========
    transport_weekly_schedule = forms.CharField(
        label=_("Horaires hebdomadaires"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _("Exemple: Lundi: 8h-18h, Mardi: 9h-17h")
        }),
        help_text=_("Indiquez vos horaires de disponibilité par jour")
    )

    # ========== TYPES DE MARCHANDISES ==========
    accepted_merchandise_types = forms.MultipleChoiceField(
        label=_("Types de marchandises acceptées"),
        choices=MerchandiseTypes.STANDARD,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )

    custom_merchandise_types = forms.CharField(
        label=_("Autres types de marchandises"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Séparez par des virgules')
        })
    )

    # ========== PHOTOS DU VÉHICULE ==========
    vehicle_photo_front = forms.ImageField(
        label=_("Photo avant du véhicule"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    vehicle_photo_back = forms.ImageField(
        label=_("Photo arrière du véhicule"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    vehicle_photo_side = forms.ImageField(
        label=_("Photo côté du véhicule"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        })
    )

    class Meta:
        model = Carrier
        fields = [
            'carrier_type', 'transport_company_name', 'transport_company_registration',
            'transport_tax_id', 'transport_company_address', 'vehicle_type',
            'vehicle_make', 'vehicle_model', 'vehicle_year',
            'vehicle_registration', 'max_weight', 'max_volume',
            'max_length', 'max_width', 'max_height',
            'provides_packaging', 'provides_insurance',
            'provides_loading', 'provides_unloading',
            'base_price_per_km', 'min_price', 'currency',
            'transport_available_from', 'transport_available_until',
            'transport_is_available'
        ]
        widgets = {
            'transport_available_from': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'transport_available_until': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'transport_is_available': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialiser les choix des pays pour User.country
        from django_countries import countries
        country_choices = [('', _('Sélectionnez un pays'))] + list(countries)
        self.fields['country'].choices = country_choices

        # Pré-remplir les données utilisateur
        if self.instance and self.instance.user:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['phone'].initial = user.phone
            self.fields['email'].initial = user.email
            self.fields['country'].initial = user.country
            self.fields['city'].initial = user.city
            self.fields['address'].initial = user.address

        # Ajuster les champs selon le type de transporteur
        if self.instance and self.instance.carrier_type == Carrier.CarrierType.PROFESSIONAL:
            self.fields['transport_company_name'].required = True
        else:
            self.fields['transport_company_name'].required = False

        # Pré-remplir les horaires hebdomadaires
        if self.instance and self.instance.transport_weekly_schedule:
            schedule = self.instance.transport_weekly_schedule
            if isinstance(schedule, dict) and schedule:
                schedule_text = self.format_schedule_for_display(schedule)
                self.fields['transport_weekly_schedule'].initial = schedule_text

    def format_schedule_for_display(self, schedule):
        """Convertir le format JSON des horaires en texte lisible"""
        if not schedule:
            return ""

        days_mapping = {
            'monday': 'Lundi',
            'tuesday': 'Mardi',
            'wednesday': 'Mercredi',
            'thursday': 'Jeudi',
            'friday': 'Vendredi',
            'saturday': 'Samedi',
            'sunday': 'Dimanche'
        }

        parts = []
        for day_en, details in schedule.items():
            if details.get('available', False) and 'start' in details and 'end' in details:
                day_fr = days_mapping.get(day_en, day_en.capitalize())
                start = details['start'].replace(':', 'h')
                end = details['end'].replace(':', 'h')
                parts.append(f"{day_fr}: {start}-{end}")

        return ', '.join(parts)

    def parse_weekly_schedule(self, schedule_text):
        """Convertir le texte des horaires en format JSON"""
        if not schedule_text:
            return {}

        schedule = {}
        days_mapping = {
            'lundi': 'monday',
            'mardi': 'tuesday',
            'mercredi': 'wednesday',
            'jeudi': 'thursday',
            'vendredi': 'friday',
            'samedi': 'saturday',
            'dimanche': 'sunday'
        }

        try:
            entries = schedule_text.split(',')
            for entry in entries:
                entry = entry.strip()
                if ':' in entry:
                    day_part, time_part = entry.split(':', 1)
                    day_fr = day_part.strip().lower()

                    if day_fr in days_mapping:
                        day_en = days_mapping[day_fr]
                        times = time_part.strip().split('-')
                        if len(times) == 2:
                            start_time = times[0].strip().replace('h', ':').replace('H', ':')
                            end_time = times[1].strip().replace('h', ':').replace('H', ':')

                            if ':' not in start_time:
                                start_time += ':00'
                            if ':' not in end_time:
                                end_time += ':00'

                            schedule[day_en] = {
                                'start': start_time,
                                'end': end_time,
                                'available': True
                            }
        except Exception as e:
            logger.warning(f"Erreur parsing horaires dans CarrierProfileForm: {e}")

        return schedule

    def clean(self):
        """Validation croisée"""
        cleaned_data = super().clean()

        # Vérifier la cohérence des dates de disponibilité
        available_from = cleaned_data.get('transport_available_from')
        available_until = cleaned_data.get('transport_available_until')

        if available_from and available_until:
            if available_from > available_until:
                self.add_error('transport_available_until',
                    _("La date de fin doit être après la date de début"))

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

        return cleaned_data

    def save(self, commit=True):
        """
        Met à jour d'abord le User, puis le Carrier
        """
        try:
            # Mettre à jour l'utilisateur
            if self.instance and self.instance.user:
                user = self.instance.user
                user.first_name = self.cleaned_data['first_name']
                user.last_name = self.cleaned_data['last_name']
                user.phone = self.cleaned_data['phone']
                user.country = self.cleaned_data.get('country')
                user.city = self.cleaned_data.get('city')
                user.address = self.cleaned_data.get('address')

                # Synchroniser la disponibilité
                transport_is_available = self.cleaned_data.get('transport_is_available', True)
                user.is_available = transport_is_available

                user.save()

            # Mettre à jour les types de marchandises
            accepted_types = self.cleaned_data.get('accepted_merchandise_types', [])
            self.instance.accepted_merchandise_types = accepted_types

            # Mettre à jour les horaires hebdomadaires
            schedule_text = self.cleaned_data.get('transport_weekly_schedule', '')
            if schedule_text:
                self.instance.transport_weekly_schedule = self.parse_weekly_schedule(schedule_text)

            # Sauvegarder le transporteur
            carrier = super().save(commit=commit)

            logger.info(f"Profil transporteur mis à jour: {self.instance.user.username}")

            return carrier

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du profil transporteur: {e}")
            raise


class CarrierRouteForm(forms.ModelForm):
    """Formulaire pour créer/modifier une route"""

    class Meta:
        model = CarrierRoute
        fields = [
            'start_country', 'start_city', 'start_location',
            'end_country', 'end_city', 'end_location',
            'frequency', 'departure_date', 'arrival_date',
            'price_per_kg', 'price_per_m3', 'fixed_price',
            'toll_costs', 'tax_costs', 'fuel_costs',
            'estimated_transit_time'
        ]
        widgets = {
            'start_country': forms.Select(attrs={'class': 'form-control'}),
            'end_country': forms.Select(attrs={'class': 'form-control'}),
            'departure_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'arrival_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'estimated_transit_time': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM:SS'
            }),
            'start_location': forms.HiddenInput(),
            'end_location': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()

        departure_date = cleaned_data.get('departure_date')
        arrival_date = cleaned_data.get('arrival_date')

        if departure_date and arrival_date:
            if departure_date > arrival_date:
                self.add_error('arrival_date',
                    _("La date d'arrivée doit être après la date de départ"))

        return cleaned_data


class MissionForm(forms.ModelForm):
    """Formulaire pour gérer une mission"""

    sender_phone = PhoneNumberField(
        label=_("Téléphone expéditeur"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('+33 6 12 34 56 78')
        })
    )

    recipient_phone = PhoneNumberField(
        label=_("Téléphone destinataire"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('+33 6 12 34 56 78')
        })
    )

    # Types de marchandises avec menu déroulant
    merchandise_type = forms.ChoiceField(
        label=_("Type de marchandise"),
        choices=[('', _('Sélectionnez un type'))] + MerchandiseTypes.STANDARD,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'merchandise-type-select'
        })
    )

    custom_merchandise_type = forms.CharField(
        label=_("Autre type de marchandise"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'custom-merchandise-type',
            'placeholder': _('Précisez le type'),
            'style': 'display: none;'
        })
    )

    # Organisation du stock
    collection_order = forms.IntegerField(
        label=_("Ordre de collecte"),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('0 = non défini')
        })
    )

    position_in_vehicle = forms.CharField(
        label=_("Position dans le véhicule"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ex: Arrière gauche, dessus...')
        })
    )

    class Meta:
        model = Mission
        fields = [
            'priority', 'sender_address', 'recipient_name',
            'recipient_address', 'description', 'weight',
            'length', 'width', 'height', 'is_fragile',
            'requires_special_handling', 'preferred_pickup_date',
            'preferred_delivery_date', 'agreed_price', 'currency'
        ]
        widgets = {
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'sender_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'recipient_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Description détaillée de la marchandise')
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001'
            }),
            'preferred_pickup_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'preferred_delivery_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'agreed_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'is_fragile': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'requires_special_handling': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.carrier = kwargs.pop('carrier', None)
        self.sender = kwargs.pop('sender', None)
        super().__init__(*args, **kwargs)

        if self.carrier:
            self.fields['carrier'].initial = self.carrier

        if self.sender:
            self.fields['sender'].initial = self.sender
            self.fields['sender_phone'].initial = self.sender.phone

    def clean(self):
        cleaned_data = super().clean()

        # Vérifier le type de marchandise
        merchandise_type = cleaned_data.get('merchandise_type')
        custom_type = cleaned_data.get('custom_merchandise_type')

        if merchandise_type == 'OTHER' and not custom_type:
            self.add_error('custom_merchandise_type',
                _("Veuillez spécifier le type de marchandise"))

        # Vérifier les dimensions
        weight = cleaned_data.get('weight')
        length = cleaned_data.get('length')
        width = cleaned_data.get('width')
        height = cleaned_data.get('height')

        if all([weight, length, width, height]) and self.carrier:
            if not self.carrier.can_carry_item(weight, length, width, height):
                self.add_error('weight',
                    _("Cet objet dépasse les capacités du transporteur"))

        return cleaned_data

    def save(self, commit=True):
        mission = super().save(commit=False)

        if self.carrier:
            mission.carrier = self.carrier

        if self.sender:
            mission.sender = self.sender

        # Gérer le type de marchandise
        if self.cleaned_data.get('merchandise_type') == 'OTHER':
            mission.merchandise_type = 'CUSTOM'
            mission.custom_merchandise_type = self.cleaned_data.get('custom_merchandise_type')
        else:
            mission.merchandise_type = self.cleaned_data.get('merchandise_type', '')

        if commit:
            mission.save()

        return mission


class CollectionDayForm(forms.ModelForm):
    """Formulaire pour organiser un jour de collecte"""

    class Meta:
        model = CollectionDay
        fields = ['date', 'start_time', 'end_time', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Notes pour cette journée de collecte...')
            }),
        }

    def clean(self):
        cleaned_data = super().clean()

        date = cleaned_data.get('date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if date and start_time and end_time:
            if start_time >= end_time:
                self.add_error('end_time',
                    _("L'heure de fin doit être après l'heure de début"))

        return cleaned_data


class DocumentUploadForm(forms.ModelForm):
    """Formulaire pour uploader des documents"""

    class Meta:
        model = CarrierDocument
        fields = ['document_type', 'file', 'description', 'expiry_date']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Description du document')
            }),
            'expiry_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }


class FinancialTransactionForm(forms.ModelForm):
    """Formulaire pour enregistrer une transaction financière"""

    class Meta:
        model = FinancialTransaction
        fields = [
            'transaction_type', 'amount', 'currency',
            'mission', 'payment_method', 'expense_category',
            'expense_description', 'expense_receipt',
            'transaction_date', 'notes'
        ]
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'mission': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'expense_category': forms.Select(attrs={'class': 'form-control'}),
            'expense_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'expense_receipt': forms.FileInput(attrs={
                'class': 'form-control-file'
            }),
            'transaction_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }

    def __init__(self, *args, **kwargs):
        self.carrier = kwargs.pop('carrier', None)
        super().__init__(*args, **kwargs)

        if self.carrier:
            # Filtrer les missions du transporteur
            self.fields['mission'].queryset = Mission.objects.filter(
                carrier=self.carrier
            )


class CarrierReviewForm(forms.ModelForm):
    """Formulaire pour laisser un avis sur un transporteur"""

    class Meta:
        model = CarrierReview
        fields = [
            'rating', 'title', 'comment',
            'communication', 'punctuality',
            'handling', 'professionalism'
        ]
        widgets = {
            'rating': forms.Select(choices=[(i, str(i)) for i in range(1, 6)],
                attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Titre de votre avis')
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Décrivez votre expérience...')
            }),
            'communication': forms.Select(choices=[(i, str(i)) for i in range(1, 6)],
                attrs={'class': 'form-control'}),
            'punctuality': forms.Select(choices=[(i, str(i)) for i in range(1, 6)],
                attrs={'class': 'form-control'}),
            'handling': forms.Select(choices=[(i, str(i)) for i in range(1, 6)],
                attrs={'class': 'form-control'}),
            'professionalism': forms.Select(choices=[(i, str(i)) for i in range(1, 6)],
                attrs={'class': 'form-control'}),
        }


class CarrierOfferForm(forms.ModelForm):
    """Formulaire pour créer une offre de service"""

    class Meta:
        model = CarrierOffer
        fields = [
            'title', 'description', 'offer_type',
            'start_country', 'start_city',
            'end_country', 'end_city',
            'available_from', 'available_until',
            'price', 'currency',
            'available_weight', 'available_volume'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Titre de votre offre')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Décrivez votre offre de service...')
            }),
            'offer_type': forms.Select(attrs={'class': 'form-control'}),
            'start_country': forms.Select(attrs={'class': 'form-control'}),
            'end_country': forms.Select(attrs={'class': 'form-control'}),
            'available_from': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'available_until': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'available_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001'
            }),
            'available_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()

        available_from = cleaned_data.get('available_from')
        available_until = cleaned_data.get('available_until')

        if available_from and available_until:
            if available_from >= available_until:
                self.add_error('available_until',
                    _("La date de fin doit être après la date de début"))

        return cleaned_data


class MissionAcceptanceForm(forms.Form):
    """Formulaire pour accepter/refuser une mission"""

    accept = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput()
    )

    rejection_reason = forms.CharField(
        label=_("Raison du refus"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Optionnel : précisez pourquoi vous refusez cette mission')
        })
    )


class MissionStatusUpdateForm(forms.ModelForm):
    """Formulaire pour mettre à jour le statut d'une mission"""

    class Meta:
        model = Mission
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'})
        }


class DeliveryProofForm(forms.ModelForm):
    """Formulaire pour uploader la preuve de livraison"""

    class Meta:
        model = Mission
        fields = ['delivery_proof_photo', 'recipient_signature', 'delivery_notes']
        widgets = {
            'delivery_proof_photo': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*'
            }),
            'recipient_signature': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*'
            }),
            'delivery_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Notes sur la livraison...')
            }),
        }


class MissionFilterForm(forms.Form):
    """Formulaire pour filtrer les missions"""

    STATUS_CHOICES = [
        ('', _('Tous les statuts')),
    ] + Mission.MissionStatus.choices

    PRIORITY_CHOICES = [
        ('', _('Toutes les priorités')),
    ] + Mission.PriorityLevel.choices

    status = forms.ChoiceField(
        label=_("Statut"),
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    priority = forms.ChoiceField(
        label=_("Priorité"),
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_from = forms.DateField(
        label=_("Du"),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    date_to = forms.DateField(
        label=_("Au"),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


class RouteOptimizationForm(forms.Form):
    """Formulaire pour optimiser un itinéraire de collecte"""

    optimization_type = forms.ChoiceField(
        label=_("Type d'optimisation"),
        choices=[
            ('DISTANCE', _('Distance minimale')),
            ('TIME', _('Temps minimal')),
            ('PRIORITY', _('Par priorité')),
            ('CAPACITY', _('Optimisation capacité')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    consider_traffic = forms.BooleanField(
        label=_("Prendre en compte le trafic"),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    max_distance = forms.DecimalField(
        label=_("Distance maximale (km)"),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        })
    )


class CarrierSearchForm(forms.Form):
    """Formulaire de recherche de transporteurs"""

    start_country = forms.ChoiceField(
        label=_("Pays de départ"),
        required=False,
        choices=[('', _('Tous les pays'))],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    start_city = forms.CharField(
        label=_("Ville de départ"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom de la ville')
        })
    )

    end_country = forms.ChoiceField(
        label=_("Pays d'arrivée"),
        required=False,
        choices=[('', _('Tous les pays'))],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    end_city = forms.CharField(
        label=_("Ville d'arrivée"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom de la ville')
        })
    )

    departure_date = forms.DateField(
        label=_("Date de départ"),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    max_weight = forms.DecimalField(
        label=_("Poids maximum (kg)"),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001'
        })
    )

    max_volume = forms.DecimalField(
        label=_("Volume maximum (m³)"),
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001'
        })
    )

    vehicle_types = forms.MultipleChoiceField(
        label=_("Types de véhicule"),
        required=False,
        choices=Carrier.VehicleType.choices,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )

    min_rating = forms.ChoiceField(
        label=_("Note minimum"),
        required=False,
        choices=[
            ('', _('Toutes les notes')),
            ('4.5', '4.5 ★ et plus'),
            ('4.0', '4.0 ★ et plus'),
            ('3.5', '3.5 ★ et plus'),
            ('3.0', '3.0 ★ et plus'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialiser les choix des pays
        from django_countries import countries
        country_choices = [('', _('Tous les pays'))] + list(countries)

        self.fields['start_country'].choices = country_choices
        self.fields['end_country'].choices = country_choices
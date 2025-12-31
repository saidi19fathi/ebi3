# ~/ebi3/carriers/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django_countries import countries  # AJOUT: Pour avoir la liste des pays
from django_countries.widgets import CountrySelectWidget  # AJOUT: Widget pour les pays

from .models import Carrier, CarrierRoute, CarrierDocument, CarrierReview
from users.models import User

class CarrierApplicationForm(forms.ModelForm):
    """Formulaire de candidature pour devenir transporteur"""

    class Meta:
        model = Carrier
        fields = [
            'carrier_type', 'company_name', 'company_registration', 'tax_id',
            'company_address', 'vehicle_type', 'vehicle_make', 'vehicle_model',
            'vehicle_year', 'vehicle_registration', 'max_weight', 'max_volume',
            'max_length', 'max_width', 'max_height', 'provides_packaging',
            'provides_insurance', 'provides_loading', 'provides_unloading',
            'base_price_per_km', 'min_price', 'currency'
        ]

        widgets = {
            'carrier_type': forms.Select(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Nom de votre entreprise")
            }),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_make': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ex: Renault, Mercedes, etc.")
            }),
            'vehicle_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1990',
                'max': '2100'
            }),
            'max_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001'
            }),
            'max_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001'
            }),
            'base_price_per_km': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001'
            }),
            'min_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
        }

        labels = {
            'carrier_type': _("Type de transporteur"),
            'max_weight': _("Poids maximum transportable (kg)"),
            'max_volume': _("Volume maximum transportable (m³)"),
            'provides_packaging': _("Je fournis l'emballage"),
            'provides_insurance': _("Je fournis l'assurance"),
            'provides_loading': _("Je fournis le chargement"),
            'provides_unloading': _("Je fournis le déchargement"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Masquer les champs non pertinents pour les particuliers
        if self.instance.carrier_type == Carrier.CarrierType.PERSONAL or \
           (self.initial.get('carrier_type') == Carrier.CarrierType.PERSONAL):
            self.fields['company_name'].required = False
            self.fields['company_registration'].required = False
            self.fields['tax_id'].required = False
            self.fields['company_address'].required = False

    def clean(self):
        cleaned_data = super().clean()
        carrier_type = cleaned_data.get('carrier_type')
        company_name = cleaned_data.get('company_name')

        # Validation pour les transporteurs professionnels
        if carrier_type == Carrier.CarrierType.PROFESSIONAL:
            if not company_name:
                self.add_error('company_name',
                             _("Le nom de l'entreprise est obligatoire pour les transporteurs professionnels."))

        # Validation des capacités
        max_weight = cleaned_data.get('max_weight')
        max_volume = cleaned_data.get('max_volume')

        if max_weight and max_weight <= 0:
            self.add_error('max_weight', _("Le poids maximum doit être supérieur à 0."))

        if max_volume and max_volume <= 0:
            self.add_error('max_volume', _("Le volume maximum doit être supérieur à 0."))

        return cleaned_data

    def save(self, commit=True):
        carrier = super().save(commit=False)

        if self.user:
            carrier.user = self.user

        if commit:
            carrier.save()

        return carrier


class CarrierUpdateForm(forms.ModelForm):
    """Formulaire de mise à jour pour les transporteurs"""

    class Meta:
        model = Carrier
        fields = [
            'company_name', 'company_address', 'vehicle_make', 'vehicle_model',
            'vehicle_year', 'vehicle_registration', 'max_weight', 'max_volume',
            'max_length', 'max_width', 'max_height', 'provides_packaging',
            'provides_insurance', 'provides_loading', 'provides_unloading',
            'base_price_per_km', 'min_price', 'currency', 'is_available',
            'available_from', 'available_until'
        ]

        widgets = {
            'available_from': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'available_until': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }


class CarrierRouteForm(forms.ModelForm):
    """Formulaire pour créer/modifier une route"""

    # AJOUT: Définir les champs de pays manuellement pour le formulaire
    start_country = forms.ChoiceField(
        choices=[('', _("Sélectionnez un pays"))] + list(countries),
        label=_("Pays de départ"),
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )

    end_country = forms.ChoiceField(
        choices=[('', _("Sélectionnez un pays"))] + list(countries),
        label=_("Pays d'arrivée"),
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CarrierRoute
        fields = [
            'start_country', 'start_city', 'end_country', 'end_city',
            'frequency', 'departure_date', 'arrival_date',
            'available_weight', 'available_volume', 'fixed_price'
        ]

        widgets = {
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'departure_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'arrival_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'start_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ville de départ")
            }),
            'end_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ville d'arrivée")
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pré-remplir les champs si l'instance existe
        if self.instance.pk:
            self.fields['start_country'].initial = self.instance.start_country
            self.fields['end_country'].initial = self.instance.end_country

    def clean(self):
        cleaned_data = super().clean()
        departure_date = cleaned_data.get('departure_date')
        arrival_date = cleaned_data.get('arrival_date')

        if departure_date and arrival_date:
            if arrival_date < departure_date:
                self.add_error('arrival_date',
                             _("La date d'arrivée doit être postérieure à la date de départ."))

            if departure_date < timezone.now().date():
                self.add_error('departure_date',
                             _("La date de départ ne peut pas être dans le passé."))

        return cleaned_data

    def save(self, commit=True):
        # S'assurer que les pays sont sauvegardés correctement
        instance = super().save(commit=False)
        instance.start_country = self.cleaned_data.get('start_country')
        instance.end_country = self.cleaned_data.get('end_country')

        if commit:
            instance.save()

        return instance


class CarrierDocumentForm(forms.ModelForm):
    """Formulaire pour télécharger un document"""

    class Meta:
        model = CarrierDocument
        fields = ['document_type', 'file', 'description', 'expiry_date']

        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Description du document")
            }),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }


class CarrierReviewForm(forms.ModelForm):
    """Formulaire pour laisser un avis sur un transporteur"""

    class Meta:
        model = CarrierReview
        fields = [
            'rating', 'title', 'comment',
            'communication', 'punctuality', 'handling', 'professionalism'
        ]

        widgets = {
            'rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Titre de votre avis")
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _("Partagez votre expérience...")
            }),
            'communication': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5'
            }),
            'punctuality': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5'
            }),
            'handling': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5'
            }),
            'professionalism': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5'
            }),
        }

        labels = {
            'communication': _("Communication (1-5)"),
            'punctuality': _("Ponctualité (1-5)"),
            'handling': _("Manutention (1-5)"),
            'professionalism': _("Professionalisme (1-5)"),
        }


class CarrierSearchForm(forms.Form):
    """Formulaire de recherche de transporteurs"""

    carrier_type = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous"))] + list(Carrier.CarrierType.choices),
        label=_("Type de transporteur"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    vehicle_type = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous"))] + list(Carrier.VehicleType.choices),
        label=_("Type de véhicule"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # CORRECTION: Utiliser forms.ChoiceField avec la liste des pays
    start_country = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous les pays"))] + list(countries),
        label=_("Pays de départ"),
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )

    end_country = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous les pays"))] + list(countries),
        label=_("Pays de destination"),
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )

    start_city = forms.CharField(
        required=False,
        label=_("Ville de départ"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: Paris, Casablanca...")
        })
    )

    end_city = forms.CharField(
        required=False,
        label=_("Ville d'arrivée"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: Lyon, Rabat...")
        })
    )

    departure_date = forms.DateField(
        required=False,
        label=_("Date de départ"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    max_weight = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=3,
        label=_("Poids maximum (kg)"),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _("Poids de votre objet")
        })
    )

    min_rating = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=5,
        decimal_places=2,
        label=_("Note minimum"),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: 4.0")
        })
    )

    provides_insurance = forms.BooleanField(
        required=False,
        label=_("Fournit l'assurance"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    provides_packaging = forms.BooleanField(
        required=False,
        label=_("Fournit l'emballage"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('rating', _("Meilleure note")),
            ('price', _("Prix le plus bas")),
            ('experience', _("Plus d'expérience")),
            ('newest', _("Plus récent")),
        ],
        initial='rating',
        label=_("Trier par"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# Formsets
CarrierDocumentFormSet = inlineformset_factory(
    Carrier,
    CarrierDocument,
    form=CarrierDocumentForm,
    extra=3,
    max_num=10,
    can_delete=True,
)

CarrierRouteFormSet = inlineformset_factory(
    Carrier,
    CarrierRoute,
    form=CarrierRouteForm,
    extra=1,
    max_num=20,
    can_delete=True,
)
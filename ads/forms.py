# ~/ebi3/ads/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django_countries.fields import CountryField  # AJOUTEZ CETTE LIGNE

from .models import Ad, AdImage, Category, AdReport
from users.models import User

class AdBaseForm(forms.ModelForm):
    """Formulaire de base pour les annonces"""

    class Meta:
        model = Ad
        fields = [
            'title', 'category', 'description', 'condition',
            'price', 'currency', 'is_negotiable',
            'weight', 'length', 'width', 'height',
            'country_from', 'city_from', 'address_from',
            'country_to', 'city_to', 'address_to',
            'logistics_option', 'requires_insurance',
            'insurance_value', 'fragile_item', 'requires_packaging',
            'available_from', 'available_until',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Titre de votre annonce")
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _("Décrivez votre objet en détail...")
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'placeholder': _("kg")
            }),
            'length': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': _("cm")
            }),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': _("cm")
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': _("cm")
            }),
            'country_from': forms.Select(attrs={'class': 'form-control'}),
            'city_from': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ville de départ")
            }),
            'address_from': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _("Adresse complète (optionnel)")
            }),
            'country_to': forms.Select(attrs={'class': 'form-control'}),
            'city_to': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ville de destination")
            }),
            'address_to': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _("Adresse complète (optionnel)")
            }),
            'logistics_option': forms.Select(attrs={'class': 'form-control'}),
            'insurance_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'available_from': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'available_until': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }
        labels = {
            'is_negotiable': _("Prix négociable"),
            'requires_insurance': _("Assurance requise"),
            'fragile_item': _("Objet fragile"),
            'requires_packaging': _("Emballage requis"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les catégories actives
        self.fields['category'].queryset = Category.objects.filter(is_active=True)

        # Définir les dates par défaut
        if not self.instance.pk:
            self.fields['available_from'].initial = timezone.now().date()
            self.fields['available_until'].initial = (timezone.now() + timezone.timedelta(days=30)).date()

    def clean_available_until(self):
        available_from = self.cleaned_data.get('available_from')
        available_until = self.cleaned_data.get('available_until')

        if available_from and available_until:
            if available_until < available_from:
                raise ValidationError(
                    _("La date de fin doit être postérieure à la date de début.")
                )
            if available_until < timezone.now().date():
                raise ValidationError(
                    _("La date de fin ne peut pas être dans le passé.")
                )

        return available_until

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price <= 0:
            raise ValidationError(_("Le prix doit être supérieur à 0."))
        return price


class AdCreateForm(AdBaseForm):
    """Formulaire pour créer une annonce"""

    def save(self, commit=True):
        ad = super().save(commit=False)
        if self.user:
            ad.seller = self.user

        if commit:
            ad.save()
        return ad


class AdUpdateForm(AdBaseForm):
    """Formulaire pour mettre à jour une annonce"""
    pass


class AdImageForm(forms.ModelForm):
    """Formulaire pour les images d'annonces"""

    class Meta:
        model = AdImage
        fields = ['image', 'caption', 'is_primary', 'is_paid', 'display_order']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Description de l'image")
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }


# Formset pour les images
AdImageFormSet = inlineformset_factory(
    Ad,
    AdImage,
    form=AdImageForm,
    extra=5,  # 5 formulaires d'image vides par défaut
    max_num=20,  # Maximum d'images
    can_delete=True,
    validate_max=True,
)


class AdSearchForm(forms.Form):
    """Formulaire de recherche d'annonces"""

    q = forms.CharField(
        required=False,
        label=_("Rechercher"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Que cherchez-vous ?")
        })
    )

    category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.filter(is_active=True),
        label=_("Catégorie"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    min_price = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        label=_("Prix minimum"),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _("Min")
        })
    )

    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        label=_("Prix maximum"),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _("Max")
        })
    )

    condition = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous"))] + list(Ad.Condition.choices),
        label=_("État"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    logistics_option = forms.ChoiceField(
        required=False,
        choices=[('', _("Toutes"))] + list(Ad.LogisticsOption.choices),
        label=_("Option logistique"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # CORRECTION : Utiliser CountryField directement pour le formfield
    country_from = CountryField().formfield(
        required=False,
        label=_("Pays de départ"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    country_to = CountryField().formfield(
        required=False,
        label=_("Pays de destination"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')

        if min_price and max_price and min_price > max_price:
            raise ValidationError(
                _("Le prix minimum ne peut pas être supérieur au prix maximum.")
            )

        return cleaned_data


class AdReportForm(forms.ModelForm):
    """Formulaire pour signaler une annonce"""

    class Meta:
        model = AdReport
        fields = ['reason', 'description', 'evidence']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _("Décrivez le problème en détail...")
            }),
            'evidence': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf,.doc,.docx'
            }),
        }
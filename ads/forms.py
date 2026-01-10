from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django_countries.fields import CountryField

from .models import Ad, AdImage, Category, AdReport
from users.models import User

class AdBaseForm(forms.ModelForm):
    """Formulaire de base pour les annonces"""

    # Nouveaux champs pour la sélection hiérarchique
    main_category = forms.ModelChoiceField(
        required=True,
        queryset=Category.objects.filter(
            is_active=True
        ).exclude(
            name__in=[
                # Liste des catégories qui sont clairement des sous-catégories
                'Voitures', 'Motos & Scooters', 'Utilitaires & Poids lourds',
                'Ventes immobilières', 'Locations', 'Immobilier neuf',
                'Offres emploi', 'Services à la personne',
                'Vêtements femmes', 'Vêtements hommes', 'Chaussures',
                'Informatique', 'Téléphonie', 'Image & Son',
                'Ameublement', 'Électroménager', 'Décoration',
                'Sports & Plein air', 'Jeux & Jouets', 'Livres & Magazines',
                'BTP & Chantier', 'Agriculture & Espaces verts',
                'Services professionnels', 'Événements & Animation',
                'Accessoires animaux', 'Cuisine & Arts de la table',
                'Jardin & Extérieur', 'Caravanes & Mobil-homes',
                'Nautisme', 'Pièces & Accessoires auto',
                'Bien-être & Santé', 'Collection', 'Luxe & Créateurs',
                'Commerce & Magasin', 'Travaux & Rénovation',
                'Transport & Manutention', 'Transport & Déménagement',
                'Informatique & Web', 'Industrie & Production',
                'Matériel Professionnel', 'Photo & Vidéo',
                'Instruments de musique', 'Vêtements enfants'
            ]
        ).order_by('name'),
        label=_("Catégorie principale *"),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_main_category'
        }),
        help_text=_("Sélectionnez une catégorie principale")
    )

    sub_category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.none(),
        label=_("Sous-catégorie"),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_sub_category',
            'disabled': True
        }),
        help_text=_("Sélectionnez une sous-catégorie (optionnel)")
    )

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
            'category': forms.HiddenInput(attrs={'id': 'id_category'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _("Décrivez votre objet en détail...")
            }),
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

        # Rendre le champ category optionnel pour le formulaire HTML
        # La validation se fera dans la méthode clean
        self.fields['category'].required = False

        # Réorganiser l'ordre des champs pour mettre la catégorie en premier
        field_order = ['title', 'main_category', 'sub_category'] + [f for f in self.fields if f not in ['title', 'main_category', 'sub_category']]
        self.fields = {f: self.fields[f] for f in field_order}

        # Si c'est une modification, pré-remplir les champs
        if self.instance.pk and self.instance.category:
            category = self.instance.category

            # Trouver la catégorie principale
            main_cat = None
            if category.parent:
                # Si la catégorie a un parent
                if category.parent.parent:
                    # Si le parent a aussi un parent, prendre le grand-parent
                    main_cat = category.parent.parent
                else:
                    # Sinon, prendre le parent comme catégorie principale
                    main_cat = category.parent
            else:
                # Si pas de parent, c'est déjà une catégorie principale
                main_cat = category

            if main_cat:
                self.fields['main_category'].initial = main_cat

                # Charger les sous-catégories de la catégorie principale
                subcategories = Category.objects.filter(
                    parent=main_cat,
                    is_active=True
                ).order_by('display_order', 'name')

                self.fields['sub_category'].queryset = subcategories

                # Pré-sélectionner la sous-catégorie si elle existe
                if category.parent == main_cat:
                    self.fields['sub_category'].initial = category
                elif category == main_cat:
                    # Si c'est déjà la catégorie principale, pas de sous-catégorie
                    pass
                elif category in subcategories:
                    # Si c'est une sous-catégorie directe
                    self.fields['sub_category'].initial = category

                # Activer le champ sub_category s'il y a des sous-catégories
                if subcategories.exists():
                    self.fields['sub_category'].disabled = False

        # Définir les dates par défaut
        if not self.instance.pk:
            self.fields['available_from'].initial = timezone.now().date()
            self.fields['available_until'].initial = (timezone.now() + timezone.timedelta(days=30)).date()

    def clean(self):
        cleaned_data = super().clean()

        # Récupérer la catégorie depuis le champ caché
        category_id = cleaned_data.get('category')
        main_category = cleaned_data.get('main_category')
        sub_category = cleaned_data.get('sub_category')

        debug_info = {
            'category_id': category_id,
            'main_category': main_category.id if main_category else None,
            'sub_category': sub_category.id if sub_category else None,
        }
        print("DEBUG - Données de catégorie:", debug_info)

        # Déterminer la catégorie finale
        final_category = None

        # Si une sous-catégorie est sélectionnée, l'utiliser
        if sub_category:
            final_category = sub_category
            print("DEBUG - Utilisation de la sous-catégorie:", sub_category.id, sub_category.name)
        # Sinon, utiliser la catégorie principale
        elif main_category:
            final_category = main_category
            print("DEBUG - Utilisation de la catégorie principale:", main_category.id, main_category.name)
        # Sinon, utiliser le champ caché (pour compatibilité)
        elif category_id:
            try:
                final_category = Category.objects.get(id=category_id)
                print("DEBUG - Utilisation du champ caché:", final_category.id, final_category.name)
            except Category.DoesNotExist:
                pass

        # Valider que nous avons une catégorie
        if not final_category:
            print("DEBUG - ERREUR: Aucune catégorie trouvée")
            raise ValidationError({
                'main_category': _("Veuillez sélectionner une catégorie principale.")
            })

        # S'assurer que la catégorie est active
        if not final_category.is_active:
            print("DEBUG - ERREUR: Catégorie inactive")
            raise ValidationError({
                'main_category': _("Cette catégorie n'est pas disponible.")
            })

        # Mettre à jour les données nettoyées
        cleaned_data['category'] = final_category
        print("DEBUG - Catégorie finale définie:", final_category.id, final_category.name)

        return cleaned_data

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
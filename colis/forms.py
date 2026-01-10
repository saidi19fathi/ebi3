# ~/ebi3/colis/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from django_countries import countries
from django_countries.widgets import CountrySelectWidget

from .models import Package, PackageCategory, PackageImage, TransportOffer, PackageReport
from users.models import User
from carriers.models import Carrier


class PackageBaseForm(forms.ModelForm):
    """Formulaire de base pour les colis"""

    # AJOUT: Champs pour la sélection hiérarchique des catégories
    main_category = forms.ModelChoiceField(
        queryset=PackageCategory.objects.filter(parent__isnull=True, is_active=True),
        required=False,
        label=_("Catégorie principale"),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_main_category'
        })
    )

    sub_category = forms.ModelChoiceField(
        queryset=PackageCategory.objects.none(),  # Vide initialement
        required=False,
        label=_("Sous-catégorie"),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_sub_category',
            'disabled': 'disabled'
        })
    )

    # MODIFICATION: Champ category rendu caché
    category = forms.ModelChoiceField(
        queryset=PackageCategory.objects.filter(is_active=True),
        required=True,
        label=_("Catégorie finale"),
        widget=forms.HiddenInput(attrs={'id': 'id_final_category'})
    )

    # Champs supplémentaires pour l'UI
    use_current_location = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Utiliser ma position actuelle"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Package
        fields = [
            'title', 'category', 'package_type', 'description',
            'weight', 'length', 'width', 'height',
            'pickup_country', 'pickup_city', 'pickup_address', 'pickup_postal_code',
            'delivery_country', 'delivery_city', 'delivery_address', 'delivery_postal_code',
            'pickup_date', 'delivery_date', 'flexible_dates',
            'price_type', 'asking_price', 'currency',
            'is_fragile', 'requires_insurance', 'insurance_value',
            'requires_packaging', 'requires_loading_help', 'requires_unloading_help',
            # AJOUT: Champs pour la hiérarchie des catégories
            'main_category', 'sub_category'
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ex: Déménagement Paris → Lyon")
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _("Décrivez votre colis en détail...\n• Contenu\n• État\n• Instructions spéciales")
            }),
            'category': forms.HiddenInput(attrs={'id': 'id_final_category'}),  # Changé en HiddenInput
            'package_type': forms.Select(attrs={'class': 'form-control'}),
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
            'pickup_country': CountrySelectWidget(attrs={'class': 'form-control'}),
            'pickup_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ville de départ")
            }),
            'pickup_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _("Adresse complète (optionnel)")
            }),
            'pickup_postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Code postal")
            }),
            'delivery_country': CountrySelectWidget(attrs={'class': 'form-control'}),
            'delivery_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Ville de destination")
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _("Adresse complète (optionnel)")
            }),
            'delivery_postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _("Code postal")
            }),
            'pickup_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'delivery_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'price_type': forms.Select(attrs={'class': 'form-control'}),
            'asking_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': _("0.00")
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'insurance_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }

        labels = {
            'flexible_dates': _("Dates flexibles"),
            'is_fragile': _("Colis fragile"),
            'requires_insurance': _("Assurance requise"),
            'requires_packaging': _("Emballage requis"),
            'requires_loading_help': _("Aide au chargement nécessaire"),
            'requires_unloading_help': _("Aide au déchargement nécessaire"),
        }

        help_texts = {
            'asking_price': _("Prix que vous souhaitez payer pour le transport"),
            'pickup_date': _("Date à partir de laquelle le colis est disponible"),
            'delivery_date': _("Date limite pour la livraison"),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Initialiser la hiérarchie des catégories si le colis existe déjà
        if self.instance and self.instance.pk and self.instance.category:
            category = self.instance.category
            # Trouver la catégorie racine
            ancestors = category.get_ancestors(include_self=True)
            if ancestors.exists():
                main_cat = ancestors.first()
                self.fields['main_category'].initial = main_cat.id

                # Configurer les sous-catégories
                if ancestors.count() > 1:
                    sub_cat = ancestors[1] if len(ancestors) > 1 else None
                    self.fields['sub_category'].queryset = PackageCategory.objects.filter(
                        parent=main_cat, is_active=True
                    )
                    if sub_cat:
                        self.fields['sub_category'].initial = sub_cat.id
                        # Configurer la catégorie finale
                        self.fields['category'].queryset = PackageCategory.objects.filter(
                            parent=sub_cat, is_active=True
                        )

        # Définir les dates par défaut
        if not self.instance.pk:
            self.fields['pickup_date'].initial = timezone.now().date() + timezone.timedelta(days=1)
            self.fields['delivery_date'].initial = timezone.now().date() + timezone.timedelta(days=7)

        # Ajuster les champs selon le type de colis
        if self.instance.package_type:
            self.adjust_fields_for_package_type()

        # Masquer les champs d'assurance si non requis
        self.fields['insurance_value'].widget.attrs['class'] = 'form-control insurance-field'
        if not self.data.get('requires_insurance', False) and not self.instance.requires_insurance:
            self.fields['insurance_value'].widget.attrs['style'] = 'display: none;'

    def adjust_fields_for_package_type(self):
        """Ajuste les champs requis selon le type de colis"""
        package_type = self.instance.package_type or self.data.get('package_type')

        if package_type == Package.PackageType.SMALL_PACKAGE:
            self.fields['requires_loading_help'].required = False
            self.fields['requires_unloading_help'].required = False
        elif package_type == Package.PackageType.FURNITURE:
            self.fields['requires_loading_help'].initial = True
            self.fields['requires_unloading_help'].initial = True

    def clean(self):
        cleaned_data = super().clean()

        # Validation de la catégorie hiérarchique
        main_category = cleaned_data.get('main_category')
        sub_category = cleaned_data.get('sub_category')
        final_category = cleaned_data.get('category')

        # Si une catégorie finale est sélectionnée, vérifier la hiérarchie
        if final_category:
            try:
                final_cat = PackageCategory.objects.get(id=final_category)
                ancestors = final_cat.get_ancestors(include_self=True)

                # Valider que main_category correspond au bon ancêtre
                if main_category and ancestors.exists():
                    expected_main = ancestors.first()
                    if main_category != expected_main:
                        raise ValidationError({
                            'main_category': _("La catégorie principale ne correspond pas à la hiérarchie sélectionnée.")
                        })

                # Valider que sub_category correspond si spécifié
                if sub_category and ancestors.count() > 1:
                    expected_sub = ancestors[1] if len(ancestors) > 1 else None
                    if sub_category != expected_sub:
                        raise ValidationError({
                            'sub_category': _("La sous-catégorie ne correspond pas à la hiérarchie sélectionnée.")
                        })
            except PackageCategory.DoesNotExist:
                raise ValidationError({
                    'category': _("La catégorie sélectionnée n'existe pas.")
                })

        # Calcul automatique du type de colis basé sur le poids
        weight = cleaned_data.get('weight')
        if weight and not cleaned_data.get('package_type'):
            if weight <= 30:
                cleaned_data['package_type'] = Package.PackageType.SMALL_PACKAGE
            elif weight <= 100:
                cleaned_data['package_type'] = Package.PackageType.MEDIUM_PACKAGE
            elif weight <= 500:
                cleaned_data['package_type'] = Package.PackageType.LARGE_PACKAGE
            else:
                cleaned_data['package_type'] = Package.PackageType.PALLET

        return cleaned_data

    def clean_delivery_date(self):
        pickup_date = self.cleaned_data.get('pickup_date')
        delivery_date = self.cleaned_data.get('delivery_date')

        if pickup_date and delivery_date:
            if delivery_date < pickup_date:
                raise ValidationError(
                    _("La date de livraison doit être postérieure à la date de départ.")
                )

            # Maximum 90 jours entre départ et livraison
            if (delivery_date - pickup_date).days > 90:
                raise ValidationError(
                    _("L'écart maximum entre départ et livraison est de 90 jours.")
                )

            if delivery_date < timezone.now().date():
                raise ValidationError(
                    _("La date de livraison ne peut pas être dans le passé.")
                )

        return delivery_date

    def clean_pickup_date(self):
        pickup_date = self.cleaned_data.get('pickup_date')

        if pickup_date and pickup_date < timezone.now().date():
            raise ValidationError(
                _("La date de départ ne peut pas être dans le passé.")
            )

        return pickup_date

    def clean_asking_price(self):
        price = self.cleaned_data.get('asking_price')
        price_type = self.cleaned_data.get('price_type')

        if price:
            if price <= 0:
                raise ValidationError(_("Le prix doit être supérieur à 0."))

            if price_type == Package.PriceType.FIXED and price < 5:
                raise ValidationError(_("Le prix fixe minimum est de 5€."))

        return price

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')

        if weight:
            if weight <= 0:
                raise ValidationError(_("Le poids doit être supérieur à 0."))
            if weight > 2000:  # 2 tonnes maximum
                raise ValidationError(_("Le poids maximum autorisé est de 2000 kg."))

        return weight

    def clean_insurance_value(self):
        requires_insurance = self.cleaned_data.get('requires_insurance', False)
        insurance_value = self.cleaned_data.get('insurance_value')

        if requires_insurance and not insurance_value:
            raise ValidationError(
                _("Veuillez spécifier la valeur à assurer.")
            )

        if insurance_value and insurance_value <= 0:
            raise ValidationError(_("La valeur assurée doit être positive."))

        return insurance_value


class PackageCreateForm(PackageBaseForm):
    """Formulaire pour créer un colis"""

    accept_terms = forms.BooleanField(
        required=True,
        label=_("J'accepte les conditions générales"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={'required': _("Vous devez accepter les conditions générales.")}
    )

    def save(self, commit=True):
        package = super().save(commit=False)

        if self.user:
            package.sender = self.user

        if commit:
            package.save()

        return package


class PackageUpdateForm(PackageBaseForm):
    """Formulaire pour mettre à jour un colis"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Empêcher la modification de certains champs si le colis est réservé
        if self.instance.status in [Package.Status.RESERVED, Package.Status.IN_TRANSIT]:
            disabled_fields = ['pickup_date', 'delivery_date', 'pickup_address',
                              'delivery_address', 'asking_price', 'price_type']
            for field in disabled_fields:
                if field in self.fields:
                    self.fields[field].disabled = True
                    self.fields[field].help_text = _("Non modifiable car le colis est réservé.")


class PackageImageForm(forms.ModelForm):
    """Formulaire pour les images de colis"""

    class Meta:
        model = PackageImage
        fields = ['image', 'caption', 'is_primary', 'display_order']

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

    def clean_image(self):
        image = self.cleaned_data.get('image')

        if image:
            # Vérifier la taille (déjà fait par le validateur)
            # Vérifier le type MIME
            import imghdr
            image.seek(0)
            file_type = imghdr.what(image)
            if file_type not in ['jpeg', 'png', 'gif', 'webp']:
                raise ValidationError(
                    _("Format d'image non supporté. Utilisez JPEG, PNG, GIF ou WebP.")
                )
            image.seek(0)

        return image


class TransportOfferForm(forms.ModelForm):
    """Formulaire pour proposer une offre de transport"""

    class Meta:
        model = TransportOffer
        fields = [
            'price', 'currency', 'proposed_pickup_date', 'proposed_delivery_date',
            'message', 'provides_insurance', 'insurance_coverage',
            'provides_packaging', 'provides_loading', 'provides_unloading'
        ]

        widgets = {
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': _("0.00")
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'proposed_pickup_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'proposed_delivery_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _("Présentez-vous et expliquez pourquoi vous êtes le bon transporteur...")
            }),
            'insurance_coverage': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }

        labels = {
            'provides_insurance': _("Je fournis une assurance"),
            'provides_packaging': _("Je fournis l'emballage"),
            'provides_loading': _("Je fournis le chargement"),
            'provides_unloading': _("Je fournis le déchargement"),
        }

    def __init__(self, *args, **kwargs):
        self.package = kwargs.pop('package', None)
        self.carrier = kwargs.pop('carrier', None)
        super().__init__(*args, **kwargs)

        # Pré-remplir les dates basées sur le colis
        if self.package and not self.instance.pk:
            self.fields['proposed_pickup_date'].initial = self.package.pickup_date
            self.fields['proposed_delivery_date'].initial = self.package.delivery_date
            self.fields['currency'].initial = self.package.currency

            # Suggérer un prix basé sur le prix demandé
            if self.package.asking_price:
                suggested_price = float(self.package.asking_price) * 0.9  # 10% de moins
                self.fields['price'].initial = round(suggested_price, 2)

        # Masquer le champ de couverture d'assurance si non fournie
        self.fields['insurance_coverage'].widget.attrs['class'] = 'form-control insurance-coverage-field'
        if not self.data.get('provides_insurance', False) and not self.instance.provides_insurance:
            self.fields['insurance_coverage'].widget.attrs['style'] = 'display: none;'

    def clean_proposed_delivery_date(self):
        pickup_date = self.cleaned_data.get('proposed_pickup_date')
        delivery_date = self.cleaned_data.get('proposed_delivery_date')

        if pickup_date and delivery_date and delivery_date < pickup_date:
            raise ValidationError(
                _("La date de livraison proposée doit être postérieure à la date de départ.")
            )

        # Vérifier que la livraison est avant la date limite du colis
        if self.package and delivery_date:
            if delivery_date > self.package.delivery_date and not self.package.flexible_dates:
                raise ValidationError(
                    _("La date de livraison proposée dépasse la date limite du colis.")
                )

        return delivery_date

    def clean_proposed_pickup_date(self):
        pickup_date = self.cleaned_data.get('proposed_pickup_date')

        # Vérifier que le départ est après la date demandée
        if self.package and pickup_date:
            if pickup_date < self.package.pickup_date and not self.package.flexible_dates:
                raise ValidationError(
                    _("La date de départ proposée est antérieure à la date demandée.")
                )

        return pickup_date

    def clean_price(self):
        price = self.cleaned_data.get('price')

        if price:
            if price <= 0:
                raise ValidationError(_("Le prix doit être supérieur à 0."))

            # Vérifier que le prix n'est pas trop bas par rapport au prix demandé
            if self.package and self.package.asking_price:
                min_price = float(self.package.asking_price) * 0.5  # Minimum 50% du prix demandé
                if price < min_price:
                    raise ValidationError(
                        _("Le prix proposé est trop bas. Le minimum suggéré est {:.2f}€.").format(min_price)
                    )

        return price

    def clean_insurance_coverage(self):
        provides_insurance = self.cleaned_data.get('provides_insurance', False)
        insurance_coverage = self.cleaned_data.get('insurance_coverage')

        if provides_insurance and not insurance_coverage:
            raise ValidationError(
                _("Veuillez spécifier le montant de la couverture d'assurance.")
            )

        if insurance_coverage and insurance_coverage <= 0:
            raise ValidationError(_("La couverture d'assurance doit être positive."))

        return insurance_coverage

    def save(self, commit=True):
        offer = super().save(commit=False)

        if self.package:
            offer.package = self.package

        if self.carrier:
            offer.carrier = self.carrier

        if commit:
            offer.save()

        return offer


class PackageSearchForm(forms.Form):
    """Formulaire de recherche de colis"""

    q = forms.CharField(
        required=False,
        label=_("Rechercher"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Que souhaitez-vous transporter ?")
        })
    )

    category = forms.ModelChoiceField(
        required=False,
        queryset=PackageCategory.objects.filter(is_active=True),
        label=_("Catégorie"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    package_type = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous"))] + list(Package.PackageType.choices),
        label=_("Type de colis"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # Origine
    pickup_country = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous les pays"))] + list(countries),
        label=_("Pays de départ"),
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )

    pickup_city = forms.CharField(
        required=False,
        label=_("Ville de départ"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: Paris, Lyon...")
        })
    )

    # Destination
    delivery_country = forms.ChoiceField(
        required=False,
        choices=[('', _("Tous les pays"))] + list(countries),
        label=_("Pays de destination"),
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )

    delivery_city = forms.CharField(
        required=False,
        label=_("Ville de destination"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: Marseille, Casablanca...")
        })
    )

    # Dates
    pickup_date_from = forms.DateField(
        required=False,
        label=_("Départ à partir du"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    pickup_date_to = forms.DateField(
        required=False,
        label=_("Départ jusqu'au"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    # Dimensions et poids
    max_weight = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=3,
        label=_("Poids maximum (kg)"),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: 50")
        })
    )

    max_volume = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=3,
        label=_("Volume maximum (L)"),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _("Ex: 100")
        })
    )

    # Prix
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

    # Options
    flexible_dates = forms.BooleanField(
        required=False,
        label=_("Dates flexibles seulement"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    provides_insurance = forms.BooleanField(
        required=False,
        label=_("Transport avec assurance"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Tri
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', _("Plus récent")),
            ('pickup_date', _("Départ proche")),
            ('asking_price', _("Prix croissant")),
            ('-asking_price', _("Prix décroissant")),
            ('-view_count', _("Plus populaire")),
        ],
        initial='-created_at',
        label=_("Trier par"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        pickup_date_from = cleaned_data.get('pickup_date_from')
        pickup_date_to = cleaned_data.get('pickup_date_to')
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')

        if pickup_date_from and pickup_date_to:
            if pickup_date_to < pickup_date_from:
                raise ValidationError(
                    _("La date 'jusqu'au' doit être postérieure à la date 'à partir du'.")
                )

        if min_price and max_price:
            if min_price > max_price:
                raise ValidationError(
                    _("Le prix minimum ne peut pas être supérieur au prix maximum.")
                )

        return cleaned_data


class PackageReportForm(forms.ModelForm):
    """Formulaire pour signaler un colis"""

    class Meta:
        model = PackageReport
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

        labels = {
            'evidence': _("Preuve (capture d'écran, document...)"),
        }


class QuickQuoteForm(forms.Form):
    """Formulaire de devis rapide (pour transporteurs)"""

    pickup_address = forms.CharField(
        label=_("Adresse de départ"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Adresse complète")
        })
    )

    delivery_address = forms.CharField(
        label=_("Adresse de destination"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Adresse complète")
        })
    )

    weight = forms.DecimalField(
        label=_("Poids (kg)"),
        min_value=0.001,
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001'
        })
    )

    length = forms.DecimalField(
        required=False,
        label=_("Longueur (cm)"),
        min_value=0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        })
    )

    width = forms.DecimalField(
        required=False,
        label=_("Largeur (cm)"),
        min_value=0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        })
    )

    height = forms.DecimalField(
        required=False,
        label=_("Hauteur (cm)"),
        min_value=0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        })
    )

    pickup_date = forms.DateField(
        label=_("Date de départ souhaitée"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    delivery_date = forms.DateField(
        label=_("Date de livraison souhaitée"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    is_fragile = forms.BooleanField(
        required=False,
        label=_("Colis fragile"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    requires_insurance = forms.BooleanField(
        required=False,
        label=_("Assurance requise"),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    insurance_value = forms.DecimalField(
        required=False,
        label=_("Valeur à assurer"),
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )

    def clean_delivery_date(self):
        pickup_date = self.cleaned_data.get('pickup_date')
        delivery_date = self.cleaned_data.get('delivery_date')

        if pickup_date and delivery_date and delivery_date < pickup_date:
            raise ValidationError(
                _("La date de livraison doit être postérieure à la date de départ.")
            )

        return delivery_date


# Formsets
PackageImageFormSet = inlineformset_factory(
    Package,
    PackageImage,
    form=PackageImageForm,
    extra=5,  # 5 formulaires d'image vides par défaut
    max_num=15,  # Maximum d'images
    can_delete=True,
    validate_max=True,
)


class PackageFilterForm(forms.Form):
    """Formulaire de filtrage pour le dashboard"""

    STATUS_CHOICES = [
        ('', _("Tous les statuts")),
        ('AVAILABLE', _("Disponible")),
        ('RESERVED', _("Réservé")),
        ('IN_TRANSIT', _("En transit")),
        ('DELIVERED', _("Livré")),
        ('CANCELLED', _("Annulé")),
    ]

    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        label=_("Statut"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_from = forms.DateField(
        required=False,
        label=_("À partir du"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    date_to = forms.DateField(
        required=False,
        label=_("Jusqu'au"),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_to < date_from:
            raise ValidationError(
                _("La date 'jusqu'au' doit être postérieure à la date 'à partir du'.")
            )

        return cleaned_data
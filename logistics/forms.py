# ~/ebi3/logistics/forms.py

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

from .models import (
    Reservation, Mission, Route, TransportProposal, TrackingEvent,
    LogisticsOption, ReservationStatus, MissionStatus, RouteStatus,
    TransportProposalStatus, TrackingEventType
)
from ads.models import Ad
from carriers.models import Carrier
from core.models import Country, City


class ReservationForm(forms.ModelForm):
    """Formulaire de création/modification de réservation"""

    class Meta:
        model = Reservation
        fields = [
            'logistics_option',
            'carrier',
            'pickup_address',
            'delivery_address',
            'pickup_date',
            'delivery_date',
            'shipping_cost',
            'insurance_cost',
            'requires_insurance',
            'insurance_value',
            'requires_packaging',
            'packaging_details',
            'buyer_notes'
        ]
        widgets = {
            'logistics_option': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'toggleCarrierField()'
            }),
            'carrier': forms.Select(attrs={
                'class': 'form-select',
                'id': 'carrier-select'
            }),
            'pickup_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Adresse complète de prise en charge')
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Adresse complète de livraison')
            }),
            'pickup_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'delivery_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'shipping_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'insurance_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'insurance_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'packaging_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Spécifications d\'emballage si nécessaire')
            }),
            'buyer_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Notes ou instructions spéciales')
            }),
        }
        labels = {
            'logistics_option': _('Option logistique'),
            'carrier': _('Transporteur'),
            'pickup_address': _('Adresse de prise en charge'),
            'delivery_address': _('Adresse de livraison'),
            'pickup_date': _('Date de prise en charge'),
            'delivery_date': _('Date de livraison estimée'),
            'shipping_cost': _('Coût du transport (€)'),
            'insurance_cost': _('Coût de l\'assurance (€)'),
            'requires_insurance': _('Nécessite une assurance'),
            'insurance_value': _('Valeur à assurer (€)'),
            'requires_packaging': _('Nécessite un emballage'),
            'packaging_details': _('Détails de l\'emballage'),
            'buyer_notes': _('Notes pour le vendeur/transporteur'),
        }
        help_texts = {
            'logistics_option': _('Choisissez comment vous souhaitez faire livrer l\'objet'),
            'pickup_date': _('Date à laquelle l\'objet sera pris en charge'),
            'delivery_date': _('Date estimée de livraison chez vous'),
        }

    def __init__(self, *args, **kwargs):
        self.ad = kwargs.pop('ad', None)
        self.buyer = kwargs.pop('buyer', None)
        super().__init__(*args, **kwargs)

        if self.ad:
            # Filtrer les transporteurs disponibles pour cette annonce
            self.fields['carrier'].queryset = Carrier.objects.filter(
                is_available=True,
                status=Carrier.Status.APPROVED,
                max_weight__gte=self.ad.weight if self.ad.weight else 0,
                max_volume__gte=self.ad.volume if self.ad.volume else 0
            ).select_related('user')

            # Pré-remplir certaines informations
            if not self.instance.pk:
                self.initial['pickup_address'] = self.ad.address_from
                self.initial['delivery_address'] = self.ad.address_to

                # Calculer le coût de transport estimé
                estimated_cost = self.estimate_shipping_cost()
                if estimated_cost:
                    self.initial['shipping_cost'] = estimated_cost

        # Ajouter des classes CSS aux champs booléens
        for field_name in ['requires_insurance', 'requires_packaging']:
            self.fields[field_name].widget.attrs['class'] = 'form-check-input'

    def estimate_shipping_cost(self):
        """Estime le coût de transport pour cette annonce"""
        if not self.ad:
            return None

        # Logique simplifiée d'estimation
        # Vous pouvez ajuster cette logique selon vos besoins
        base_cost = 10.0  # Coût de base

        if self.ad.weight:
            base_cost += self.ad.weight * 0.5  # 0.5€ par kg

        # Ajouter un coût pour la distance (simplifié)
        # Dans une vraie application, vous utiliseriez une API de distance
        base_cost += 20.0  # Coût distance estimé

        return round(base_cost, 2)

    def clean(self):
        cleaned_data = super().clean()

        logistics_option = cleaned_data.get('logistics_option')
        carrier = cleaned_data.get('carrier')
        pickup_date = cleaned_data.get('pickup_date')
        delivery_date = cleaned_data.get('delivery_date')
        requires_insurance = cleaned_data.get('requires_insurance')
        insurance_value = cleaned_data.get('insurance_value')

        # Validation de l'option logistique
        if logistics_option == LogisticsOption.WITH_CARRIER and not carrier:
            self.add_error('carrier', _('Veuillez sélectionner un transporteur pour cette option.'))

        if logistics_option == LogisticsOption.P2P_DIRECT and carrier:
            self.add_error('carrier', _('L\'option P2P direct ne nécessite pas de transporteur.'))

        # Validation des dates
        if pickup_date and pickup_date < timezone.now().date():
            self.add_error('pickup_date', _('La date de prise en charge ne peut pas être dans le passé.'))

        if delivery_date and pickup_date and delivery_date < pickup_date:
            self.add_error('delivery_date', _('La date de livraison doit être après la date de prise en charge.'))

        # Validation de l'assurance
        if requires_insurance and not insurance_value:
            self.add_error('insurance_value', _('Veuillez spécifier la valeur à assurer.'))

        if insurance_value and not requires_insurance:
            self.add_error('requires_insurance', _('Cochez cette case si vous voulez une assurance.'))

        # Validation du transporteur (capacités)
        if carrier and self.ad:
            if self.ad.weight and carrier.max_weight < self.ad.weight:
                self.add_error('carrier', _('Ce transporteur ne peut pas prendre en charge le poids de cet objet.'))

            if self.ad.volume and carrier.max_volume < self.ad.volume:
                self.add_error('carrier', _('Ce transporteur ne peut pas prendre en charge le volume de cet objet.'))

        return cleaned_data


class ReservationStatusForm(forms.ModelForm):
    """Formulaire de changement de statut d'une réservation"""

    class Meta:
        model = Reservation
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrer les statuts disponibles selon le statut actuel
        current_status = self.instance.status
        available_statuses = self.get_available_statuses(current_status)

        self.fields['status'].choices = [
            (status.value, label) for status, label in ReservationStatus.choices
            if status in available_statuses
        ]

    def get_available_statuses(self, current_status):
        """Détermine les statuts disponibles selon le statut actuel"""
        status_transitions = {
            ReservationStatus.PENDING: [
                ReservationStatus.CONFIRMED,
                ReservationStatus.CANCELLED
            ],
            ReservationStatus.CONFIRMED: [
                ReservationStatus.PAYMENT_PENDING,
                ReservationStatus.CANCELLED
            ],
            ReservationStatus.PAYMENT_PENDING: [
                ReservationStatus.PAID,
                ReservationStatus.CANCELLED
            ],
            ReservationStatus.PAID: [
                ReservationStatus.IN_TRANSIT,
                ReservationStatus.CANCELLED
            ],
            ReservationStatus.IN_TRANSIT: [
                ReservationStatus.DELIVERED,
                ReservationStatus.DISPUTED
            ],
            ReservationStatus.DELIVERED: [],
            ReservationStatus.CANCELLED: [],
            ReservationStatus.DISPUTED: [
                ReservationStatus.DELIVERED,
                ReservationStatus.REFUNDED
            ],
            ReservationStatus.REFUNDED: [],
        }

        # Toujours permettre de rester dans le même statut
        return [current_status] + status_transitions.get(current_status, [])


class MissionForm(forms.ModelForm):
    """Formulaire de création/modification de mission"""

    class Meta:
        model = Mission
        fields = [
            'status',
            'current_location',
            'estimated_delivery',
            'delay_reason',
            'notes'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'current_location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ville, pays')
            }),
            'estimated_delivery': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'min': timezone.now().isoformat()[:16]
            }),
            'delay_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Raison du retard...')
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Notes internes...')
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si la mission est retardée, rendre le champ delay_reason obligatoire
        if self.instance.status == MissionStatus.DELAYED:
            self.fields['delay_reason'].required = True


class TrackingEventForm(forms.ModelForm):
    """Formulaire de création d'événement de suivi"""

    class Meta:
        model = TrackingEvent
        fields = [
            'event_type',
            'description',
            'location',
            'photo'
        ]
        widgets = {
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Détails de l\'événement...')
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ville, pays ou adresse')
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.mission = kwargs.pop('mission', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les types d'événements selon le statut de la mission
        if self.mission:
            available_events = self.get_available_events(self.mission.status)
            self.fields['event_type'].choices = [
                (event.value, label) for event, label in TrackingEventType.choices
                if event in available_events
            ]

        # Pré-remplir la localisation
        if self.mission and self.mission.current_location:
            self.initial['location'] = self.mission.current_location

    def get_available_events(self, mission_status):
        """Détermine les événements disponibles selon le statut de la mission"""
        event_mapping = {
            MissionStatus.SCHEDULED: [
                TrackingEventType.PICKUP_SCHEDULED,
                TrackingEventType.PICKUP_CONFIRMED,
                TrackingEventType.DELAYED
            ],
            MissionStatus.PICKUP_PENDING: [
                TrackingEventType.PICKUP_CONFIRMED,
                TrackingEventType.PICKUP_COMPLETED,
                TrackingEventType.DELAYED
            ],
            MissionStatus.PICKED_UP: [
                TrackingEventType.IN_TRANSIT,
                TrackingEventType.CUSTOMS_CLEARANCE,
                TrackingEventType.DELAYED
            ],
            MissionStatus.IN_TRANSIT: [
                TrackingEventType.ARRIVED_AT_HUB,
                TrackingEventType.DEPARTED_FROM_HUB,
                TrackingEventType.CUSTOMS_CLEARANCE,
                TrackingEventType.CUSTOMS_HELD,
                TrackingEventType.DELAYED
            ],
            MissionStatus.AT_HUB: [
                TrackingEventType.DEPARTED_FROM_HUB,
                TrackingEventType.OUT_FOR_DELIVERY,
                TrackingEventType.DELAYED
            ],
            MissionStatus.OUT_FOR_DELIVERY: [
                TrackingEventType.DELIVERY_ATTEMPTED,
                TrackingEventType.DELIVERY_RESCHEDULED,
                TrackingEventType.DELIVERED,
                TrackingEventType.DELAYED
            ],
            MissionStatus.DELIVERY_PENDING: [
                TrackingEventType.DELIVERY_ATTEMPTED,
                TrackingEventType.DELIVERY_RESCHEDULED,
                TrackingEventType.DELIVERED,
                TrackingEventType.DELAYED
            ],
            MissionStatus.DELAYED: [
                TrackingEventType.ISSUE_RESOLVED,
                TrackingEventType.IN_TRANSIT,
                TrackingEventType.OUT_FOR_DELIVERY
            ],
            MissionStatus.DELIVERED: [],
            MissionStatus.CANCELLED: [],
        }

        return event_mapping.get(mission_status, [])


class RouteForm(forms.ModelForm):
    """Formulaire de création/modification de route"""

    start_country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        label=_("Pays de départ"),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    end_country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        label=_("Pays d'arrivée"),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Route
        fields = [
            'start_city',
            'start_country',
            'start_address',
            'end_city',
            'end_country',
            'end_address',
            'departure_date',
            'arrival_date',
            'max_weight',
            'max_volume',
            'available_weight',
            'available_volume',
            'fixed_price',
            'price_per_kg',
            'price_per_m3',
            'includes_insurance',
            'includes_packaging',
            'includes_loading',
            'includes_unloading',
            'description',
            'special_conditions'
        ]
        widgets = {
            'start_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ville de départ')
            }),
            'end_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ville d\'arrivée')
            }),
            'start_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Adresse exacte de départ (optionnel)')
            }),
            'end_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Adresse exacte d\'arrivée (optionnel)')
            }),
            'departure_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'arrival_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'max_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
            'max_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
            'available_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
            'available_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
            'fixed_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'price_per_kg': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'price_per_m3': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Décrivez votre trajet...')
            }),
            'special_conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Conditions spéciales, restrictions...')
            }),
        }
        labels = {
            'start_city': _('Ville de départ'),
            'end_city': _('Ville d\'arrivée'),
            'start_address': _('Adresse de départ'),
            'end_address': _('Adresse d\'arrivée'),
            'departure_date': _('Date de départ'),
            'arrival_date': _('Date d\'arrivée'),
            'max_weight': _('Poids maximum (kg)'),
            'max_volume': _('Volume maximum (m³)'),
            'available_weight': _('Poids disponible (kg)'),
            'available_volume': _('Volume disponible (m³)'),
            'fixed_price': _('Prix fixe (€)'),
            'price_per_kg': _('Prix par kg (€)'),
            'price_per_m3': _('Prix par m³ (€)'),
            'includes_insurance': _('Assurance incluse'),
            'includes_packaging': _('Emballage inclus'),
            'includes_loading': _('Chargement inclus'),
            'includes_unloading': _('Déchargement inclus'),
            'description': _('Description'),
            'special_conditions': _('Conditions spéciales'),
        }

    def __init__(self, *args, **kwargs):
        self.carrier = kwargs.pop('carrier', None)
        super().__init__(*args, **kwargs)

        # Si création, pré-remplir avec les capacités du transporteur
        if not self.instance.pk and self.carrier:
            self.initial['max_weight'] = self.carrier.max_weight
            self.initial['max_volume'] = self.carrier.max_volume
            self.initial['available_weight'] = self.carrier.max_weight
            self.initial['available_volume'] = self.carrier.max_volume

            # Utiliser base_price_per_km pour les calculs
            if hasattr(self.carrier, 'base_price_per_km'):
                self.initial['price_per_kg'] = self.carrier.base_price_per_km * 0.1  # Estimation
                self.initial['price_per_m3'] = self.carrier.base_price_per_km * 0.5  # Estimation

        # Ajouter des classes CSS aux champs booléens
        for field_name in ['includes_insurance', 'includes_packaging',
                          'includes_loading', 'includes_unloading']:
            self.fields[field_name].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        cleaned_data = super().clean()

        departure_date = cleaned_data.get('departure_date')
        arrival_date = cleaned_data.get('arrival_date')
        max_weight = cleaned_data.get('max_weight')
        available_weight = cleaned_data.get('available_weight')
        max_volume = cleaned_data.get('max_volume')
        available_volume = cleaned_data.get('available_volume')
        fixed_price = cleaned_data.get('fixed_price')
        price_per_kg = cleaned_data.get('price_per_kg')
        price_per_m3 = cleaned_data.get('price_per_m3')

        # Validation des dates
        if departure_date and departure_date < timezone.now().date():
            self.add_error('departure_date', _('La date de départ ne peut pas être dans le passé.'))

        if arrival_date and departure_date and arrival_date < departure_date:
            self.add_error('arrival_date', _('La date d\'arrivée doit être après la date de départ.'))

        # Validation des capacités
        if max_weight and available_weight and available_weight > max_weight:
            self.add_error('available_weight', _('Le poids disponible ne peut pas dépasser le poids maximum.'))

        if max_volume and available_volume and available_volume > max_volume:
            self.add_error('available_volume', _('Le volume disponible ne peut pas dépasser le volume maximum.'))

        # Validation des prix
        if not fixed_price and not price_per_kg and not price_per_m3:
            self.add_error('fixed_price', _('Veuillez spécifier au moins un type de prix.'))

        # Limiter les capacités selon celles du transporteur
        if self.carrier:
            if max_weight and max_weight > self.carrier.max_weight:
                self.add_error('max_weight', _(
                    f'Votre capacité maximale est de {self.carrier.max_weight} kg.'
                ))

            if max_volume and max_volume > self.carrier.max_volume:
                self.add_error('max_volume', _(
                    f'Votre volume maximal est de {self.carrier.max_volume} m³.'
                ))

        return cleaned_data


class RouteSearchForm(forms.Form):
    """Formulaire de recherche de routes"""

    start_city = forms.CharField(
        required=False,
        label=_('Ville de départ'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ville de départ')
        })
    )

    start_country = forms.ModelChoiceField(
        required=False,
        queryset=Country.objects.all(),
        label=_('Pays de départ'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    end_city = forms.CharField(
        required=False,
        label=_('Ville d\'arrivée'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Ville d\'arrivée')
        })
    )

    end_country = forms.ModelChoiceField(
        required=False,
        queryset=Country.objects.all(),
        label=_('Pays d\'arrivée'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    departure_date_from = forms.DateField(
        required=False,
        label=_('Départ après le'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().date().isoformat()
        })
    )

    departure_date_to = forms.DateField(
        required=False,
        label=_('Départ avant le'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().date().isoformat()
        })
    )

    max_price = forms.DecimalField(
        required=False,
        label=_('Prix maximum (€)'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
    )

    min_available_weight = forms.DecimalField(
        required=False,
        label=_('Poids disponible minimum (kg)'),
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001',
            'min': '0'
        })
    )

    min_available_volume = forms.DecimalField(
        required=False,
        label=_('Volume disponible minimum (m³)'),
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.001',
            'min': '0'
        })
    )

    includes_insurance = forms.BooleanField(
        required=False,
        label=_('Avec assurance'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    includes_packaging = forms.BooleanField(
        required=False,
        label=_('Avec emballage'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    carrier_type = forms.ChoiceField(
        required=False,
        choices=[('', _('Tous'))] + list(Carrier.CarrierType.choices),
        label=_('Type de transporteur'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('departure_date', _('Date de départ')),
            ('price', _('Prix croissant')),
            ('-price', _('Prix décroissant')),
            ('available_weight', _('Capacité disponible')),
            ('-created_at', _('Plus récent')),
        ],
        label=_('Trier par'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class TransportProposalForm(forms.ModelForm):
    """Formulaire de création de proposition de transport"""

    class Meta:
        model = TransportProposal
        fields = [
            'proposed_price',
            'message',
            'estimated_pickup_date',
            'estimated_delivery_date',
            'includes_insurance',
            'insurance_value',
            'includes_packaging',
            'includes_loading',
            'includes_unloading'
        ]
        widgets = {
            'proposed_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Présentez-vous et expliquez votre proposition...')
            }),
            'estimated_pickup_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'estimated_delivery_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': timezone.now().date().isoformat()
            }),
            'insurance_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }
        labels = {
            'proposed_price': _('Prix proposé (€)'),
            'message': _('Message au vendeur'),
            'estimated_pickup_date': _('Date de prise en charge estimée'),
            'estimated_delivery_date': _('Date de livraison estimée'),
            'includes_insurance': _('Inclure une assurance'),
            'insurance_value': _('Valeur assurée (€)'),
            'includes_packaging': _('Inclure l\'emballage'),
            'includes_loading': _('Inclure le chargement'),
            'includes_unloading': _('Inclure le déchargement'),
        }

    def __init__(self, *args, **kwargs):
        self.ad = kwargs.pop('ad', None)
        self.carrier = kwargs.pop('carrier', None)
        super().__init__(*args, **kwargs)

        if self.ad:
            # Calculer le prix suggéré basé sur l'annonce
            suggested_price = self.calculate_suggested_price()
            self.initial['proposed_price'] = suggested_price

        # Ajouter des classes CSS aux champs booléens
        for field_name in ['includes_insurance', 'includes_packaging',
                          'includes_loading', 'includes_unloading']:
            self.fields[field_name].widget.attrs['class'] = 'form-check-input'

    def calculate_suggested_price(self):
        """Calcule un prix suggéré pour la proposition"""
        if not self.ad or not self.carrier:
            return 0

        # Prix de base : coût estimé du transport
        base_price = 0

        # Si l'annonce a un poids, utiliser une estimation
        if self.ad.weight and hasattr(self.carrier, 'base_price_per_km'):
            # Estimation: 0.5€ par kg pour les courtes distances
            base_price += self.ad.weight * 0.5

        # Ajouter une marge (20%)
        suggested_price = base_price * 1.2

        # S'assurer que le prix est au moins le prix minimum du transporteur
        if hasattr(self.carrier, 'min_price') and suggested_price < self.carrier.min_price:
            suggested_price = self.carrier.min_price

        # Arrondir à 2 décimales
        return round(suggested_price, 2)

    def clean(self):
        cleaned_data = super().clean()

        estimated_pickup_date = cleaned_data.get('estimated_pickup_date')
        estimated_delivery_date = cleaned_data.get('estimated_delivery_date')
        includes_insurance = cleaned_data.get('includes_insurance')
        insurance_value = cleaned_data.get('insurance_value')
        proposed_price = cleaned_data.get('proposed_price')

        # Validation des dates
        if estimated_pickup_date and estimated_pickup_date < timezone.now().date():
            self.add_error('estimated_pickup_date', _('La date de prise en charge ne peut pas être dans le passé.'))

        if estimated_delivery_date and estimated_pickup_date and estimated_delivery_date < estimated_pickup_date:
            self.add_error('estimated_delivery_date', _('La date de livraison doit être après la date de prise en charge.'))

        # Validation de l'assurance
        if includes_insurance and not insurance_value:
            self.add_error('insurance_value', _('Veuillez spécifier la valeur à assurer.'))

        # Validation du prix
        if proposed_price and proposed_price <= 0:
            self.add_error('proposed_price', _('Le prix doit être supérieur à 0.'))

        # Vérifier les capacités du transporteur
        if self.carrier and self.ad:
            if self.ad.weight and self.carrier.max_weight < self.ad.weight:
                raise ValidationError(_(
                    'Votre capacité maximale est insuffisante pour cet objet.'
                ))

            if self.ad.volume and self.carrier.max_volume < self.ad.volume:
                raise ValidationError(_(
                    'Votre volume maximal est insuffisant pour cet objet.'
                ))

        return cleaned_data


class ProposalResponseForm(forms.ModelForm):
    """Formulaire de réponse à une proposition de transport"""

    accept = forms.BooleanField(
        required=False,
        label=_('Accepter la proposition'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = TransportProposal
        fields = ['response_message']
        widgets = {
            'response_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Votre message au transporteur...')
            }),
        }
        labels = {
            'response_message': _('Message'),
        }

    def clean(self):
        cleaned_data = super().clean()
        accept = cleaned_data.get('accept')
        response_message = cleaned_data.get('response_message')

        # Si on accepte, pas besoin de message
        # Si on refuse, un message est recommandé mais pas obligatoire
        if not accept and not response_message:
            self.add_error('response_message', _(
                'Un message expliquant votre refus est recommandé.'
            ))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        accept = self.cleaned_data.get('accept')
        if accept:
            instance.status = TransportProposalStatus.ACCEPTED
        else:
            instance.status = TransportProposalStatus.REJECTED

        instance.responded_at = timezone.now()

        if commit:
            instance.save()

        return instance


class LogisticsSettingsForm(forms.Form):
    """Formulaire des paramètres logistiques (formulaire simple, pas ModelForm)"""

    commission_rate = forms.DecimalField(
        label=_('Taux de commission (%)'),
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        help_text=_('Pourcentage prélevé sur chaque transaction')
    )

    reservation_expiry_hours = forms.IntegerField(
        label=_('Expiration réservation (heures)'),
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text=_('Délai avant expiration automatique d\'une réservation non confirmée')
    )

    proposal_expiry_days = forms.IntegerField(
        label=_('Expiration proposition (jours)'),
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        })
    )

    payment_hold_days = forms.IntegerField(
        label=_('Rétention paiement (jours)'),
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        help_text=_('Nombre de jours où le paiement est retenu après livraison')
    )

    auto_release_payment = forms.BooleanField(
        label=_('Libération automatique paiement'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text=_('Libérer automatiquement le paiement après la période de rétention')
    )

    notify_on_reservation = forms.BooleanField(
        label=_('Notifier nouvelle réservation'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    notify_on_status_change = forms.BooleanField(
        label=_('Notifier changement statut'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    notify_before_expiry = forms.BooleanField(
        label=_('Notifier avant expiration'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class QuickReservationForm(forms.Form):
    """Formulaire de réservation rapide (sans transporteur)"""

    pickup_date = forms.DateField(
        label=_('Date de prise en charge'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().date().isoformat()
        })
    )

    delivery_date = forms.DateField(
        label=_('Date de livraison estimée'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().date().isoformat()
        })
    )

    buyer_notes = forms.CharField(
        required=False,
        label=_('Notes'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Notes ou instructions...')
        })
    )

    agree_terms = forms.BooleanField(
        label=_('J\'accepte les conditions de réservation'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        pickup_date = cleaned_data.get('pickup_date')
        delivery_date = cleaned_data.get('delivery_date')

        if pickup_date and delivery_date and delivery_date < pickup_date:
            self.add_error('delivery_date', _('La date de livraison doit être après la date de prise en charge.'))

        return cleaned_data


# Formulaire pour les rapports/logistique
class LogisticsReportForm(forms.Form):
    """Formulaire pour générer des rapports logistiques"""

    report_type = forms.ChoiceField(
        label=_('Type de rapport'),
        choices=[
            ('reservations', _('Réservations')),
            ('missions', _('Missions')),
            ('revenue', _('Revenus')),
            ('carrier_performance', _('Performance des transporteurs')),
            ('delivery_times', _('Délais de livraison')),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    start_date = forms.DateField(
        label=_('Date de début'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    end_date = forms.DateField(
        label=_('Date de fin'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    carrier = forms.ModelChoiceField(
        label=_('Transporteur'),
        required=False,
        queryset=Carrier.objects.filter(status=Carrier.Status.APPROVED),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('La date de fin doit être après la date de début.'))

        return cleaned_data


# Formulaire pour les notifications
class LogisticsNotificationForm(forms.Form):
    """Formulaire pour gérer les notifications logistiques"""

    email_notifications = forms.BooleanField(
        label=_('Notifications par email'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    push_notifications = forms.BooleanField(
        label=_('Notifications push'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    notify_on_reservation = forms.BooleanField(
        label=_('Nouvelle réservation'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    notify_on_status_change = forms.BooleanField(
        label=_('Changement de statut'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    notify_on_delay = forms.BooleanField(
        label=_('Retard de livraison'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    notify_before_pickup = forms.BooleanField(
        label=_('Rappel avant prise en charge'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    notify_before_delivery = forms.BooleanField(
        label=_('Rappel avant livraison'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
# ~/ebi3/payments/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms import inlineformset_factory
from django.core.validators import RegexValidator
from django.utils.text import slugify
from django.db.models import Sum
import re
from decimal import Decimal
import uuid

from .models import (
    PaymentTransaction, PaymentMethod, Invoice, Refund,
    Commission, Payout, Wallet, WalletTransaction,
    Tax, ExchangeRate, FraudAlert, PaymentSession, PaymentCard,
    InvoiceItem, Currency, Plan, Subscription, Coupon
)
from users.models import User
from ads.models import Ad
from logistics.models import Mission

# ============================================================================
# VALIDATEURS PERSONNALISÉS
# ============================================================================

class CardNumberValidator:
    """Validateur de numéro de carte avec algorithme de Luhn"""

    def __call__(self, value):
        # Supprimer les espaces et tirets
        value = re.sub(r'\s+|-', '', value)

        if not value.isdigit():
            raise ValidationError(_("Le numéro de carte doit contenir uniquement des chiffres."))

        if len(value) < 13 or len(value) > 19:
            raise ValidationError(_("Numéro de carte invalide."))

        # Algorithme de Luhn
        def luhn_checksum(card_number):
            digits = [int(d) for d in str(card_number)]
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum([int(x) for x in str(d * 2)])
            return checksum % 10

        if luhn_checksum(value) != 0:
            raise ValidationError(_("Numéro de carte invalide."))

        # Détection du type de carte
        if value.startswith('4'):
            card_type = 'VISA'
        elif value.startswith(('51', '52', '53', '54', '55')):
            card_type = 'MASTERCARD'
        elif value.startswith(('34', '37')):
            card_type = 'AMEX'
        elif value.startswith(('300', '301', '302', '303', '304', '305', '36', '38')):
            card_type = 'DINERS'
        elif value.startswith(('6011', '65')):
            card_type = 'DISCOVER'
        else:
            card_type = 'UNKNOWN'

        return value, card_type


class CVVValidator:
    """Validateur de code de sécurité CVV"""

    def __call__(self, value):
        value = str(value).strip()

        if not value.isdigit():
            raise ValidationError(_("Le CVV doit contenir uniquement des chiffres."))

        if len(value) not in [3, 4]:
            raise ValidationError(_("Le CVV doit contenir 3 ou 4 chiffres."))

        return value


class ExpiryDateValidator:
    """Validateur de date d'expiration"""

    def __call__(self, value):
        today = timezone.now().date()

        # Vérifier que la date n'est pas passée
        if value < today:
            raise ValidationError(_("La date d'expiration est dépassée."))

        # Vérifier que la date n'est pas trop éloignée (max 10 ans)
        max_date = today.replace(year=today.year + 10)
        if value > max_date:
            raise ValidationError(_("La date d'expiration est trop éloignée."))

        return value


class IBANValidator:
    """Validateur d'IBAN (International Bank Account Number)"""

    def __call__(self, value):
        value = value.upper().replace(' ', '')

        # Vérifier la longueur
        if len(value) < 15 or len(value) > 34:
            raise ValidationError(_("IBAN invalide : longueur incorrecte."))

        # Vérifier le format (2 lettres + 2 chiffres + caractères alphanumériques)
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$', value):
            raise ValidationError(_("Format IBAN invalide."))

        # Vérifier le pays supporté
        supported_countries = ['FR', 'BE', 'DE', 'ES', 'IT', 'LU', 'NL', 'MA', 'TN', 'DZ']
        country_code = value[:2]
        if country_code not in supported_countries:
            raise ValidationError(_(f"IBAN du pays {country_code} non supporté."))

        # Algorithme de vérification IBAN
        def iban_checksum(iban):
            # Déplacer les 4 premiers caractères à la fin
            rearranged = iban[4:] + iban[:4]
            # Convertir les lettres en chiffres (A=10, B=11, ...)
            digits = ''
            for char in rearranged:
                if char.isdigit():
                    digits += char
                else:
                    digits += str(ord(char) - 55)
            # Calculer le modulo 97
            mod = int(digits) % 97
            return mod == 1

        if not iban_checksum(value):
            raise ValidationError(_("IBAN invalide : vérification échouée."))

        return value


class PhoneNumberValidator:
    """Validateur de numéro de téléphone pour mobile money"""

    def __call__(self, value):
        value = re.sub(r'\s+', '', value)

        # Formats internationaux
        patterns = [
            r'^\+[1-9]\d{10,14}$',  # Format international
            r'^0[5-9]\d{8}$',       # Format français
            r'^0[6-7]\d{8}$',       # Format marocain
        ]

        if not any(re.match(p, value) for p in patterns):
            raise ValidationError(_("Numéro de téléphone invalide."))

        return value

# ============================================================================
# FORMULAIRES MANQUANTS POUR COMPATIBILITÉ AVEC VIEWS.PY
# ============================================================================

class InvoiceForm(forms.ModelForm):
    """Formulaire pour créer/modifier une facture"""

    class Meta:
        model = Invoice
        fields = ['billing_name', 'billing_address', 'billing_country',
                 'billing_vat', 'invoice_date', 'due_date', 'notes']
        widgets = {
            'billing_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Nom complet')
            }),
            'billing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Adresse complète')
            }),
            'billing_country': forms.Select(attrs={
                'class': 'form-control'
            }),
            'billing_vat': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Numéro TVA (optionnel)')
            }),
            'invoice_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Notes additionnelles')
            }),
        }

    def __init__(self, *args, **kwargs):
        self.transaction = kwargs.pop('transaction', None)
        super().__init__(*args, **kwargs)

        if self.transaction:
            # Pré-remplir avec les informations de la transaction
            if self.transaction.payer:
                self.fields['billing_name'].initial = self.transaction.payer.get_full_name()

            # Calculer la date d'échéance (30 jours par défaut)
            if not self.instance.due_date:
                self.fields['due_date'].initial = timezone.now().date() + timezone.timedelta(days=30)


class PlanForm(forms.ModelForm):
    """Formulaire pour les plans d'abonnement"""

    class Meta:
        model = Plan
        fields = ['name', 'description', 'price', 'currency', 'interval',
                 'interval_count', 'trial_period_days', 'is_active', 'features']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Nom du plan')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Description du plan...')
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'interval': forms.Select(attrs={
                'class': 'form-control'
            }),
            'interval_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'trial_period_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'features': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Fonctionnalités (format JSON)')
            }),
        }


class SubscriptionForm(forms.ModelForm):
    """Formulaire pour les abonnements"""

    class Meta:
        model = Subscription
        fields = ['plan', 'status', 'current_period_start', 'current_period_end',
                 'cancel_at_period_end', 'metadata']
        widgets = {
            'plan': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'current_period_start': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'current_period_end': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'metadata': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Métadonnées (format JSON)')
            }),
        }


class CouponForm(forms.ModelForm):
    """Formulaire pour les coupons de réduction"""

    class Meta:
        model = Coupon
        fields = ['code', 'discount_type', 'discount_value', 'currency',
                 'valid_from', 'valid_until', 'max_uses', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Code du coupon')
            }),
            'discount_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'valid_from': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'valid_until': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'max_uses': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
        }


class PaymentSessionForm(forms.ModelForm):
    """Formulaire pour les sessions de paiement"""

    class Meta:
        model = PaymentSession
        fields = ['amount', 'currency', 'payment_method', 'metadata', 'expires_at']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'metadata': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Métadonnées (format JSON)')
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Définir la date d'expiration par défaut (30 minutes)
        if not self.instance.expires_at:
            self.fields['expires_at'].initial = timezone.now() + timezone.timedelta(minutes=30)


class CurrencyForm(forms.ModelForm):
    """Formulaire pour les devises"""

    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'is_active', 'exchange_rate', 'display_order']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('EUR, USD, etc.')
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Euro, Dollar US, etc.')
            }),
            'symbol': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('€, $, £, etc.')
            }),
            'exchange_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001'
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
        }


class PaymentCardForm(forms.ModelForm):
    """Formulaire pour les cartes bancaires"""

    class Meta:
        model = PaymentCard
        fields = ['cardholder_name', 'expiry_month', 'expiry_year',
                 'is_default', 'is_active']
        widgets = {
            'cardholder_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Nom tel qu\'indiqué sur la carte')
            }),
            'expiry_month': forms.Select(attrs={
                'class': 'form-control',
                'choices': [(str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)]
            }),
            'expiry_year': forms.Select(attrs={
                'class': 'form-control',
                'choices': [(str(i), str(i)) for i in range(timezone.now().year, timezone.now().year + 11)]
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Définir les valeurs par défaut pour l'expiration
        now = timezone.now()
        self.fields['expiry_month'].initial = str(now.month).zfill(2)
        self.fields['expiry_year'].initial = str(now.year)


# ============================================================================
# FORMULAIRES DE BASE (EXISTANTS)
# ============================================================================

class PaymentForm(forms.Form):
    """Formulaire de base pour les paiements"""

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Montant'),
            'step': '0.01'
        }),
        label=_("Montant")
    )

    currency = forms.ChoiceField(
        choices=[
            ('EUR', '€ EUR'),
            ('USD', '$ USD'),
            ('GBP', '£ GBP'),
            ('MAD', 'DH MAD'),
            ('XOF', 'CFA XOF'),
        ],
        initial='EUR',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_("Devise")
    )

    description = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Description du paiement')
        }),
        label=_("Description")
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

# ============================================================================
# FORMULAIRES DE PAIEMENT PRINCIPAUX (EXISTANTS)
# ============================================================================

class PaymentCheckoutForm(forms.Form):
    """Formulaire de checkout principal"""

    # Montant et devise
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Montant'),
            'step': '0.01'
        }),
        label=_("Montant")
    )

    currency = forms.ChoiceField(
        choices=[
            ('EUR', '€ EUR'),
            ('USD', '$ USD'),
            ('GBP', '£ GBP'),
            ('MAD', 'DH MAD'),
            ('XOF', 'CFA XOF'),
        ],
        initial='EUR',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_("Devise")
    )

    # Méthode de paiement
    payment_method = forms.ChoiceField(
        choices=PaymentTransaction.PaymentMethod.choices,
        initial='CREDIT_CARD',
        widget=forms.RadioSelect(attrs={
            'class': 'payment-method-radio'
        }),
        label=_("Méthode de paiement")
    )

    # Pour les paiements liés à des objets
    object_type = forms.ChoiceField(
        choices=[
            ('', _('Sélectionnez...')),
            ('AD', _('Annonce')),
            ('MISSION', _('Mission')),
            ('WALLET', _('Portefeuille')),
            ('OTHER', _('Autre')),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'object-type'
        }),
        label=_("Type d'objet")
    )

    object_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("ID de l'objet")
    )

    # Notes optionnelles
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Notes additionnelles...')
        }),
        label=_("Notes")
    )

    # Conditions générales
    accept_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_("J'accepte les conditions générales et la politique de confidentialité")
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.object = kwargs.pop('object', None)
        super().__init__(*args, **kwargs)

        # Pré-remplir si un objet est fourni
        if self.object:
            if isinstance(self.object, Ad):
                self.fields['object_type'].initial = 'AD'
                self.fields['object_id'].initial = self.object.id
                self.fields['amount'].initial = self.object.price
                self.fields['currency'].initial = self.object.currency
            elif isinstance(self.object, Mission):
                self.fields['object_type'].initial = 'MISSION'
                self.fields['object_id'].initial = self.object.id
                # Calculer le montant de la mission
                if hasattr(self.object, 'calculated_price'):
                    self.fields['amount'].initial = self.object.calculated_price
                self.fields['currency'].initial = 'EUR'

        # Filtrer les méthodes de paiement selon l'utilisateur
        if self.user and hasattr(self.user, 'wallet'):
            # Ajouter le portefeuille Ebi3 comme option
            payment_methods = list(PaymentTransaction.PaymentMethod.choices)
            if ('EBI3_WALLET', _('Portefeuille Ebi3')) not in payment_methods:
                payment_methods.append(('EBI3_WALLET', _('Portefeuille Ebi3')))
            self.fields['payment_method'].choices = payment_methods

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        payment_method = cleaned_data.get('payment_method')
        accept_terms = cleaned_data.get('accept_terms')

        # Validation du montant minimum selon la méthode
        min_amounts = {
            'CREDIT_CARD': Decimal('1.00'),
            'PAYPAL': Decimal('0.10'),
            'BANK_TRANSFER': Decimal('10.00'),
            'EBI3_WALLET': Decimal('0.01'),
        }

        if payment_method in min_amounts and amount < min_amounts[payment_method]:
            self.add_error('amount',
                _(f"Le montant minimum pour {self.fields['payment_method'].choices_dict[payment_method]} est de {min_amounts[payment_method]}"))

        # Vérification du portefeuille si paiement par Ebi3 Wallet
        if payment_method == 'EBI3_WALLET' and self.user:
            try:
                wallet = self.user.wallet
                if wallet.balance < amount:
                    self.add_error('payment_method',
                        _("Solde insuffisant dans votre portefeuille Ebi3."))
            except Wallet.DoesNotExist:
                self.add_error('payment_method',
                    _("Vous n'avez pas de portefeuille Ebi3. Veuillez en créer un."))

        # Validation des conditions générales
        if not accept_terms:
            self.add_error('accept_terms',
                _("Vous devez accepter les conditions générales."))

        return cleaned_data


class CreditCardPaymentForm(forms.Form):
    """Formulaire pour le paiement par carte de crédit"""

    card_number = forms.CharField(
        max_length=19,
        validators=[CardNumberValidator()],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'data-mask': '0000 0000 0000 0000'
        }),
        label=_("Numéro de carte")
    )

    card_holder = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom tel qu\'indiqué sur la carte')
        }),
        label=_("Titulaire de la carte")
    )

    expiry_month = forms.ChoiceField(
        choices=[(str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)],
        widget=forms.Select(attrs={
            'class': 'form-control expiry-month'
        }),
        label=_("Mois d'expiration")
    )

    expiry_year = forms.ChoiceField(
        choices=[(str(i), str(i)) for i in range(timezone.now().year, timezone.now().year + 11)],
        widget=forms.Select(attrs={
            'class': 'form-control expiry-year'
        }),
        label=_("Année d'expiration")
    )

    cvv = forms.CharField(
        max_length=4,
        validators=[CVVValidator()],
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '123',
            'maxlength': '4'
        }),
        label=_("Code de sécurité (CVV)")
    )

    save_card = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_("Enregistrer cette carte pour de futurs paiements")
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Définir les valeurs par défaut pour l'expiration
        now = timezone.now()
        self.fields['expiry_month'].initial = str(now.month).zfill(2)
        self.fields['expiry_year'].initial = str(now.year)

    def clean(self):
        cleaned_data = super().clean()
        expiry_month = cleaned_data.get('expiry_month')
        expiry_year = cleaned_data.get('expiry_year')

        # Valider la date d'expiration
        if expiry_month and expiry_year:
            expiry_date = timezone.datetime(
                year=int(expiry_year),
                month=int(expiry_month),
                day=1
            ).date()

            # Vérifier que la carte n'est pas expirée
            today = timezone.now().date()
            if expiry_date < today.replace(day=1):
                self.add_error('expiry_month',
                    _("La carte est expirée."))

            # Vérifier que la date n'est pas trop éloignée
            max_date = today.replace(year=today.year + 10, day=1)
            if expiry_date > max_date:
                self.add_error('expiry_year',
                    _("La date d'expiration est trop éloignée."))

        return cleaned_data


class PayPalPaymentForm(forms.Form):
    """Formulaire pour le paiement via PayPal"""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'paypal@example.com'
        }),
        label=_("Email PayPal")
    )

    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_("Se souvenir de moi")
    )


class BankTransferForm(forms.Form):
    """Formulaire pour le paiement par virement bancaire"""

    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom de votre banque')
        }),
        label=_("Nom de la banque")
    )

    account_holder = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom du titulaire du compte')
        }),
        label=_("Titulaire du compte")
    )

    iban = forms.CharField(
        max_length=34,
        validators=[IBANValidator()],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'FR76 3000 1000 0100 0000 0000 123'
        }),
        label=_("IBAN")
    )

    bic = forms.CharField(
        max_length=11,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'BNPAFRPP'
        }),
        label=_("BIC/SWIFT (optionnel)")
    )

    reference = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Référence du virement')
        }),
        label=_("Référence")
    )

    def clean_reference(self):
        reference = self.cleaned_data.get('reference')
        # S'assurer que la référence est unique
        if PaymentTransaction.objects.filter(reference=reference).exists():
            raise ValidationError(_("Cette référence existe déjà. Veuillez en choisir une autre."))
        return reference


class MobileMoneyForm(forms.Form):
    """Formulaire pour le paiement par mobile money"""

    provider = forms.ChoiceField(
        choices=[
            ('ORANGE_MONEY', 'Orange Money'),
            ('MTN_MONEY', 'MTN Money'),
            ('MOOV_MONEY', 'Moov Money'),
            ('WAVE', 'Wave'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_("Opérateur")
    )

    phone = forms.CharField(
        max_length=20,
        validators=[PhoneNumberValidator()],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+33 6 12 34 56 78'
        }),
        label=_("Numéro de téléphone")
    )

    country = forms.ChoiceField(
        choices=[
            ('FR', 'France'),
            ('SN', 'Sénégal'),
            ('CI', "Côte d'Ivoire"),
            ('CM', 'Cameroun'),
            ('MG', 'Madagascar'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_("Pays")
    )


# ============================================================================
# FORMULAIRES DE GESTION (EXISTANTS)
# ============================================================================

class PaymentMethodForm(forms.ModelForm):
    """Formulaire pour ajouter une méthode de paiement"""

    class Meta:
        model = PaymentMethod
        fields = ['method_type', 'is_default']
        widgets = {
            'method_type': forms.Select(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Limiter les types selon l'utilisateur
        if self.user and self.user.country:
            if self.user.country.code in ['FR', 'BE', 'LU']:
                self.fields['method_type'].choices = [
                    ('CARD', _('Carte bancaire')),
                    ('BANK_ACCOUNT', _('Compte bancaire')),
                ]
            elif self.user.country.code in ['SN', 'CI', 'CM']:
                self.fields['method_type'].choices = [
                    ('MOBILE_MONEY', _('Mobile Money')),
                    ('CARD', _('Carte bancaire')),
                ]

    def clean(self):
        cleaned_data = super().clean()

        # Si c'est la méthode par défaut, désactiver les autres
        if cleaned_data.get('is_default') and self.user:
            PaymentMethod.objects.filter(
                user=self.user,
                is_default=True
            ).update(is_default=False)

        return cleaned_data


class RefundRequestForm(forms.ModelForm):
    """Formulaire pour demander un remboursement"""

    class Meta:
        model = Refund
        fields = ['reason', 'description', 'evidence']
        widgets = {
            'reason': forms.Select(attrs={
                'class': 'form-control',
                'id': 'refund-reason'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Décrivez en détail pourquoi vous demandez un remboursement...')
            }),
            'evidence': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf,.doc,.docx'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.transaction = kwargs.pop('transaction', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Pré-remplir le montant maximum
        if self.transaction:
            max_refund = self.transaction.calculate_refund_amount()
            self.fields['amount'] = forms.DecimalField(
                max_digits=12,
                decimal_places=4,
                max_value=max_refund,
                min_value=Decimal('0.01'),
                initial=max_refund,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control',
                    'step': '0.01'
                }),
                label=_("Montant à rembourser")
            )

            # Afficher le montant maximum
            self.helper_text = _("Montant maximum remboursable : {} {}").format(
                max_refund, self.transaction.currency
            )

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')

        if amount and self.transaction:
            max_refund = self.transaction.calculate_refund_amount()
            if amount > max_refund:
                self.add_error('amount',
                    _(f"Le montant ne peut pas dépasser {max_refund} {self.transaction.currency}"))

        return cleaned_data


class PayoutRequestForm(forms.ModelForm):
    """Formulaire pour demander un versement"""

    class Meta:
        model = Payout
        fields = ['payout_method', 'amount']
        widgets = {
            'payout_method': forms.Select(attrs={
                'class': 'form-control',
                'id': 'payout-method'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Récupérer le portefeuille de l'utilisateur
        if self.user:
            try:
                wallet = self.user.wallet
                self.available_balance = wallet.available_balance
                self.currency = wallet.currency

                # Définir le montant maximum
                self.fields['amount'].max_value = self.available_balance
                self.fields['amount'].initial = self.available_balance

                # Ajouter l'information du solde disponible
                self.helper_text = _("Solde disponible : {} {}").format(
                    self.available_balance, self.currency
                )

                # Filtrer les méthodes de versement selon le pays
                if self.user.country:
                    if self.user.country.code in ['FR', 'BE', 'LU']:
                        self.fields['payout_method'].choices = [
                            ('BANK_TRANSFER', _('Virement bancaire')),
                            ('PAYPAL', 'PayPal'),
                            ('EBI3_WALLET', _('Portefeuille Ebi3')),
                        ]
                    elif self.user.country.code in ['SN', 'CI']:
                        self.fields['payout_method'].choices = [
                            ('WESTERN_UNION', 'Western Union'),
                            ('EBI3_WALLET', _('Portefeuille Ebi3')),
                        ]

            except Wallet.DoesNotExist:
                self.available_balance = Decimal('0')
                self.currency = 'EUR'

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')

        if amount and hasattr(self, 'available_balance'):
            if amount > self.available_balance:
                self.add_error('amount',
                    _(f"Le montant ne peut pas dépasser votre solde disponible de {self.available_balance} {self.currency}"))

            # Vérifier le montant minimum selon la méthode
            payout_method = cleaned_data.get('payout_method')
            min_amounts = {
                'BANK_TRANSFER': Decimal('10.00'),
                'PAYPAL': Decimal('1.00'),
                'WESTERN_UNION': Decimal('50.00'),
                'EBI3_WALLET': Decimal('0.01'),
            }

            if payout_method in min_amounts and amount < min_amounts[payout_method]:
                self.add_error('amount',
                    _(f"Le montant minimum pour ce type de versement est de {min_amounts[payout_method]} {self.currency}"))

        return cleaned_data


class WalletRechargeForm(forms.Form):
    """Formulaire pour recharger un portefeuille"""
    # Alias pour WalletTopUpForm pour compatibilité avec views.py

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal('1.00'),
        max_value=Decimal('10000.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '50.00'
        }),
        label=_("Montant de recharge")
    )

    currency = forms.ChoiceField(
        choices=[
            ('EUR', '€ EUR'),
            ('USD', '$ USD'),
            ('MAD', 'DH MAD'),
            ('XOF', 'CFA XOF'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label=_("Devise")
    )

    payment_method = forms.ChoiceField(
        choices=[
            ('CREDIT_CARD', _('Carte de crédit')),
            ('PAYPAL', 'PayPal'),
            ('BANK_TRANSFER', _('Virement bancaire')),
            ('MOBILE_MONEY', _('Mobile Money')),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'topup-method-radio'
        }),
        label=_("Méthode de paiement")
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and hasattr(self.user, 'wallet'):
            # Définir la devise par défaut selon le portefeuille
            self.fields['currency'].initial = self.user.wallet.currency

            # Limiter le montant maximum selon le pays
            if self.user.country:
                country_limits = {
                    'FR': Decimal('5000.00'),
                    'MA': Decimal('10000.00'),
                    'SN': Decimal('1000.00'),
                    'CI': Decimal('1000.00'),
                }
                limit = country_limits.get(self.user.country.code, Decimal('5000.00'))
                self.fields['amount'].max_value = limit

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')

        # Vérifier les limites selon la méthode
        payment_method = cleaned_data.get('payment_method')
        if payment_method == 'MOBILE_MONEY' and amount > Decimal('500.00'):
            self.add_error('amount',
                _("Le montant maximum pour Mobile Money est de 500.00"))

        return cleaned_data


# Alias pour compatibilité
WalletTopUpForm = WalletRechargeForm


class WalletWithdrawalForm(forms.Form):
    """Formulaire pour retirer des fonds d'un portefeuille"""
    # Alias pour PayoutRequestForm pour compatibilité avec views.py

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'id': 'transfer-amount'
        }),
        label=_("Montant")
    )

    payment_method = forms.ChoiceField(
        choices=[
            ('BANK_TRANSFER', _('Virement bancaire')),
            ('PAYPAL', 'PayPal'),
            ('WESTERN_UNION', 'Western Union'),
            ('EBI3_WALLET', _('Portefeuille Ebi3')),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'payout-method'
        }),
        label=_("Méthode de retrait")
    )

    account_details = forms.JSONField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("Détails du compte")
    )

    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Notes optionnelles...')
        }),
        label=_("Notes")
    )

    def __init__(self, *args, **kwargs):
        self.wallet = kwargs.pop('wallet', None)
        super().__init__(*args, **kwargs)

        if self.wallet:
            # Définir le montant maximum
            self.fields['amount'].max_value = self.wallet.available_balance

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')

        if amount and self.wallet:
            if amount > self.wallet.available_balance:
                self.add_error('amount',
                    _("Le montant ne peut pas dépasser votre solde disponible."))

        return cleaned_data


class WalletTransferForm(forms.Form):
    """Formulaire pour transférer des fonds entre portefeuilles"""

    recipient = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Nom d'utilisateur ou email"),
            'id': 'recipient-search'
        }),
        label=_("Destinataire")
    )

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'id': 'transfer-amount'
        }),
        label=_("Montant")
    )

    message = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Message optionnel...")
        }),
        label=_("Message")
    )

    def __init__(self, *args, **kwargs):
        self.sender = kwargs.pop('sender', None)
        super().__init__(*args, **kwargs)

        if self.sender and hasattr(self.sender, 'wallet'):
            # Définir le montant maximum
            self.fields['amount'].max_value = self.sender.wallet.available_balance

            # Ajouter l'information du solde
            self.helper_text = _("Solde disponible : {} {}").format(
                self.sender.wallet.available_balance,
                self.sender.wallet.currency
            )

    def clean(self):
        cleaned_data = super().clean()
        recipient = cleaned_data.get('recipient')
        amount = cleaned_data.get('amount')

        # Rechercher le destinataire
        if recipient:
            try:
                # Chercher par email ou username
                if '@' in recipient:
                    recipient_user = User.objects.get(email=recipient)
                else:
                    recipient_user = User.objects.get(username=recipient)

                cleaned_data['recipient_user'] = recipient_user

                # Vérifier que le destinataire a un portefeuille
                if not hasattr(recipient_user, 'wallet'):
                    self.add_error('recipient',
                        _("Le destinataire n'a pas de portefeuille Ebi3."))

                # Vérifier qu'on ne se transfère pas à soi-même
                if recipient_user == self.sender:
                    self.add_error('recipient',
                        _("Vous ne pouvez pas vous transférer des fonds à vous-même."))

            except User.DoesNotExist:
                self.add_error('recipient',
                    _("Utilisateur non trouvé. Veuillez vérifier le nom d'utilisateur ou l'email."))

        # Vérifier le solde de l'expéditeur
        if amount and self.sender and hasattr(self.sender, 'wallet'):
            if amount > self.sender.wallet.available_balance:
                self.add_error('amount',
                    _("Solde insuffisant."))

            # Vérifier les limites de transfert
            daily_transfers = WalletTransaction.objects.filter(
                wallet=self.sender.wallet,
                transaction_type='TRANSFER',
                created_at__date=timezone.now().date()
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            if daily_transfers + amount > Decimal('1000.00'):
                self.add_error('amount',
                    _("Vous avez atteint votre limite de transfert quotidienne (1000 €)."))

        return cleaned_data


# ============================================================================
# FORMULAIRES D'ADMINISTRATION (EXISTANTS)
# ============================================================================

class TransactionSearchForm(forms.Form):
    """Formulaire de recherche de transactions"""

    STATUS_CHOICES = [('', _('Tous'))] + list(PaymentTransaction.Status.choices)
    PAYMENT_TYPE_CHOICES = [('', _('Tous'))] + list(PaymentTransaction.PaymentType.choices)

    reference = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Référence...')
        }),
        label=_("Référence")
    )

    payer = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom d\'utilisateur ou email...')
        }),
        label=_("Payeur")
    )

    payee = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Nom d\'utilisateur ou email...')
        }),
        label=_("Bénéficiaire")
    )

    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_("Statut")
    )

    payment_type = forms.ChoiceField(
        required=False,
        choices=PAYMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_("Type de paiement")
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label=_("Du")
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label=_("Au")
    )

    min_amount = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': _('Montant minimum')
        }),
        label=_("Montant minimum")
    )

    max_amount = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': _('Montant maximum')
        }),
        label=_("Montant maximum")
    )

    currency = forms.ChoiceField(
        required=False,
        choices=[('', _('Toutes'))] + [
            ('EUR', '€ EUR'),
            ('USD', '$ USD'),
            ('MAD', 'DH MAD'),
            ('XOF', 'CFA XOF'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_("Devise")
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')

        # Validation des dates
        if date_from and date_to and date_from > date_to:
            self.add_error('date_to',
                _("La date 'Au' doit être postérieure à la date 'Du'."))

        # Validation des montants
        if min_amount and max_amount and min_amount > max_amount:
            self.add_error('max_amount',
                _("Le montant maximum doit être supérieur au montant minimum."))

        return cleaned_data


class RefundReviewForm(forms.ModelForm):
    """Formulaire pour examiner une demande de remboursement"""

    class Meta:
        model = Refund
        fields = ['status', 'review_notes', 'rejection_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control',
                'id': 'refund-status'
            }),
            'review_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Notes internes...')
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Raison du rejet (si applicable)...')
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Limiter les statuts possibles selon le statut actuel
        if self.instance.status == Refund.Status.REQUESTED:
            self.fields['status'].choices = [
                ('UNDER_REVIEW', _('En revue')),
                ('APPROVED', _('Approuvé')),
                ('REJECTED', _('Rejeté')),
            ]
        elif self.instance.status == Refund.Status.UNDER_REVIEW:
            self.fields['status'].choices = [
                ('APPROVED', _('Approuvé')),
                ('REJECTED', _('Rejeté')),
            ]

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')

        # Si le remboursement est rejeté, une raison est requise
        if status == Refund.Status.REJECTED and not rejection_reason:
            self.add_error('rejection_reason',
                _("Une raison de rejet est requise."))

        return cleaned_data


class PayoutProcessForm(forms.ModelForm):
    """Formulaire pour traiter un versement"""

    class Meta:
        model = Payout
        fields = ['status', 'payout_gateway_id']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payout_gateway_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('ID de la passerelle de paiement')
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Limiter les statuts possibles
        if self.instance.status == Payout.Status.PENDING:
            self.fields['status'].choices = [
                ('PROCESSING', _('En traitement')),
                ('CANCELLED', _('Annulé')),
            ]
        elif self.instance.status == Payout.Status.PROCESSING:
            self.fields['status'].choices = [
                ('COMPLETED', _('Complété')),
                ('FAILED', _('Échoué')),
            ]

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        payout_gateway_id = cleaned_data.get('payout_gateway_id')

        # Si le versement est complété, un ID de passerelle est requis
        if status == Payout.Status.COMPLETED and not payout_gateway_id:
            self.add_error('payout_gateway_id',
                _("L'ID de la passerelle est requis pour les versements complétés."))

        return cleaned_data


# ============================================================================
# FORMULAIRES DE CONFIGURATION (EXISTANTS)
# ============================================================================

class TaxConfigurationForm(forms.ModelForm):
    """Formulaire pour configurer les taxes"""

    class Meta:
        model = Tax
        fields = ['country', 'tax_rate', 'tax_name', 'is_active',
                 'exempt_categories', 'minimum_amount']
        widgets = {
            'country': forms.Select(attrs={'class': 'form-control'}),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'tax_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'minimum_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }


class ExchangeRateForm(forms.ModelForm):
    """Formulaire pour configurer les taux de change"""

    class Meta:
        model = ExchangeRate
        fields = ['base_currency', 'target_currency', 'rate', 'source', 'is_active']
        widgets = {
            'base_currency': forms.Select(attrs={'class': 'form-control'}),
            'target_currency': forms.Select(attrs={'class': 'form-control'}),
            'rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001'
            }),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        base_currency = cleaned_data.get('base_currency')
        target_currency = cleaned_data.get('target_currency')

        # Empêcher le même code de devise pour base et target
        if base_currency == target_currency:
            self.add_error('target_currency',
                _("La devise cible ne peut pas être identique à la devise de base."))

        return cleaned_data


class CommissionConfigurationForm(forms.Form):
    """Formulaire pour configurer les commissions"""

    ad_purchase_commission = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('0.5'),
        initial=Decimal('0.10'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.0001'
        }),
        label=_("Commission achat annonce (ex: 0.10 pour 10%)")
    )

    mission_payment_commission = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('0.2'),
        initial=Decimal('0.05'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.0001'
        }),
        label=_("Commission paiement mission")
    )

    wallet_transfer_commission = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal('0'),
        max_value=Decimal('0.05'),
        initial=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.0001'
        }),
        label=_("Commission transfert portefeuille")
    )

    minimum_payout_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('1'),
        initial=Decimal('50'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label=_("Montant minimum versement (€)")
    )

    def clean(self):
        cleaned_data = super().clean()

        # Validation des taux de commission
        for field in ['ad_purchase_commission', 'mission_payment_commission', 'wallet_transfer_commission']:
            value = cleaned_data.get(field)
            if value and value > Decimal('0.5'):  # 50% max
                self.add_error(field,
                    _("La commission ne peut pas dépasser 50%."))

        return cleaned_data


# ============================================================================
# FORMULAIRES SPÉCIAUX POUR L'INTÉGRATION (EXISTANTS)
# ============================================================================

class AdPaymentForm(forms.Form):
    """Formulaire spécial pour le paiement d'une annonce"""

    ad = forms.ModelChoiceField(
        queryset=Ad.objects.filter(status=Ad.Status.ACTIVE),
        widget=forms.HiddenInput()
    )

    payment_type = forms.ChoiceField(
        choices=[
            ('AD_PURCHASE', _('Achat de l\'annonce')),
            ('AD_FEATURED', _('Mise en vedette (7 jours)')),
            ('AD_RESERVATION', _('Réservation de l\'annonce')),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'ad-payment-type'
        }),
        label=_("Type de paiement")
    )

    featured_duration = forms.ChoiceField(
        required=False,
        choices=[
            (7, _('7 jours - 10€')),
            (14, _('14 jours - 18€')),
            (30, _('30 jours - 30€')),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'featured-duration'
        }),
        label=_("Durée de mise en vedette")
    )

    def __init__(self, *args, **kwargs):
        self.ad = kwargs.pop('ad', None)
        super().__init__(*args, **kwargs)

        if self.ad:
            self.fields['ad'].initial = self.ad
            self.fields['ad'].queryset = Ad.objects.filter(id=self.ad.id)

            # Si l'annonce est déjà en vedette, masquer l'option
            if self.ad.is_featured:
                self.fields['payment_type'].choices = [
                    ('AD_PURCHASE', _('Achat de l\'annonce')),
                    ('AD_RESERVATION', _('Réservation de l\'annonce')),
                ]

    def clean(self):
        cleaned_data = super().clean()
        payment_type = cleaned_data.get('payment_type')
        featured_duration = cleaned_data.get('featured_duration')

        if payment_type == 'AD_FEATURED' and not featured_duration:
            self.add_error('featured_duration',
                _("Veuillez sélectionner une durée pour la mise en vedette."))

        return cleaned_data


class MissionPaymentForm(forms.Form):
    """Formulaire spécial pour le paiement d'une mission"""

    mission = forms.ModelChoiceField(
        queryset=Mission.objects.filter(status__in=['PENDING_PAYMENT', 'CONFIRMED']),
        widget=forms.HiddenInput()
    )

    insurance_required = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'insurance-required'
        }),
        label=_("Ajouter une assurance transport")
    )

    insurance_amount = forms.DecimalField(
        required=False,
        min_value=Decimal('0'),
        max_value=Decimal('10000'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'id': 'insurance-amount',
            'readonly': 'readonly'
        }),
        label=_("Montant assuré")
    )

    def __init__(self, *args, **kwargs):
        self.mission = kwargs.pop('mission', None)
        super().__init__(*args, **kwargs)

        if self.mission:
            self.fields['mission'].initial = self.mission
            self.fields['mission'].queryset = Mission.objects.filter(id=self.mission.id)

            # Calculer le montant de l'assurance (1% de la valeur)
            if hasattr(self.mission, 'calculated_price'):
                insurance_amount = self.mission.calculated_price * Decimal('0.01')
                self.fields['insurance_amount'].initial = insurance_amount

    def clean(self):
        cleaned_data = super().clean()
        insurance_required = cleaned_data.get('insurance_required')
        insurance_amount = cleaned_data.get('insurance_amount')

        if insurance_required and not insurance_amount:
            self.add_error('insurance_amount',
                _("Veuillez spécifier un montant d'assurance."))

        if insurance_amount and insurance_amount > Decimal('10000'):
            self.add_error('insurance_amount',
                _("Le montant d'assurance ne peut pas dépasser 10 000 €."))

        return cleaned_data


# ============================================================================
# FORMULAIRES DE RAPPORT (EXISTANTS)
# ============================================================================

class FinancialReportForm(forms.Form):
    """Formulaire pour générer des rapports financiers"""

    REPORT_TYPES = [
        ('DAILY', _('Journalier')),
        ('WEEKLY', _('Hebdomadaire')),
        ('MONTHLY', _('Mensuel')),
        ('QUARTERLY', _('Trimestriel')),
        ('YEARLY', _('Annuel')),
        ('CUSTOM', _('Personnalisé')),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'report-type'
        }),
        label=_("Type de rapport")
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'start-date'
        }),
        label=_("Date de début")
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'end-date'
        }),
        label=_("Date de fin")
    )

    currency = forms.ChoiceField(
        required=False,
        choices=[('', _('Toutes'))] + [
            ('EUR', '€ EUR'),
            ('USD', '$ USD'),
            ('MAD', 'DH MAD'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_("Devise")
    )

    payment_type = forms.ChoiceField(
        required=False,
        choices=[('', _('Tous'))] + list(PaymentTransaction.PaymentType.choices),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_("Type de paiement")
    )

    include_details = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Inclure les détails des transactions")
    )

    def clean(self):
        cleaned_data = super().clean()
        report_type = cleaned_data.get('report_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if report_type == 'CUSTOM':
            if not start_date:
                self.add_error('start_date',
                    _("La date de début est requise pour un rapport personnalisé."))
            if not end_date:
                self.add_error('end_date',
                    _("La date de fin est requise pour un rapport personnalisé."))
            if start_date and end_date and start_date > end_date:
                self.add_error('end_date',
                    _("La date de fin doit être postérieure à la date de début."))

        return cleaned_data


# ============================================================================
# FORMULAIRES DE NOTIFICATION (EXISTANTS)
# ============================================================================

class PaymentNotificationForm(forms.Form):
    """Formulaire pour configurer les notifications de paiement"""

    email_payment_received = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Email lors de la réception d'un paiement")
    )

    email_payment_sent = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Email lors de l'envoi d'un paiement")
    )

    email_refund_processed = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Email lors du traitement d'un remboursement")
    )

    email_payout_completed = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Email lors de la complétion d'un versement")
    )

    push_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Notifications push")
    )

    low_balance_alert = forms.DecimalField(
        required=False,
        min_value=Decimal('0'),
        max_value=Decimal('1000'),
        initial=Decimal('10'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label=_("Alerte solde bas (€)")
    )


# ============================================================================
# FORMULAIRES FACTICES POUR COMPATIBILITÉ (NÉCESSAIRES POUR VIEWS.PY)
# ============================================================================

# Ces classes sont définies dans views.py mais référencées dans les imports
# Nous les définissons ici comme des alias pour éviter les erreurs d'import

# CardPaymentForm est un alias de CreditCardPaymentForm (déjà défini)
CardPaymentForm = CreditCardPaymentForm

# MobileMoneyPaymentForm est un alias de MobileMoneyForm (déjà défini)
MobileMoneyPaymentForm = MobileMoneyForm

# TaxForm est un alias de TaxConfigurationForm (déjà défini)
TaxForm = TaxConfigurationForm

# CommissionForm est un alias de CommissionConfigurationForm (déjà défini)
CommissionForm = CommissionConfigurationForm

# PaymentReportForm est un alias de FinancialReportForm (déjà défini)
PaymentReportForm = FinancialReportForm

# TransactionFilterForm est un alias de TransactionSearchForm (déjà défini)
TransactionFilterForm = TransactionSearchForm


# ============================================================================
# FORMSETS (AJOUTÉS POUR COMPATIBILITÉ)
# ============================================================================

# Formset pour InvoiceItem (si nécessaire dans les vues)
InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    fields=['description', 'quantity', 'unit_price', 'tax_rate'],
    extra=1,
    can_delete=True,
    widgets={
        'description': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Description de l\'article')
        }),
        'quantity': forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01'
        }),
        'unit_price': forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        'tax_rate': forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'max': '100'
        }),
    }
)
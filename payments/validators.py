# ~/ebi3/payments/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import re

def validate_credit_card_number(value):
    """
    Valider un numéro de carte de crédit avec l'algorithme de Luhn
    """
    # Supprimer les espaces et tirets
    value = re.sub(r'[\s-]', '', value)

    if not value.isdigit():
        raise ValidationError(_('Le numéro de carte ne doit contenir que des chiffres.'))

    if len(value) < 13 or len(value) > 19:
        raise ValidationError(_('Le numéro de carte doit avoir entre 13 et 19 chiffres.'))

    # Algorithme de Luhn
    def luhn_checksum(card_number):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10

    if luhn_checksum(value) != 0:
        raise ValidationError(_('Numéro de carte de crédit invalide.'))

    return value

def validate_expiry_date(value):
    """
    Valider une date d'expiration de carte (format MM/YY)
    """
    if not re.match(r'^(0[1-9]|1[0-2])/\d{2}$', value):
        raise ValidationError(_('Format invalide. Utilisez MM/YY.'))

    month, year = map(int, value.split('/'))
    current_year = timezone.now().year % 100
    current_month = timezone.now().month

    if year < current_year or (year == current_year and month < current_month):
        raise ValidationError(_('La carte a expiré.'))

    if year > current_year + 20:
        raise ValidationError(_('Date d\'expiration invalide.'))

    return value

def validate_cvv(value):
    """
    Valider un code CVV
    """
    if not value.isdigit():
        raise ValidationError(_('Le CVV doit contenir uniquement des chiffres.'))

    if len(value) not in [3, 4]:
        raise ValidationError(_('Le CVV doit avoir 3 ou 4 chiffres.'))

    return value

def validate_iban(value):
    """
    Valider un numéro IBAN
    """
    # Supprimer les espaces
    value = value.replace(' ', '').upper()

    if len(value) < 15 or len(value) > 34:
        raise ValidationError(_('IBAN invalide: longueur incorrecte.'))

    # Vérifier le format de base
    if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$', value):
        raise ValidationError(_('Format IBAN invalide.'))

    # Déplacer les 4 premiers caractères à la fin
    rearranged = value[4:] + value[:4]

    # Convertir les lettres en nombres (A=10, B=11, etc.)
    def convert_to_numbers(s):
        return ''.join(str(ord(c) - 55) if c.isalpha() else c for c in s)

    converted = convert_to_numbers(rearranged)

    # Vérifier avec modulo 97
    if int(converted) % 97 != 1:
        raise ValidationError(_('IBAN invalide: vérification échouée.'))

    return value

def validate_bic(value):
    """
    Valider un code BIC/SWIFT
    """
    value = value.upper().replace(' ', '')

    # Format BIC: 8 ou 11 caractères
    if not re.match(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$', value):
        raise ValidationError(_('Format BIC/SWIFT invalide.'))

    return value

def validate_amount(value):
    """
    Valider un montant monétaire
    """
    if value <= 0:
        raise ValidationError(_('Le montant doit être supérieur à zéro.'))

    if value > 1000000:  # 1 million
        raise ValidationError(_('Le montant est trop élevé.'))

    # Vérifier les décimales
    str_value = str(value)
    if '.' in str_value:
        decimal_part = str_value.split('.')[1]
        if len(decimal_part) > 2:
            raise ValidationError(_('Maximum 2 décimales autorisées.'))

    return value

def validate_currency(value):
    """
    Valider un code de devise
    """
    valid_currencies = ['EUR', 'USD', 'GBP', 'MAD', 'XOF', 'CAD', 'AUD', 'JPY', 'CHF']

    if value not in valid_currencies:
        raise ValidationError(_('Devise non supportée.'))

    return value

def validate_transaction_id(value):
    """
    Valider un ID de transaction
    """
    if not re.match(r'^TXN[A-Z0-9]{12}$', value):
        raise ValidationError(_('Format d\'ID de transaction invalide.'))

    return value

def validate_invoice_number(value):
    """
    Valider un numéro de facture
    """
    if not re.match(r'^INV-\d{6}$', value):
        raise ValidationError(_('Format de numéro de facture invalide. Doit être INV-XXXXXX.'))

    return value

def validate_coupon_code(value):
    """
    Valider un code de coupon
    """
    if len(value) < 4 or len(value) > 20:
        raise ValidationError(_('Le code coupon doit avoir entre 4 et 20 caractères.'))

    if not re.match(r'^[A-Z0-9-_]+$', value):
        raise ValidationError(_('Le code coupon ne peut contenir que des lettres majuscules, chiffres, tirets et underscores.'))

    return value.upper()

def validate_tax_rate(value):
    """
    Valider un taux de taxe
    """
    if value < 0 or value > 100:
        raise ValidationError(_('Le taux de taxe doit être entre 0 et 100.'))

    return value

def validate_discount_value(value, discount_type):
    """
    Valider une valeur de réduction selon son type
    """
    if discount_type == 'PERCENTAGE':
        if value < 0 or value > 100:
            raise ValidationError(_('La réduction en pourcentage doit être entre 0 et 100.'))
    elif discount_type == 'FIXED_AMOUNT':
        if value <= 0:
            raise ValidationError(_('La réduction fixe doit être supérieure à zéro.'))

    return value

def validate_payment_method(value):
    """
    Valider une méthode de paiement
    """
    valid_methods = ['CREDIT_CARD', 'DEBIT_CARD', 'PAYPAL', 'BANK_TRANSFER',
                     'STRIPE', 'CASH', 'MOBILE_MONEY', 'CRYPTO']

    if value not in valid_methods:
        raise ValidationError(_('Méthode de paiement non supportée.'))

    return value

def validate_card_holder_name(value):
    """
    Valider un nom de titulaire de carte
    """
    if len(value) < 2 or len(value) > 50:
        raise ValidationError(_('Le nom doit avoir entre 2 et 50 caractères.'))

    if not re.match(r'^[a-zA-Z\s\'-]+$', value):
        raise ValidationError(_('Le nom ne peut contenir que des lettres, espaces, apostrophes et tirets.'))

    return value.title()

def validate_phone_number_for_payment(value):
    """
    Valider un numéro de téléphone pour le paiement mobile
    """
    # Format international simple
    if not re.match(r'^\+[1-9]\d{1,14}$', value):
        raise ValidationError(_('Format de numéro de téléphone invalide. Utilisez le format international: +33123456789'))

    return value

def validate_wallet_address(value, cryptocurrency):
    """
    Valider une adresse de portefeuille crypto
    """
    crypto_patterns = {
        'BTC': r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[ac-hj-np-z02-9]{11,71}$',
        'ETH': r'^0x[a-fA-F0-9]{40}$',
        'LTC': r'^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$',
        'XRP': r'^r[0-9a-zA-Z]{24,34}$',
        'BCH': r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bitcoincash:q[0-9a-z]{41}$',
    }

    if cryptocurrency not in crypto_patterns:
        raise ValidationError(_('Cryptomonnaie non supportée.'))

    pattern = crypto_patterns[cryptocurrency]
    if not re.match(pattern, value):
        raise ValidationError(_('Adresse de portefeuille invalide pour cette cryptomonnaie.'))

    return value

def validate_bank_account_number(value, country_code='FR'):
    """
    Valider un numéro de compte bancaire selon le pays
    """
    value = value.replace(' ', '').replace('-', '')

    # Validation pour la France (RIB)
    if country_code == 'FR':
        if len(value) != 23:
            raise ValidationError(_('Le RIB français doit avoir 23 chiffres.'))

        if not value.isdigit():
            raise ValidationError(_('Le RIB ne doit contenir que des chiffres.'))

        # Vérifier la clé RIB
        bank_code = value[0:5]
        branch_code = value[5:10]
        account_number = value[10:21]
        key = value[21:23]

        # Calcul de la clé RIB
        def calculate_rib_key(bank, branch, account):
            # Convertir en entier et calculer
            import math
            total = 89 * int(bank) + 15 * int(branch) + 3 * int(account)
            return str(97 - (total % 97)).zfill(2)

        calculated_key = calculate_rib_key(bank_code, branch_code, account_number)
        if calculated_key != key:
            raise ValidationError(_('Clé RIB invalide.'))

    # Ajouter d'autres validations par pays si nécessaire

    return value

def validate_file_size(file, max_size_mb=5):
    """
    Valider la taille d'un fichier
    """
    max_size = max_size_mb * 1024 * 1024  # Convertir en bytes

    if file.size > max_size:
        raise ValidationError(_(f'La taille du fichier ne doit pas dépasser {max_size_mb}MB.'))

    return file

def validate_file_type(file, allowed_types=None):
    """
    Valider le type d'un fichier
    """
    if allowed_types is None:
        allowed_types = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']

    ext = file.name.split('.')[-1].lower()

    if ext not in allowed_types:
        raise ValidationError(_(f'Type de fichier non autorisé. Types autorisés: {", ".join(allowed_types)}'))

    return file

def validate_json_schema(value, schema_name='transaction_metadata'):
    """
    Valider un JSON selon un schéma
    """
    import json

    try:
        data = json.loads(value) if isinstance(value, str) else value

        # Schémas de validation
        schemas = {
            'transaction_metadata': {
                'required': ['transaction_type', 'items'],
                'properties': {
                    'transaction_type': {'type': 'string'},
                    'items': {'type': 'array'},
                    'shipping_address': {'type': 'object', 'optional': True},
                    'billing_address': {'type': 'object', 'optional': True}
                }
            },
            'invoice_data': {
                'required': ['invoice_number', 'date', 'client'],
                'properties': {
                    'invoice_number': {'type': 'string'},
                    'date': {'type': 'string'},
                    'client': {'type': 'object'}
                }
            }
        }

        if schema_name not in schemas:
            return value

        schema = schemas[schema_name]

        # Validation simple
        for required_field in schema['required']:
            if required_field not in data:
                raise ValidationError(_(f'Champ requis manquant: {required_field}'))

        return value

    except json.JSONDecodeError:
        raise ValidationError(_('JSON invalide.'))
# ~/ebi3/payments/constants.py
"""
Constantes pour l'application payments
"""

from django.utils.translation import gettext_lazy as _

# ============================================================================
# STATUTS DES TRANSACTIONS
# ============================================================================

TRANSACTION_STATUS = {
    'PENDING': _('En attente'),
    'PROCESSING': _('En traitement'),
    'COMPLETED': _('Complétée'),
    'FAILED': _('Échouée'),
    'CANCELED': _('Annulée'),
    'REFUNDED': _('Remboursée'),
    'PARTIALLY_REFUNDED': _('Partiellement remboursée'),
    'EXPIRED': _('Expirée'),
    'REVERSED': _('Annulée (reversée)'),
    'CHARGEBACK': _('Contestée'),
}

TRANSACTION_STATUS_CHOICES = [
    ('PENDING', TRANSACTION_STATUS['PENDING']),
    ('PROCESSING', TRANSACTION_STATUS['PROCESSING']),
    ('COMPLETED', TRANSACTION_STATUS['COMPLETED']),
    ('FAILED', TRANSACTION_STATUS['FAILED']),
    ('CANCELED', TRANSACTION_STATUS['CANCELED']),
    ('REFUNDED', TRANSACTION_STATUS['REFUNDED']),
    ('PARTIALLY_REFUNDED', TRANSACTION_STATUS['PARTIALLY_REFUNDED']),
    ('EXPIRED', TRANSACTION_STATUS['EXPIRED']),
    ('REVERSED', TRANSACTION_STATUS['REVERSED']),
    ('CHARGEBACK', TRANSACTION_STATUS['CHARGEBACK']),
]

# ============================================================================
# MÉTHODES DE PAIEMENT
# ============================================================================

PAYMENT_METHODS = {
    'CREDIT_CARD': _('Carte de crédit'),
    'DEBIT_CARD': _('Carte de débit'),
    'PAYPAL': _('PayPal'),
    'BANK_TRANSFER': _('Virement bancaire'),
    'STRIPE': _('Stripe'),
    'CASH': _('Espèces'),
    'MOBILE_MONEY': _('Mobile Money'),
    'CRYPTO': _('Cryptomonnaie'),
    'APPLE_PAY': _('Apple Pay'),
    'GOOGLE_PAY': _('Google Pay'),
}

PAYMENT_METHOD_CHOICES = [
    ('CREDIT_CARD', PAYMENT_METHODS['CREDIT_CARD']),
    ('DEBIT_CARD', PAYMENT_METHODS['DEBIT_CARD']),
    ('PAYPAL', PAYMENT_METHODS['PAYPAL']),
    ('BANK_TRANSFER', PAYMENT_METHODS['BANK_TRANSFER']),
    ('STRIPE', PAYMENT_METHODS['STRIPE']),
    ('CASH', PAYMENT_METHODS['CASH']),
    ('MOBILE_MONEY', PAYMENT_METHODS['MOBILE_MONEY']),
    ('CRYPTO', PAYMENT_METHODS['CRYPTO']),
    ('APPLE_PAY', PAYMENT_METHODS['APPLE_PAY']),
    ('GOOGLE_PAY', PAYMENT_METHODS['GOOGLE_PAY']),
]

# ============================================================================
# BUTS DES TRANSACTIONS
# ============================================================================

TRANSACTION_PURPOSES = {
    'AD_PROMOTION': _('Promotion d\'annonce'),
    'FEATURED_AD': _('Annonce en vedette'),
    'ADDITIONAL_IMAGES': _('Images supplémentaires'),
    'VIDEO_UPLOAD': _('Téléchargement de vidéo'),
    'MEMBERSHIP': _('Adhésion'),
    'SUBSCRIPTION': _('Abonnement'),
    'PRODUCT_PURCHASE': _('Achat de produit'),
    'SERVICE_PAYMENT': _('Paiement de service'),
    'DONATION': _('Don'),
    'DEPOSIT': _('Dépôt'),
    'WITHDRAWAL': _('Retrait'),
    'REFUND': _('Remboursement'),
    'COMMISSION': _('Commission'),
    'TAX': _('Taxe'),
    'SHIPPING': _('Livraison'),
    'INSURANCE': _('Assurance'),
    'OTHER': _('Autre'),
}

TRANSACTION_PURPOSE_CHOICES = [
    ('AD_PROMOTION', TRANSACTION_PURPOSES['AD_PROMOTION']),
    ('FEATURED_AD', TRANSACTION_PURPOSES['FEATURED_AD']),
    ('ADDITIONAL_IMAGES', TRANSACTION_PURPOSES['ADDITIONAL_IMAGES']),
    ('VIDEO_UPLOAD', TRANSACTION_PURPOSES['VIDEO_UPLOAD']),
    ('MEMBERSHIP', TRANSACTION_PURPOSES['MEMBERSHIP']),
    ('SUBSCRIPTION', TRANSACTION_PURPOSES['SUBSCRIPTION']),
    ('PRODUCT_PURCHASE', TRANSACTION_PURPOSES['PRODUCT_PURCHASE']),
    ('SERVICE_PAYMENT', TRANSACTION_PURPOSES['SERVICE_PAYMENT']),
    ('DONATION', TRANSACTION_PURPOSES['DONATION']),
    ('DEPOSIT', TRANSACTION_PURPOSES['DEPOSIT']),
    ('WITHDRAWAL', TRANSACTION_PURPOSES['WITHDRAWAL']),
    ('REFUND', TRANSACTION_PURPOSES['REFUND']),
    ('COMMISSION', TRANSACTION_PURPOSES['COMMISSION']),
    ('TAX', TRANSACTION_PURPOSES['TAX']),
    ('SHIPPING', TRANSACTION_PURPOSES['SHIPPING']),
    ('INSURANCE', TRANSACTION_PURPOSES['INSURANCE']),
    ('OTHER', TRANSACTION_PURPOSES['OTHER']),
]

# ============================================================================
# STATUTS DES FACTURES
# ============================================================================

INVOICE_STATUS = {
    'DRAFT': _('Brouillon'),
    'SENT': _('Envoyée'),
    'PAID': _('Payée'),
    'OVERDUE': _('En retard'),
    'CANCELED': _('Annulée'),
    'REFUNDED': _('Remboursée'),
}

INVOICE_STATUS_CHOICES = [
    ('DRAFT', INVOICE_STATUS['DRAFT']),
    ('SENT', INVOICE_STATUS['SENT']),
    ('PAID', INVOICE_STATUS['PAID']),
    ('OVERDUE', INVOICE_STATUS['OVERDUE']),
    ('CANCELED', INVOICE_STATUS['CANCELED']),
    ('REFUNDED', INVOICE_STATUS['REFUNDED']),
]

# ============================================================================
# STATUTS DES REMBOURSEMENTS
# ============================================================================

REFUND_STATUS = {
    'PENDING': _('En attente'),
    'PROCESSING': _('En traitement'),
    'COMPLETED': _('Complété'),
    'FAILED': _('Échoué'),
    'CANCELED': _('Annulé'),
}

REFUND_STATUS_CHOICES = [
    ('PENDING', REFUND_STATUS['PENDING']),
    ('PROCESSING', REFUND_STATUS['PROCESSING']),
    ('COMPLETED', REFUND_STATUS['COMPLETED']),
    ('FAILED', REFUND_STATUS['FAILED']),
    ('CANCELED', REFUND_STATUS['CANCELED']),
]

REFUND_REASONS = {
    'DUPLICATE_CHARGE': _('Double facturation'),
    'FRAUDULENT_CHARGE': _('Facturation frauduleuse'),
    'CANCELLED_ORDER': _('Commande annulée'),
    'DEFECTIVE_PRODUCT': _('Produit défectueux'),
    'NOT_AS_DESCRIBED': _('Non conforme à la description'),
    'DISSATISFIED_SERVICE': _('Service non satisfaisant'),
    'OTHER': _('Autre'),
}

REFUND_REASON_CHOICES = [
    ('DUPLICATE_CHARGE', REFUND_REASONS['DUPLICATE_CHARGE']),
    ('FRAUDULENT_CHARGE', REFUND_REASONS['FRAUDULENT_CHARGE']),
    ('CANCELLED_ORDER', REFUND_REASONS['CANCELLED_ORDER']),
    ('DEFECTIVE_PRODUCT', REFUND_REASONS['DEFECTIVE_PRODUCT']),
    ('NOT_AS_DESCRIBED', REFUND_REASONS['NOT_AS_DESCRIBED']),
    ('DISSATISFIED_SERVICE', REFUND_REASONS['DISSATISFIED_SERVICE']),
    ('OTHER', REFUND_REASONS['OTHER']),
]

# ============================================================================
# STATUTS DES ABONNEMENTS
# ============================================================================

SUBSCRIPTION_STATUS = {
    'PENDING': _('En attente'),
    'ACTIVE': _('Actif'),
    'PAST_DUE': _('En retard'),
    'CANCELED': _('Annulé'),
    'EXPIRED': _('Expiré'),
    'SUSPENDED': _('Suspendu'),
}

SUBSCRIPTION_STATUS_CHOICES = [
    ('PENDING', SUBSCRIPTION_STATUS['PENDING']),
    ('ACTIVE', SUBSCRIPTION_STATUS['ACTIVE']),
    ('PAST_DUE', SUBSCRIPTION_STATUS['PAST_DUE']),
    ('CANCELED', SUBSCRIPTION_STATUS['CANCELED']),
    ('EXPIRED', SUBSCRIPTION_STATUS['EXPIRED']),
    ('SUSPENDED', SUBSCRIPTION_STATUS['SUSPENDED']),
]

SUBSCRIPTION_INTERVALS = {
    'DAILY': _('Quotidien'),
    'WEEKLY': _('Hebdomadaire'),
    'MONTHLY': _('Mensuel'),
    'QUARTERLY': _('Trimestriel'),
    'SEMI_ANNUAL': _('Semestriel'),
    'ANNUAL': _('Annuel'),
}

SUBSCRIPTION_INTERVAL_CHOICES = [
    ('DAILY', SUBSCRIPTION_INTERVALS['DAILY']),
    ('WEEKLY', SUBSCRIPTION_INTERVALS['WEEKLY']),
    ('MONTHLY', SUBSCRIPTION_INTERVALS['MONTHLY']),
    ('QUARTERLY', SUBSCRIPTION_INTERVALS['QUARTERLY']),
    ('SEMI_ANNUAL', SUBSCRIPTION_INTERVALS['SEMI_ANNUAL']),
    ('ANNUAL', SUBSCRIPTION_INTERVALS['ANNUAL']),
]

# ============================================================================
# TYPES DE COUPONS
# ============================================================================

COUPON_TYPES = {
    'PERCENTAGE': _('Pourcentage'),
    'FIXED_AMOUNT': _('Montant fixe'),
    'FREE_SHIPPING': _('Livraison gratuite'),
}

COUPON_TYPE_CHOICES = [
    ('PERCENTAGE', COUPON_TYPES['PERCENTAGE']),
    ('FIXED_AMOUNT', COUPON_TYPES['FIXED_AMOUNT']),
    ('FREE_SHIPPING', COUPON_TYPES['FREE_SHIPPING']),
]

# ============================================================================
# TYPES DE TAXES
# ============================================================================

TAX_TYPES = {
    'VAT': _('TVA'),
    'GST': _('GST'),
    'SALES_TAX': _('Taxe de vente'),
    'SERVICE_TAX': _('Taxe sur les services'),
    'OTHER': _('Autre'),
}

TAX_TYPE_CHOICES = [
    ('VAT', TAX_TYPES['VAT']),
    ('GST', TAX_TYPES['GST']),
    ('SALES_TAX', TAX_TYPES['SALES_TAX']),
    ('SERVICE_TAX', TAX_TYPES['SERVICE_TAX']),
    ('OTHER', TAX_TYPES['OTHER']),
]

# ============================================================================
# DEVISES SUPPORTÉES
# ============================================================================

CURRENCIES = {
    'EUR': {'symbol': '€', 'name': _('Euro')},
    'USD': {'symbol': '$', 'name': _('Dollar américain')},
    'GBP': {'symbol': '£', 'name': _('Livre sterling')},
    'MAD': {'symbol': 'DH', 'name': _('Dirham marocain')},
    'XOF': {'symbol': 'CFA', 'name': _('Franc CFA')},
    'CAD': {'symbol': '$', 'name': _('Dollar canadien')},
    'AUD': {'symbol': '$', 'name': _('Dollar australien')},
    'JPY': {'symbol': '¥', 'name': _('Yen japonais')},
    'CHF': {'symbol': 'CHF', 'name': _('Franc suisse')},
    'CNY': {'symbol': '¥', 'name': _('Yuan chinois')},
    'INR': {'symbol': '₹', 'name': _('Roupie indienne')},
    'RUB': {'symbol': '₽', 'name': _('Rouble russe')},
    'BRL': {'symbol': 'R$', 'name': _('Real brésilien')},
    'ZAR': {'symbol': 'R', 'name': _('Rand sud-africain')},
}

CURRENCY_CHOICES = [
    ('EUR', f"€ - {CURRENCIES['EUR']['name']}"),
    ('USD', f"$ - {CURRENCIES['USD']['name']}"),
    ('GBP', f"£ - {CURRENCIES['GBP']['name']}"),
    ('MAD', f"DH - {CURRENCIES['MAD']['name']}"),
    ('XOF', f"CFA - {CURRENCIES['XOF']['name']}"),
    ('CAD', f"$ - {CURRENCIES['CAD']['name']}"),
    ('AUD', f"$ - {CURRENCIES['AUD']['name']}"),
    ('JPY', f"¥ - {CURRENCIES['JPY']['name']}"),
    ('CHF', f"CHF - {CURRENCIES['CHF']['name']}"),
    ('CNY', f"¥ - {CURRENCIES['CNY']['name']}"),
    ('INR', f"₹ - {CURRENCIES['INR']['name']}"),
    ('RUB', f"₽ - {CURRENCIES['RUB']['name']}"),
    ('BRL', f"R$ - {CURRENCIES['BRL']['name']}"),
    ('ZAR', f"R - {CURRENCIES['ZAR']['name']}"),
]

# ============================================================================
# PAYS POUR LES TAXES
# ============================================================================

EU_COUNTRIES = [
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
    'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
]

# ============================================================================
# TAUX DE TVA STANDARD PAR PAYS (en %)
# ============================================================================

VAT_RATES = {
    'FR': 20.0,   # France
    'DE': 19.0,   # Allemagne
    'IT': 22.0,   # Italie
    'ES': 21.0,   # Espagne
    'BE': 21.0,   # Belgique
    'NL': 21.0,   # Pays-Bas
    'LU': 17.0,   # Luxembourg
    'AT': 20.0,   # Autriche
    'FI': 24.0,   # Finlande
    'SE': 25.0,   # Suède
    'DK': 25.0,   # Danemark
    'IE': 23.0,   # Irlande
    'PT': 23.0,   # Portugal
    'GR': 24.0,   # Grèce
    'PL': 23.0,   # Pologne
    'CZ': 21.0,   # République Tchèque
    'HU': 27.0,   # Hongrie
    'RO': 19.0,   # Roumanie
    'BG': 20.0,   # Bulgarie
    'HR': 25.0,   # Croatie
    'SI': 22.0,   # Slovénie
    'SK': 20.0,   # Slovaquie
    'EE': 20.0,   # Estonie
    'LV': 21.0,   # Lettonie
    'LT': 21.0,   # Lituanie
    'CY': 19.0,   # Chypre
    'MT': 18.0,   # Malte
}

# ============================================================================
# LIMITES ET CONFIGURATIONS
# ============================================================================

# Limites de montant (en devise par défaut)
MIN_TRANSACTION_AMOUNT = 0.01
MAX_TRANSACTION_AMOUNT = 100000.00

# Délais d'expiration (en secondes)
PAYMENT_SESSION_TIMEOUT = 1800  # 30 minutes
PENDING_TRANSACTION_TIMEOUT = 3600  # 1 heure

# Tentatives maximum
MAX_PAYMENT_ATTEMPTS = 3
MAX_REFUND_ATTEMPTS = 2

# Configuration des frais
PROCESSING_FEE_PERCENTAGE = 2.9  # 2.9%
PROCESSING_FEE_FIXED = 0.30      # 0.30 unités de devise
MIN_PROCESSING_FEE = 0.50

# Configuration des remboursements
REFUND_PROCESSING_DAYS = {
    'CREDIT_CARD': 5,
    'PAYPAL': 3,
    'BANK_TRANSFER': 7,
    'CASH': 0,
}

# ============================================================================
# ERREURS ET CODES
# ============================================================================

ERROR_CODES = {
    # Erreurs générales
    'INVALID_REQUEST': 'PAYMENT_001',
    'MISSING_PARAMETER': 'PAYMENT_002',
    'INVALID_PARAMETER': 'PAYMENT_003',
    'UNAUTHORIZED': 'PAYMENT_004',
    'FORBIDDEN': 'PAYMENT_005',
    'NOT_FOUND': 'PAYMENT_006',
    'RATE_LIMIT_EXCEEDED': 'PAYMENT_007',

    # Erreurs de paiement
    'INSUFFICIENT_FUNDS': 'PAYMENT_101',
    'CARD_DECLINED': 'PAYMENT_102',
    'EXPIRED_CARD': 'PAYMENT_103',
    'INVALID_CARD': 'PAYMENT_104',
    'INVALID_CVV': 'PAYMENT_105',
    'PROCESSING_ERROR': 'PAYMENT_106',
    'GATEWAY_ERROR': 'PAYMENT_107',
    'TIMEOUT': 'PAYMENT_108',

    # Erreurs de remboursement
    'REFUND_NOT_ALLOWED': 'PAYMENT_201',
    'REFUND_AMOUNT_EXCEEDED': 'PAYMENT_202',
    'REFUND_TIME_LIMIT_EXCEEDED': 'PAYMENT_203',
    'REFUND_PROCESSING_ERROR': 'PAYMENT_204',

    # Erreurs de sécurité
    'FRAUD_DETECTED': 'PAYMENT_301',
    'SECURITY_VIOLATION': 'PAYMENT_302',
    'SUSPICIOUS_ACTIVITY': 'PAYMENT_303',

    # Erreurs de configuration
    'CONFIGURATION_ERROR': 'PAYMENT_401',
    'GATEWAY_NOT_CONFIGURED': 'PAYMENT_402',

    # Erreurs de devise
    'CURRENCY_NOT_SUPPORTED': 'PAYMENT_501',
    'CURRENCY_MISMATCH': 'PAYMENT_502',

    # Erreurs de taxe
    'TAX_CALCULATION_ERROR': 'PAYMENT_601',
    'INVALID_TAX_RATE': 'PAYMENT_602',
}

# ============================================================================
# REGEX ET FORMATS
# ============================================================================

REGEX_PATTERNS = {
    'CREDIT_CARD': r'^[0-9]{13,19}$',
    'CVV': r'^[0-9]{3,4}$',
    'EXPIRY_DATE': r'^(0[1-9]|1[0-2])/([0-9]{2})$',
    'IBAN': r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$',
    'BIC': r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$',
    'EMAIL': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'PHONE': r'^\+[1-9]\d{1,14}$',
}

# ============================================================================
# NOMS DE FICHIERS ET PATHS
# ============================================================================

FILE_PATHS = {
    'INVOICE_PDFS': 'invoices/pdfs/',
    'RECEIPT_PDFS': 'receipts/pdfs/',
    'PAYMENT_PROOFS': 'payments/proofs/',
    'REFUND_DOCUMENTS': 'refunds/documents/',
}

# ============================================================================
# NOMS DES ÉVÉNEMENTS WEBHOOK
# ============================================================================

WEBHOOK_EVENTS = {
    'STRIPE': [
        'payment_intent.succeeded',
        'payment_intent.payment_failed',
        'payment_intent.canceled',
        'charge.refunded',
        'charge.dispute.created',
        'invoice.payment_succeeded',
        'invoice.payment_failed',
        'customer.subscription.created',
        'customer.subscription.updated',
        'customer.subscription.deleted',
    ],
    'PAYPAL': [
        'PAYMENT.CAPTURE.COMPLETED',
        'PAYMENT.CAPTURE.DENIED',
        'PAYMENT.CAPTURE.REFUNDED',
        'PAYMENT.CAPTURE.REVERSED',
        'BILLING.SUBSCRIPTION.ACTIVATED',
        'BILLING.SUBSCRIPTION.CANCELLED',
    ],
}

# ============================================================================
# MESSAGES DE SUCCÈS
# ============================================================================

SUCCESS_MESSAGES = {
    'PAYMENT_COMPLETED': _('Paiement effectué avec succès.'),
    'REFUND_PROCESSED': _('Remboursement traité avec succès.'),
    'INVOICE_GENERATED': _('Facture générée avec succès.'),
    'SUBSCRIPTION_ACTIVATED': _('Abonnement activé avec succès.'),
    'COUPON_APPLIED': _('Coupon appliqué avec succès.'),
}

# ============================================================================
# CONFIGURATION PAR DÉFAUT
# ============================================================================

DEFAULT_CONFIG = {
    'DEFAULT_CURRENCY': 'EUR',
    'DEFAULT_TIMEZONE': 'Europe/Paris',
    'DEFAULT_LANGUAGE': 'fr',
    'DEFAULT_DATE_FORMAT': 'd/m/Y',
    'DEFAULT_DATETIME_FORMAT': 'd/m/Y H:i:s',
    'RECORDS_PER_PAGE': 20,
    'AUTO_GENERATE_INVOICE': True,
    'SEND_PAYMENT_EMAILS': True,
    'ENABLE_TAX_CALCULATION': True,
}

# ============================================================================
# VERSIONS D'API
# ============================================================================

API_VERSIONS = {
    'V1': '1.0',
    'V2': '2.0',
    'CURRENT': '1.0',
}

# ============================================================================
# PERMISSIONS
# ============================================================================

PERMISSIONS = {
    'VIEW_TRANSACTIONS': 'payments.view_transaction',
    'ADD_TRANSACTIONS': 'payments.add_transaction',
    'CHANGE_TRANSACTIONS': 'payments.change_transaction',
    'DELETE_TRANSACTIONS': 'payments.delete_transaction',
    'PROCESS_REFUNDS': 'payments.process_refunds',
    'VIEW_INVOICES': 'payments.view_invoice',
    'GENERATE_INVOICES': 'payments.generate_invoice',
    'MANAGE_SUBSCRIPTIONS': 'payments.manage_subscriptions',
    'VIEW_REPORTS': 'payments.view_reports',
}

# ============================================================================
# NOMS DES BACKENDS DE PAIEMENT
# ============================================================================

PAYMENT_BACKENDS = {
    'STRIPE': 'stripe',
    'PAYPAL': 'paypal',
    'BANK_TRANSFER': 'bank_transfer',
    'CASH_ON_DELIVERY': 'cash_on_delivery',
    'MOBILE_MONEY': 'mobile_money',
}
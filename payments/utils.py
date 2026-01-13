# ~/ebi3/payments/utils.py
"""
Utilitaires pour l'application payments
Fonctions de chiffrement, validation, calculs financiers, etc.
"""

import json
import uuid
import hashlib
import hmac
import base64
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string, constant_time_compare
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import stripe
import paypalrestsdk
import requests
from requests.exceptions import RequestException

from .models import (
    PaymentTransaction, Invoice, Refund, Payout, Wallet,
    WalletTransaction, Tax, ExchangeRate, FraudAlert, AuditLog
)
from users.models import User

# Configuration du logger
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTES ET CONFIGURATION
# ============================================================================

class PaymentErrorCode(Enum):
    """Codes d'erreur standardisés pour les paiements"""
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    EXPIRED_CARD = "expired_card"
    INVALID_CVC = "invalid_cvc"
    PROCESSING_ERROR = "processing_error"
    FRAUD_DETECTED = "fraud_detected"
    LIMIT_EXCEEDED = "limit_exceeded"
    CURRENCY_MISMATCH = "currency_mismatch"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"


class Currency(Enum):
    """Devises supportées avec précision"""
    EUR = {"symbol": "€", "decimal_places": 2}
    USD = {"symbol": "$", "decimal_places": 2}
    GBP = {"symbol": "£", "decimal_places": 2}
    MAD = {"symbol": "DH", "decimal_places": 2}
    XOF = {"symbol": "CFA", "decimal_places": 0}
    XAF = {"symbol": "FCFA", "decimal_places": 0}
    TND = {"symbol": "DT", "decimal_places": 3}
    DZD = {"symbol": "DA", "decimal_places": 2}


# ============================================================================
# CHIFFREMENT ET SÉCURITÉ
# ============================================================================

class EncryptionManager:
    """Gestionnaire de chiffrement pour les données sensibles"""

    def __init__(self):
        self.key = self._load_encryption_key()
        self.fernet = Fernet(self.key)

    def _load_encryption_key(self) -> bytes:
        """Charge ou génère la clé de chiffrement"""
        key = settings.PAYMENT_ENCRYPTION_KEY

        if not key:
            # Générer une nouvelle clé (pour le développement seulement)
            logger.warning("No encryption key found, generating temporary key")
            key = Fernet.generate_key()

        if isinstance(key, str):
            key = key.encode('utf-8')

        return key

    def encrypt_data(self, data: Dict) -> str:
        """Chiffre les données sensibles"""
        try:
            json_data = json.dumps(data).encode('utf-8')
            encrypted = self.fernet.encrypt(json_data)
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise ValueError(_("Erreur de chiffrement des données"))

    def decrypt_data(self, encrypted_data: str) -> Dict:
        """Déchiffre les données sensibles"""
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted = self.fernet.decrypt(encrypted)
            return json.loads(decrypted.decode('utf-8'))
        except InvalidToken:
            logger.error("Invalid encryption token")
            raise ValueError(_("Token de chiffrement invalide"))
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise ValueError(_("Erreur de déchiffrement des données"))

    def generate_token(self, data: Dict, expiry_hours: int = 24) -> str:
        """Génère un token sécurisé avec expiration"""
        payload = {
            'data': data,
            'expiry': (timezone.now() + timedelta(hours=expiry_hours)).isoformat(),
            'nonce': get_random_string(32)
        }

        encrypted = self.encrypt_data(payload)

        # Ajouter une signature HMAC
        signature = hmac.new(
            self.key,
            encrypted.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return f"{encrypted}.{signature}"

    def validate_token(self, token: str) -> Optional[Dict]:
        """Valide et décode un token"""
        try:
            encrypted, signature = token.rsplit('.', 1)

            # Vérifier la signature
            expected_signature = hmac.new(
                self.key,
                encrypted.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            if not constant_time_compare(signature, expected_signature):
                logger.warning("Invalid token signature")
                return None

            # Déchiffrer les données
            payload = self.decrypt_data(encrypted)

            # Vérifier l'expiration
            expiry = datetime.fromisoformat(payload['expiry'])
            if timezone.make_aware(expiry) < timezone.now():
                logger.warning("Token expired")
                return None

            return payload['data']

        except (ValueError, KeyError) as e:
            logger.error(f"Token validation error: {e}")
            return None


class CardDataEncryptor:
    """Spécialisé dans le chiffrement des données de carte"""

    def __init__(self):
        self.encryption_manager = EncryptionManager()

    def encrypt_card(self, card_data: Dict) -> Dict:
        """Chiffre les données de carte de manière sécurisée"""
        required_fields = ['number', 'exp_month', 'exp_year', 'cvc']

        if not all(field in card_data for field in required_fields):
            raise ValueError(_("Données de carte incomplètes"))

        # Extraire les 4 derniers chiffres pour l'affichage
        last4 = card_data['number'][-4:]

        # Chiffrer les données complètes
        encrypted = self.encryption_manager.encrypt_data(card_data)

        # Générer un token unique pour cette carte
        card_token = f"card_{uuid.uuid4().hex}"

        return {
            'encrypted_data': encrypted,
            'last4': last4,
            'exp_month': card_data['exp_month'],
            'exp_year': card_data['exp_year'],
            'brand': self._detect_card_brand(card_data['number']),
            'token': card_token,
            'fingerprint': self._generate_card_fingerprint(card_data)
        }

    def decrypt_card(self, encrypted_card: Dict) -> Optional[Dict]:
        """Déchiffre les données de carte"""
        try:
            return self.encryption_manager.decrypt_data(encrypted_card['encrypted_data'])
        except Exception as e:
            logger.error(f"Card decryption error: {e}")
            return None

    def _detect_card_brand(self, card_number: str) -> str:
        """Détecte la marque de la carte"""
        card_number = card_number.replace(' ', '')

        if card_number.startswith('4'):
            return 'VISA'
        elif card_number.startswith(('51', '52', '53', '54', '55')):
            return 'MASTERCARD'
        elif card_number.startswith(('34', '37')):
            return 'AMEX'
        elif card_number.startswith(('300', '301', '302', '303', '304', '305', '36', '38')):
            return 'DINERS'
        elif card_number.startswith(('6011', '65')):
            return 'DISCOVER'
        elif card_number.startswith(('35', '2131', '1800')):
            return 'JCB'
        else:
            return 'UNKNOWN'

    def _generate_card_fingerprint(self, card_data: Dict) -> str:
        """Génère une empreinte unique pour la carte"""
        data = f"{card_data['number'][-8:]}{card_data['exp_month']}{card_data['exp_year']}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]


# ============================================================================
# CALCULS FINANCIERS
# ============================================================================

class FinancialCalculator:
    """Effectue tous les calculs financiers"""

    @staticmethod
    def calculate_fees(
        amount: Decimal,
        payment_method: str,
        currency: str = 'EUR'
    ) -> Dict[str, Decimal]:
        """Calcule les frais de transaction"""

        # Taux de frais par méthode (en pourcentage)
        fee_rates = {
            'CREDIT_CARD': Decimal('0.029'),  # 2.9%
            'DEBIT_CARD': Decimal('0.019'),   # 1.9%
            'PAYPAL': Decimal('0.034'),       # 3.4%
            'STRIPE': Decimal('0.029'),       # 2.9%
            'EBI3_WALLET': Decimal('0.01'),   # 1%
            'BANK_TRANSFER': Decimal('0.005'), # 0.5%
            'PAYSTACK': Decimal('0.015'),     # 1.5%
            'CINETPAY': Decimal('0.02'),      # 2%
            'ORANGE_MONEY': Decimal('0.02'),  # 2%
            'MTN_MONEY': Decimal('0.02'),     # 2%
        }

        # Frais fixes par devise
        fixed_fees = {
            'EUR': Decimal('0.30'),
            'USD': Decimal('0.30'),
            'GBP': Decimal('0.25'),
            'MAD': Decimal('3.00'),
            'XOF': Decimal('200'),
            'XAF': Decimal('200'),
            'TND': Decimal('0.80'),
            'DZD': Decimal('40'),
        }

        # Récupérer les taux
        rate = fee_rates.get(payment_method, Decimal('0.03'))  # 3% par défaut
        fixed = fixed_fees.get(currency, Decimal('0.30'))

        # Calculer les frais variables
        variable_fee = amount * rate

        # Total des frais
        total_fee = variable_fee + fixed

        # Arrondir selon la devise
        total_fee = FinancialCalculator._round_currency(total_fee, currency)

        return {
            'variable_fee': variable_fee,
            'fixed_fee': fixed,
            'total_fee': total_fee,
            'rate': rate
        }

    @staticmethod
    def calculate_tax(
        amount: Decimal,
        user: User,
        country_code: Optional[str] = None
    ) -> Dict[str, Decimal]:
        """Calcule la TVA/Taxe applicable"""

        # Déterminer le pays
        if not country_code and hasattr(user, 'profile'):
            country_code = user.profile.country.code if user.profile.country else None

        if not country_code:
            country_code = 'FR'  # Par défaut France

        # Chercher le taux de taxe
        try:
            tax = Tax.objects.get(country=country_code, is_active=True)
            tax_rate = tax.tax_rate / 100
            tax_name = tax.tax_name
        except Tax.DoesNotExist:
            # Taux par défaut selon le pays
            default_rates = {
                'FR': Decimal('0.20'),   # 20%
                'BE': Decimal('0.21'),   # 21%
                'DE': Decimal('0.19'),   # 19%
                'ES': Decimal('0.21'),   # 21%
                'IT': Decimal('0.22'),   # 22%
                'MA': Decimal('0.20'),   # 20%
                'TN': Decimal('0.19'),   # 19%
                'DZ': Decimal('0.19'),   # 19%
                'SN': Decimal('0.18'),   # 18%
                'CI': Decimal('0.18'),   # 18%
            }
            tax_rate = default_rates.get(country_code, Decimal('0'))
            tax_name = "TVA" if tax_rate > 0 else "Taxe"

        # Calculer le montant taxable (souvent le net après frais)
        taxable_amount = amount

        # Calculer la taxe
        tax_amount = taxable_amount * tax_rate

        # Arrondir
        tax_amount = tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'tax_rate': tax_rate * 100,  # En pourcentage
            'tax_amount': tax_amount,
            'tax_name': tax_name,
            'country_code': country_code
        }

    @staticmethod
    def calculate_commission(
        amount: Decimal,
        transaction_type: str
    ) -> Dict[str, Decimal]:
        """Calcule la commission Ebi3"""

        # Taux de commission par type de transaction
        commission_rates = {
            'AD_PURCHASE': Decimal('0.10'),      # 10%
            'AD_FEATURED': Decimal('0.15'),      # 15%
            'AD_RESERVATION': Decimal('0.05'),   # 5%
            'MISSION_PAYMENT': Decimal('0.05'),  # 5%
            'WALLET_TRANSFER': Decimal('0.01'),  # 1%
            'SUBSCRIPTION': Decimal('0.00'),     # 0% pour abonnements
            'OTHER': Decimal('0.03'),            # 3% par défaut
        }

        rate = commission_rates.get(transaction_type, Decimal('0.03'))
        commission = amount * rate

        # Minimum de commission
        min_commission = Decimal('0.10')  # 0.10€ minimum

        if commission < min_commission:
            commission = min_commission

        return {
            'rate': rate,
            'amount': commission,
            'min_commission': min_commission
        }

    @staticmethod
    def calculate_net_amount(
        gross_amount: Decimal,
        fees: Decimal,
        tax: Decimal,
        commission: Decimal = Decimal('0')
    ) -> Decimal:
        """Calcule le montant net après déduction des frais"""
        net_amount = gross_amount - fees - tax - commission

        # Vérifier que le montant net n'est pas négatif
        if net_amount < Decimal('0'):
            raise ValueError(_("Le montant net ne peut pas être négatif"))

        return net_amount

    @staticmethod
    def convert_currency(
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Convertit un montant d'une devise à une autre"""

        if from_currency == to_currency:
            return {
                'amount': amount,
                'converted_amount': amount,
                'rate': Decimal('1'),
                'from_currency': from_currency,
                'to_currency': to_currency
            }

        # Récupérer le taux de change
        try:
            if date:
                exchange_rate = ExchangeRate.objects.get(
                    base_currency=from_currency,
                    target_currency=to_currency,
                    last_updated__date=date.date(),
                    is_active=True
                )
            else:
                exchange_rate = ExchangeRate.objects.filter(
                    base_currency=from_currency,
                    target_currency=to_currency,
                    is_active=True
                ).latest('last_updated')

            rate = exchange_rate.rate
            source = exchange_rate.source

        except ExchangeRate.DoesNotExist:
            # Taux de change par défaut (pour développement)
            default_rates = {
                ('EUR', 'USD'): Decimal('1.08'),
                ('EUR', 'GBP'): Decimal('0.86'),
                ('EUR', 'MAD'): Decimal('10.75'),
                ('EUR', 'XOF'): Decimal('655.957'),
                ('USD', 'EUR'): Decimal('0.93'),
                ('GBP', 'EUR'): Decimal('1.16'),
                ('MAD', 'EUR'): Decimal('0.093'),
            }

            rate = default_rates.get((from_currency, to_currency))
            source = 'DEFAULT'

            if not rate:
                raise ValueError(_(f"Taux de change non disponible pour {from_currency} -> {to_currency}"))

        # Convertir le montant
        converted_amount = amount * rate

        # Arrondir selon la devise de destination
        converted_amount = FinancialCalculator._round_currency(converted_amount, to_currency)

        return {
            'amount': amount,
            'converted_amount': converted_amount,
            'rate': rate,
            'from_currency': from_currency,
            'to_currency': to_currency,
            'source': source,
            'date': date or timezone.now()
        }

    @staticmethod
    def _round_currency(amount: Decimal, currency: str) -> Decimal:
        """Arrondit un montant selon les règles de la devise"""
        try:
            currency_info = Currency[currency]
            decimal_places = currency_info.value['decimal_places']

            # Pour les devises sans décimales (comme XOF)
            if decimal_places == 0:
                return amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            # Pour les devises avec décimales
            quantizer = Decimal(f"0.{'0' * decimal_places}")
            return amount.quantize(quantizer, rounding=ROUND_HALF_UP)

        except KeyError:
            # Arrondi par défaut à 2 décimales
            return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_monthly_interest(
        principal: Decimal,
        annual_rate: Decimal,
        days: int = 30
    ) -> Decimal:
        """Calcule les intérêts mensuels"""
        daily_rate = annual_rate / Decimal('365')
        interest = principal * daily_rate * Decimal(days)
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ============================================================================
# GÉNÉRATION DE DOCUMENTS
# ============================================================================

class DocumentGenerator:
    """Génère des documents financiers (factures, reçus, etc.)"""

    @staticmethod
    def generate_invoice_pdf(invoice: Invoice) -> bytes:
        """Génère le PDF d'une facture"""
        try:
            # Rendre le template HTML
            html_content = render_to_string('payments/invoices/pdf_template.html', {
                'invoice': invoice,
                'company': {
                    'name': settings.COMPANY_NAME,
                    'address': settings.COMPANY_ADDRESS,
                    'vat_number': settings.COMPANY_VAT_NUMBER,
                    'logo_url': settings.COMPANY_LOGO_URL,
                }
            })

            # Convertir HTML en PDF
            # Note: Implémentation réelle nécessite WeasyPrint ou ReportLab
            pdf_content = DocumentGenerator._html_to_pdf(html_content)

            return pdf_content

        except Exception as e:
            logger.error(f"Invoice PDF generation error: {e}")
            raise

    @staticmethod
    def generate_receipt(transaction: PaymentTransaction) -> Dict:
        """Génère un reçu numérique signé"""

        # Créer le contenu du reçu
        receipt_data = {
            'receipt_id': f"RCP-{uuid.uuid4().hex[:8].upper()}",
            'transaction_id': str(transaction.transaction_id),
            'reference': transaction.reference,
            'date': timezone.now().isoformat(),
            'payer': {
                'id': str(transaction.payer.id) if transaction.payer else None,
                'username': transaction.payer.username if transaction.payer else None,
                'email': transaction.payer.email if transaction.payer else None,
            },
            'payee': {
                'id': str(transaction.payee.id) if transaction.payee else None,
                'username': transaction.payee.username if transaction.payee else None,
            },
            'amount': {
                'gross': str(transaction.amount),
                'currency': transaction.currency,
                'fees': str(transaction.fee_amount),
                'tax': str(transaction.tax_amount),
                'net': str(transaction.net_amount),
            },
            'payment_method': transaction.get_payment_method_display(),
            'status': transaction.get_status_display(),
            'description': f"Paiement {transaction.get_payment_type_display()}",
            'merchant': {
                'name': settings.COMPANY_NAME,
                'website': settings.SITE_URL,
                'support_email': settings.SUPPORT_EMAIL,
            }
        }

        # Signer le reçu
        signature = DocumentGenerator._sign_data(receipt_data)

        receipt_data['signature'] = signature
        receipt_data['verification_url'] = f"{settings.SITE_URL}/verify-receipt/{receipt_data['receipt_id']}"

        return receipt_data

    @staticmethod
    def generate_financial_report(
        start_date: datetime,
        end_date: datetime,
        report_type: str = 'DETAILED'
    ) -> Dict:
        """Génère un rapport financier"""

        # Récupérer les transactions
        transactions = PaymentTransaction.objects.filter(
            created_at__range=[start_date, end_date],
            status=PaymentTransaction.Status.COMPLETED
        )

        # Calculer les statistiques
        stats = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'summary': {
                'total_transactions': transactions.count(),
                'total_volume': transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
                'total_fees': transactions.aggregate(total=Sum('fee_amount'))['total'] or Decimal('0'),
                'total_tax': transactions.aggregate(total=Sum('tax_amount'))['total'] or Decimal('0'),
                'net_volume': transactions.aggregate(total=Sum('net_amount'))['total'] or Decimal('0'),
            },
            'by_currency': {},
            'by_method': {},
            'by_type': {},
        }

        # Statistiques par devise
        currency_stats = transactions.values('currency').annotate(
            count=Count('id'),
            volume=Sum('amount'),
            fees=Sum('fee_amount')
        )

        for stat in currency_stats:
            stats['by_currency'][stat['currency']] = {
                'count': stat['count'],
                'volume': stat['volume'],
                'fees': stat['fees'],
            }

        # Statistiques par méthode de paiement
        method_stats = transactions.values('payment_method').annotate(
            count=Count('id'),
            volume=Sum('amount')
        )

        for stat in method_stats:
            stats['by_method'][stat['payment_method']] = {
                'count': stat['count'],
                'volume': stat['volume'],
            }

        # Statistiques par type de transaction
        type_stats = transactions.values('payment_type').annotate(
            count=Count('id'),
            volume=Sum('amount')
        )

        for stat in type_stats:
            stats['by_type'][stat['payment_type']] = {
                'count': stat['count'],
                'volume': stat['volume'],
            }

        # Transactions détaillées si nécessaire
        if report_type == 'DETAILED':
            stats['transactions'] = list(transactions.values(
                'reference', 'created_at', 'amount', 'currency',
                'payment_method', 'payment_type', 'payer__username'
            )[:100])  # Limiter à 100 transactions

        return stats

    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """Convertit HTML en PDF (implémentation simplifiée)"""
        # En production, utiliser WeasyPrint ou ReportLab
        # Ceci est un placeholder pour la démonstration
        try:
            # Pour l'instant, retourner du HTML
            # Dans une implémentation réelle :
            # from weasyprint import HTML
            # pdf = HTML(string=html_content).write_pdf()
            return html_content.encode('utf-8')
        except Exception as e:
            logger.error(f"HTML to PDF conversion error: {e}")
            raise

    @staticmethod
    def _sign_data(data: Dict) -> str:
        """Signe numériquement des données"""
        # Créer une chaîne de données à signer
        data_string = json.dumps(data, sort_keys=True)

        # Générer la signature HMAC
        secret = settings.SECRET_KEY.encode('utf-8')
        signature = hmac.new(secret, data_string.encode('utf-8'), hashlib.sha256)

        return base64.urlsafe_b64encode(signature.digest()).decode('utf-8')


# ============================================================================
# NOTIFICATIONS ET COMMUNICATIONS
# ============================================================================

class NotificationManager:
    """Gère l'envoi des notifications de paiement"""

    @staticmethod
    def send_payment_confirmation(transaction: PaymentTransaction) -> bool:
        """Envoie une confirmation de paiement"""
        try:
            if not transaction.payer or not transaction.payer.email:
                return False

            subject = _("Confirmation de paiement - {}").format(transaction.reference)

            # Rendre le template d'email
            context = {
                'transaction': transaction,
                'user': transaction.payer,
                'site_url': settings.SITE_URL,
                'support_email': settings.SUPPORT_EMAIL,
            }

            html_message = render_to_string('payments/emails/payment_confirmation.html', context)
            text_message = render_to_string('payments/emails/payment_confirmation.txt', context)

            # Envoyer l'email
            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.payer.email],
                fail_silently=False
            )

            logger.info(f"Payment confirmation sent for transaction {transaction.reference}")
            return True

        except Exception as e:
            logger.error(f"Payment confirmation email error: {e}")
            return False

    @staticmethod
    def send_payment_received(transaction: PaymentTransaction) -> bool:
        """Notifie le bénéficiaire qu'un paiement a été reçu"""
        try:
            if not transaction.payee or not transaction.payee.email:
                return False

            subject = _("Paiement reçu - {}").format(transaction.reference)

            context = {
                'transaction': transaction,
                'user': transaction.payee,
                'site_url': settings.SITE_URL,
            }

            html_message = render_to_string('payments/emails/payment_received.html', context)
            text_message = render_to_string('payments/emails/payment_received.txt', context)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.payee.email],
                fail_silently=False
            )

            logger.info(f"Payment received notification sent for transaction {transaction.reference}")
            return True

        except Exception as e:
            logger.error(f"Payment received email error: {e}")
            return False

    @staticmethod
    def send_refund_status(refund: Refund) -> bool:
        """Notifie du statut d'un remboursement"""
        try:
            if not refund.requested_by or not refund.requested_by.email:
                return False

            subject = _("Statut de votre remboursement - {}").format(refund.transaction.reference)

            context = {
                'refund': refund,
                'user': refund.requested_by,
                'site_url': settings.SITE_URL,
            }

            html_message = render_to_string('payments/emails/refund_status.html', context)
            text_message = render_to_string('payments/emails/refund_status.txt', context)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[refund.requested_by.email],
                fail_silently=False
            )

            logger.info(f"Refund status notification sent for refund {refund.id}")
            return True

        except Exception as e:
            logger.error(f"Refund status email error: {e}")
            return False

    @staticmethod
    def send_payout_notification(payout: Payout) -> bool:
        """Notifie du traitement d'un versement"""
        try:
            if not payout.user or not payout.user.email:
                return False

            subject = _("Statut de votre versement - {}").format(payout.payout_id)

            context = {
                'payout': payout,
                'user': payout.user,
                'site_url': settings.SITE_URL,
            }

            html_message = render_to_string('payments/emails/payout_notification.html', context)
            text_message = render_to_string('payments/emails/payout_notification.txt', context)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[payout.user.email],
                fail_silently=False
            )

            logger.info(f"Payout notification sent for payout {payout.payout_id}")
            return True

        except Exception as e:
            logger.error(f"Payout notification email error: {e}")
            return False

    @staticmethod
    def send_fraud_alert(fraud_alert: FraudAlert) -> bool:
        """Envoie une alerte de fraude aux administrateurs"""
        try:
            admin_emails = User.objects.filter(
                is_staff=True,
                is_active=True
            ).values_list('email', flat=True)

            if not admin_emails:
                return False

            subject = _("🚨 Alerte de fraude - Transaction {}").format(
                fraud_alert.transaction.reference
            )

            context = {
                'fraud_alert': fraud_alert,
                'transaction': fraud_alert.transaction,
                'site_url': settings.SITE_URL,
            }

            html_message = render_to_string('payments/emails/fraud_alert.html', context)
            text_message = render_to_string('payments/emails/fraud_alert.txt', context)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(admin_emails),
                fail_silently=False
            )

            logger.info(f"Fraud alert sent for transaction {fraud_alert.transaction.reference}")
            return True

        except Exception as e:
            logger.error(f"Fraud alert email error: {e}")
            return False


# ============================================================================
# DÉTECTION DE FRAUDE
# ============================================================================

class FraudDetector:
    """Détecte les activités frauduleuses"""

    def __init__(self):
        self.rules = self._load_fraud_rules()

    def _load_fraud_rules(self) -> List[Dict]:
        """Charge les règles de détection de fraude"""
        return [
            {
                'name': 'HIGH_AMOUNT',
                'condition': lambda t: t.amount > Decimal('10000'),
                'score': 30,
                'message': _("Montant anormalement élevé"),
            },
            {
                'name': 'FREQUENT_TRANSACTIONS',
                'condition': lambda t: self._check_frequent_transactions(t),
                'score': 25,
                'message': _("Transactions trop fréquentes"),
            },
            {
                'name': 'MULTIPLE_FAILED_ATTEMPTS',
                'condition': lambda t: self._check_failed_attempts(t),
                'score': 40,
                'message': _("Multiples tentatives échouées"),
            },
            {
                'name': 'NEW_USER_HIGH_AMOUNT',
                'condition': lambda t: self._check_new_user_high_amount(t),
                'score': 35,
                'message': _("Nouvel utilisateur avec montant élevé"),
            },
            {
                'name': 'COUNTRY_MISMATCH',
                'condition': lambda t: self._check_country_mismatch(t),
                'score': 20,
                'message': _("Incohérence de pays"),
            },
            {
                'name': 'UNUSUAL_TIME',
                'condition': lambda t: self._check_unusual_time(t),
                'score': 15,
                'message': _("Heure de transaction inhabituelle"),
            },
        ]

    def analyze_transaction(self, transaction: PaymentTransaction) -> Dict:
        """Analyse une transaction pour détecter la fraude"""
        fraud_score = 0
        reasons = []

        for rule in self.rules:
            try:
                if rule['condition'](transaction):
                    fraud_score += rule['score']
                    reasons.append({
                        'rule': rule['name'],
                        'score': rule['score'],
                        'message': rule['message']
                    })
            except Exception as e:
                logger.error(f"Fraud rule error {rule['name']}: {e}")
                continue

        # Calculer le niveau de risque
        risk_level = self._calculate_risk_level(fraud_score)

        return {
            'fraud_score': fraud_score,
            'risk_level': risk_level,
            'reasons': reasons,
            'recommendation': self._get_recommendation(risk_level),
            'timestamp': timezone.now()
        }

    def _check_frequent_transactions(self, transaction: PaymentTransaction) -> bool:
        """Vérifie les transactions trop fréquentes"""
        if not transaction.payer:
            return False

        # Nombre de transactions dans les dernières 10 minutes
        recent_count = PaymentTransaction.objects.filter(
            payer=transaction.payer,
            created_at__gte=timezone.now() - timedelta(minutes=10)
        ).count()

        return recent_count > 5

    def _check_failed_attempts(self, transaction: PaymentTransaction) -> bool:
        """Vérifie les tentatives échouées récentes"""
        if not transaction.payer:
            return False

        # Nombre de transactions échouées dans la dernière heure
        failed_count = PaymentTransaction.objects.filter(
            payer=transaction.payer,
            status=PaymentTransaction.Status.FAILED,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()

        return failed_count >= 3

    def _check_new_user_high_amount(self, transaction: PaymentTransaction) -> bool:
        """Vérifie si un nouvel utilisateur fait un gros paiement"""
        if not transaction.payer:
            return False

        # Vérifier si l'utilisateur est nouveau (moins de 7 jours)
        user_age = timezone.now() - transaction.payer.date_joined
        is_new_user = user_age.days < 7

        # Vérifier si le montant est élevé
        is_high_amount = transaction.amount > Decimal('1000')

        return is_new_user and is_high_amount

    def _check_country_mismatch(self, transaction: PaymentTransaction) -> bool:
        """Vérifie les incohérences de pays"""
        if not transaction.payer or not hasattr(transaction.payer, 'profile'):
            return False

        # Cette règle nécessite des données de géolocalisation
        # Pour l'instant, retourner False
        return False

    def _check_unusual_time(self, transaction: PaymentTransaction) -> bool:
        """Vérifie si la transaction est à une heure inhabituelle"""
        # Transactions entre 2h et 5h du matin
        hour = transaction.created_at.hour
        return 2 <= hour <= 5

    def _calculate_risk_level(self, fraud_score: int) -> str:
        """Calcule le niveau de risque"""
        if fraud_score >= 70:
            return 'CRITICAL'
        elif fraud_score >= 50:
            return 'HIGH'
        elif fraud_score >= 30:
            return 'MEDIUM'
        elif fraud_score >= 15:
            return 'LOW'
        else:
            return 'NONE'

    def _get_recommendation(self, risk_level: str) -> str:
        """Retourne la recommandation basée sur le niveau de risque"""
        recommendations = {
            'CRITICAL': _("Bloquer la transaction et contacter le client"),
            'HIGH': _("Exiger une vérification supplémentaire (3D Secure)"),
            'MEDIUM': _("Surveiller et possiblement demander une confirmation"),
            'LOW': _("Autoriser mais surveiller"),
            'NONE': _("Autoriser la transaction"),
        }
        return recommendations.get(risk_level, _("Autoriser la transaction"))

    def create_fraud_alert(self, transaction: PaymentTransaction, analysis: Dict) -> Optional[FraudAlert]:
        """Crée une alerte de fraude si nécessaire"""
        if analysis['risk_level'] in ['MEDIUM', 'HIGH', 'CRITICAL']:
            try:
                fraud_alert = FraudAlert.objects.create(
                    transaction=transaction,
                    severity=analysis['risk_level'],
                    fraud_score=analysis['fraud_score'],
                    reasons=analysis['reasons']
                )

                # Envoyer une notification
                NotificationManager.send_fraud_alert(fraud_alert)

                return fraud_alert
            except Exception as e:
                logger.error(f"Error creating fraud alert: {e}")

        return None


# ============================================================================
# INTÉGRATION AVEC LES PASSERELLES DE PAIEMENT
# ============================================================================

class PaymentGatewayManager:
    """Gère l'intégration avec les différentes passerelles de paiement"""

    @staticmethod
    def process_stripe_payment(
        amount: Decimal,
        currency: str,
        payment_method_id: str,
        metadata: Dict,
        customer_email: Optional[str] = None
    ) -> Dict:
        """Traite un paiement via Stripe"""
        try:
            # Convertir le montant en cents
            amount_cents = int(amount * 100)

            # Créer ou récupérer le client
            customer = None
            if customer_email:
                customers = stripe.Customer.list(email=customer_email, limit=1)
                if customers.data:
                    customer = customers.data[0]
                else:
                    customer = stripe.Customer.create(email=customer_email)

            # Créer le PaymentIntent
            intent_data = {
                'amount': amount_cents,
                'currency': currency.lower(),
                'payment_method': payment_method_id,
                'confirmation_method': 'manual',
                'confirm': True,
                'metadata': metadata,
                'capture_method': 'automatic',
            }

            if customer:
                intent_data['customer'] = customer.id

            # Activer 3D Secure si nécessaire
            if amount > Decimal('100'):  # Au-dessus de 100€
                intent_data['payment_method_options'] = {
                    'card': {
                        'request_three_d_secure': 'any'
                    }
                }

            payment_intent = stripe.PaymentIntent.create(**intent_data)

            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'status': payment_intent.status,
                'requires_action': payment_intent.status == 'requires_action',
                'next_action': payment_intent.next_action if hasattr(payment_intent, 'next_action') else None,
            }

        except stripe.error.CardError as e:
            logger.error(f"Stripe card error: {e.error.code} - {e.error.message}")
            return {
                'success': False,
                'error_code': e.error.code,
                'error_message': e.error.message,
                'gateway': 'stripe',
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return {
                'success': False,
                'error_code': 'stripe_error',
                'error_message': str(e),
                'gateway': 'stripe',
            }

    @staticmethod
    def process_paypal_payment(
        amount: Decimal,
        currency: str,
        return_url: str,
        cancel_url: str,
        description: str = ""
    ) -> Dict:
        """Crée un paiement PayPal"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                },
                "transactions": [{
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    },
                    "description": description or f"Payment of {amount} {currency}"
                }]
            })

            if payment.create():
                # Trouver le lien d'approbation
                approval_url = None
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break

                return {
                    'success': True,
                    'payment_id': payment.id,
                    'approval_url': approval_url,
                    'status': payment.state,
                }
            else:
                logger.error(f"PayPal payment creation failed: {payment.error}")
                return {
                    'success': False,
                    'error_code': 'payment_creation_failed',
                    'error_message': str(payment.error),
                    'gateway': 'paypal',
                }

        except Exception as e:
            logger.error(f"PayPal error: {e}")
            return {
                'success': False,
                'error_code': 'paypal_error',
                'error_message': str(e),
                'gateway': 'paypal',
            }

    @staticmethod
    def execute_paypal_payment(payment_id: str, payer_id: str) -> Dict:
        """Exécute un paiement PayPal après approbation"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)

            if payment.execute({"payer_id": payer_id}):
                # Récupérer les détails de la transaction
                sale = payment.transactions[0].related_resources[0].sale

                return {
                    'success': True,
                    'sale_id': sale.id,
                    'state': sale.state,
                    'amount': sale.amount.total,
                    'currency': sale.amount.currency,
                    'create_time': sale.create_time,
                }
            else:
                logger.error(f"PayPal payment execution failed: {payment.error}")
                return {
                    'success': False,
                    'error_code': 'payment_execution_failed',
                    'error_message': str(payment.error),
                    'gateway': 'paypal',
                }

        except Exception as e:
            logger.error(f"PayPal execution error: {e}")
            return {
                'success': False,
                'error_code': 'execution_error',
                'error_message': str(e),
                'gateway': 'paypal',
            }

    @staticmethod
    def process_mobile_money_payment(
        provider: str,
        phone: str,
        amount: Decimal,
        currency: str,
        country: str
    ) -> Dict:
        """Traite un paiement par mobile money"""
        # Implémentation spécifique au fournisseur
        # Ceci est un exemple simplifié

        providers_config = {
            'ORANGE_MONEY': {
                'api_url': settings.ORANGE_MONEY_API_URL,
                'api_key': settings.ORANGE_MONEY_API_KEY,
            },
            'MTN_MONEY': {
                'api_url': settings.MTN_MONEY_API_URL,
                'api_key': settings.MTN_MONEY_API_KEY,
            },
        }

        config = providers_config.get(provider)
        if not config:
            return {
                'success': False,
                'error_code': 'provider_not_supported',
                'error_message': _("Fournisseur non supporté"),
            }

        try:
            # Préparer la requête
            headers = {
                'Authorization': f'Bearer {config["api_key"]}',
                'Content-Type': 'application/json',
            }

            payload = {
                'phone': phone,
                'amount': str(amount),
                'currency': currency,
                'country': country,
                'reference': f"EBI3_{uuid.uuid4().hex[:8].upper()}",
            }

            # Envoyer la requête
            response = requests.post(
                config['api_url'],
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'transaction_id': data.get('transaction_id'),
                    'status': data.get('status'),
                    'message': data.get('message'),
                    'gateway': provider.lower(),
                }
            else:
                logger.error(f"Mobile money API error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error_code': 'api_error',
                    'error_message': response.text,
                    'gateway': provider.lower(),
                }

        except RequestException as e:
            logger.error(f"Mobile money request error: {e}")
            return {
                'success': False,
                'error_code': 'network_error',
                'error_message': str(e),
                'gateway': provider.lower(),
            }


# ============================================================================
# UTILITAIRES DIVERS
# ============================================================================

class PaymentValidator:
    """Valide les données de paiement"""

    @staticmethod
    def validate_card_number(card_number: str) -> Tuple[bool, str]:
        """Valide un numéro de carte avec l'algorithme de Luhn"""
        card_number = card_number.replace(' ', '').replace('-', '')

        if not card_number.isdigit():
            return False, _("Le numéro de carte doit contenir uniquement des chiffres")

        if len(card_number) < 13 or len(card_number) > 19:
            return False, _("Numéro de carte invalide")

        # Algorithme de Luhn
        def luhn_checksum(card_number: str) -> bool:
            digits = [int(d) for d in card_number]
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum([int(x) for x in str(d * 2)])
            return checksum % 10 == 0

        if not luhn_checksum(card_number):
            return False, _("Numéro de carte invalide")

        return True, ""

    @staticmethod
    def validate_cvv(cvv: str) -> Tuple[bool, str]:
        """Valide un code CVV"""
        cvv = cvv.strip()

        if not cvv.isdigit():
            return False, _("Le CVV doit contenir uniquement des chiffres")

        if len(cvv) not in [3, 4]:
            return False, _("Le CVV doit contenir 3 ou 4 chiffres")

        return True, ""

    @staticmethod
    def validate_expiry_date(month: int, year: int) -> Tuple[bool, str]:
        """Valide une date d'expiration"""
        current_year = timezone.now().year
        current_month = timezone.now().month

        if year < current_year or (year == current_year and month < current_month):
            return False, _("La carte est expirée")

        if year > current_year + 20:
            return False, _("Date d'expiration invalide")

        if month < 1 or month > 12:
            return False, _("Mois invalide")

        return True, ""

    @staticmethod
    def validate_iban(iban: str) -> Tuple[bool, str]:
        """Valide un numéro IBAN"""
        iban = iban.upper().replace(' ', '')

        # Vérifier la longueur
        if len(iban) < 15 or len(iban) > 34:
            return False, _("IBAN invalide : longueur incorrecte")

        # Vérifier le format
        import re
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$', iban):
            return False, _("Format IBAN invalide")

        # Vérifier le pays
        supported_countries = ['FR', 'BE', 'DE', 'ES', 'IT', 'LU', 'NL', 'MA', 'TN', 'DZ']
        country_code = iban[:2]
        if country_code not in supported_countries:
            return False, _(f"IBAN du pays {country_code} non supporté")

        # Algorithme de vérification IBAN
        def iban_checksum(iban: str) -> bool:
            # Déplacer les 4 premiers caractères à la fin
            rearranged = iban[4:] + iban[:4]
            # Convertir les lettres en chiffres
            digits = ''
            for char in rearranged:
                if char.isdigit():
                    digits += char
                else:
                    digits += str(ord(char) - 55)
            # Calculer le modulo 97
            return int(digits) % 97 == 1

        if not iban_checksum(iban):
            return False, _("IBAN invalide")

        return True, ""


class ReferenceGenerator:
    """Génère des références uniques"""

    @staticmethod
    def generate_transaction_reference(prefix: str = "PAY") -> str:
        """Génère une référence de transaction unique"""
        date_str = timezone.now().strftime("%Y%m%d")
        random_str = uuid.uuid4().hex[:8].upper()
        return f"{prefix}{date_str}{random_str}"

    @staticmethod
    def generate_invoice_number() -> str:
        """Génère un numéro de facture unique"""
        year = timezone.now().strftime("%Y")
        month = timezone.now().strftime("%m")

        # Compter les factures du mois
        count = Invoice.objects.filter(
            invoice_date__year=int(year),
            invoice_date__month=int(month)
        ).count() + 1

        return f"INV{year}{month}{count:04d}"

    @staticmethod
    def generate_payout_reference() -> str:
        """Génère une référence de versement unique"""
        date_str = timezone.now().strftime("%Y%m%d")
        random_str = uuid.uuid4().hex[:6].upper()
        return f"PO{date_str}{random_str}"


# ============================================================================
# FONCTIONS D'AUDIT ET DE LOGGING
# ============================================================================

class AuditLogger:
    """Gère les logs d'audit pour la conformité"""

    @staticmethod
    def log_payment_action(
        user: User,
        action: str,
        transaction: Optional[PaymentTransaction] = None,
        details: Dict = None
    ) -> AuditLog:
        """Log une action de paiement"""
        try:
            audit_log = AuditLog.objects.create(
                user=user,
                action_type=action,
                action_description=AuditLogger._get_action_description(action, details),
                object_type='PaymentTransaction',
                object_id=str(transaction.transaction_id) if transaction else 'N/A',
                old_data=details.get('old_data') if details else None,
                new_data=details.get('new_data') if details else None,
                ip_address=AuditLogger._get_client_ip(),
                user_agent=AuditLogger._get_user_agent(),
            )
            return audit_log
        except Exception as e:
            logger.error(f"Audit log error: {e}")
            return None

    @staticmethod
    def log_refund_action(
        user: User,
        action: str,
        refund: Refund,
        details: Dict = None
    ) -> AuditLog:
        """Log une action de remboursement"""
        try:
            audit_log = AuditLog.objects.create(
                user=user,
                action_type=action,
                action_description=AuditLogger._get_action_description(action, details),
                object_type='Refund',
                object_id=str(refund.refund_id),
                old_data=details.get('old_data') if details else None,
                new_data=details.get('new_data') if details else None,
                ip_address=AuditLogger._get_client_ip(),
                user_agent=AuditLogger._get_user_agent(),
            )
            return audit_log
        except Exception as e:
            logger.error(f"Audit log error: {e}")
            return None

    @staticmethod
    def _get_action_description(action: str, details: Dict) -> str:
        """Génère une description d'action"""
        descriptions = {
            'CREATE': _("Création de transaction"),
            'UPDATE': _("Mise à jour de transaction"),
            'DELETE': _("Suppression de transaction"),
            'REFUND': _("Remboursement"),
            'PAYOUT': _("Versement"),
            'APPROVE': _("Approbation"),
            'REJECT': _("Rejet"),
        }

        base_description = descriptions.get(action, action)

        if details and 'amount' in details:
            return f"{base_description} - Montant: {details['amount']}"

        return base_description

    @staticmethod
    def _get_client_ip() -> Optional[str]:
        """Récupère l'adresse IP du client"""
        # À implémenter selon le middleware utilisé
        return None

    @staticmethod
    def _get_user_agent() -> Optional[str]:
        """Récupère le User Agent du client"""
        # À implémenter selon la requête
        return None


# ============================================================================
# INSTANCES GLOBALES POUR FACILITER L'UTILISATION
# ============================================================================

# Instances globales pour un accès facile
encryption_manager = EncryptionManager()
card_encryptor = CardDataEncryptor()
financial_calculator = FinancialCalculator()
fraud_detector = FraudDetector()
payment_validator = PaymentValidator()
reference_generator = ReferenceGenerator()
notification_manager = NotificationManager()
document_generator = DocumentGenerator()
payment_gateway_manager = PaymentGatewayManager()
audit_logger = AuditLogger()
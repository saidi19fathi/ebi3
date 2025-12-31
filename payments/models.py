# ~/ebi3/payments/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
import uuid
import json
from decimal import Decimal
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django_countries.fields import CountryField
import hashlib
import hmac

# Import des applications liées
from ads.models import Ad
from carriers.models import Carrier
from logistics.models import Mission, TransportProposal
from users.models import User

# Liste commune des devises pour maintenir la cohérence
CURRENCY_CHOICES = [
    ('EUR', '€'),
    ('USD', '$'),
    ('GBP', '£'),
    ('MAD', 'DH'),
    ('XOF', 'CFA'),
    ('XAF', 'FCFA'),
    ('TND', 'DT'),      # Dinar tunisien - AJOUT
    ('DZD', 'DA'),      # Dinar algérien - AJOUT
]

# Validateurs personnalisés
def validate_iban(value):
    """Validation basique d'IBAN"""
    if not value.startswith(('FR', 'BE', 'DE', 'ES', 'IT', 'LU', 'NL')):
        raise ValidationError(_("IBAN non supporté. Seuls les IBAN européens sont acceptés."))
    if len(value) < 15 or len(value) > 34:
        raise ValidationError(_("IBAN invalide."))
    return value

def validate_card_number(value):
    """Validation de numéro de carte (algorithme de Luhn)"""
    def luhn_checksum(card_number):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10

    if luhn_checksum(value) != 0:
        raise ValidationError(_("Numéro de carte invalide."))
    return value

def validate_expiry_date(value):
    """Validation de date d'expiration"""
    if value < timezone.now().date():
        raise ValidationError(_("La date d'expiration est dépassée."))
    return value

# ============================================================================
# NOUVEAU MODÈLE : PaymentCard (carte bancaire sauvegardée)
# ============================================================================

class PaymentCard(models.Model):
    """Carte bancaire enregistrée par l'utilisateur"""

    class CardType(models.TextChoices):
        VISA = 'VISA', _('Visa')
        MASTERCARD = 'MASTERCARD', _('Mastercard')
        AMEX = 'AMEX', _('American Express')
        DISCOVER = 'DISCOVER', _('Discover')
        DINERS = 'DINERS', _('Diners Club')
        JCB = 'JCB', _('JCB')
        UNKNOWN = 'UNKNOWN', _('Inconnu')

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_cards',
        verbose_name=_("Utilisateur")
    )

    # Informations masquées
    last_four = models.CharField(
        max_length=4,
        verbose_name=_("4 derniers chiffres")
    )
    expiry_month = models.CharField(
        max_length=2,
        verbose_name=_("Mois d'expiration")
    )
    expiry_year = models.CharField(
        max_length=4,
        verbose_name=_("Année d'expiration")
    )
    cardholder_name = models.CharField(
        max_length=100,
        verbose_name=_("Nom du titulaire")
    )
    card_type = models.CharField(
        max_length=20,
        choices=CardType.choices,
        default=CardType.UNKNOWN,
        verbose_name=_("Type de carte")
    )

    # Données sécurisées (chiffrées)
    token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Token sécurisé")
    )
    provider = models.CharField(
        max_length=50,
        default='STRIPE',
        verbose_name=_("Fournisseur")
    )

    # Métadonnées
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Carte par défaut")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Vérifiée")
    )

    # Utilisation
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dernière utilisation")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Carte bancaire")
        verbose_name_plural = _("Cartes bancaires")
        ordering = ['-is_default', '-last_used']
        unique_together = ['user', 'token']

    def __str__(self):
        return f"{self.get_card_type_display()} **** {self.last_four}"

    def save(self, *args, **kwargs):
        # Si c'est la carte par défaut, désactiver les autres
        if self.is_default and self.is_active:
            PaymentCard.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def mask_display(self):
        """Retourne une version masquée pour l'affichage"""
        return f"{self.get_card_type_display()} **** **** **** {self.last_four}"

    def expiry_date_display(self):
        """Format d'expiration pour l'affichage"""
        return f"{self.expiry_month}/{self.expiry_year[-2:]}"

    def is_expired(self):
        """Vérifie si la carte est expirée"""
        today = timezone.now().date()
        expiry_date = timezone.datetime(
            year=int(self.expiry_year),
            month=int(self.expiry_month),
            day=1
        ).date()
        return expiry_date < today

    @staticmethod
    def detect_card_type(card_number):
        """Détecte le type de carte à partir du numéro"""
        card_number = str(card_number).replace(' ', '')

        if card_number.startswith('4'):
            return PaymentCard.CardType.VISA
        elif card_number.startswith(('51', '52', '53', '54', '55')):
            return PaymentCard.CardType.MASTERCARD
        elif card_number.startswith(('34', '37')):
            return PaymentCard.CardType.AMEX
        elif card_number.startswith(('6011', '65')):
            return PaymentCard.CardType.DISCOVER
        elif card_number.startswith(('300', '301', '302', '303', '304', '305', '36', '38')):
            return PaymentCard.CardType.DINERS
        elif card_number.startswith(('35', '2131', '1800')):
            return PaymentCard.CardType.JCB
        else:
            return PaymentCard.CardType.UNKNOWN


class PaymentTransaction(models.Model):
    """Transaction de paiement principale"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        PROCESSING = 'PROCESSING', _('En traitement')
        COMPLETED = 'COMPLETED', _('Complété')
        FAILED = 'FAILED', _('Échoué')
        REFUNDED = 'REFUNDED', _('Remboursé')
        PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED', _('Partiellement remboursé')
        CANCELLED = 'CANCELLED', _('Annulé')
        EXPIRED = 'EXPIRED', _('Expiré')
        DISPUTED = 'DISPUTED', _('En litige')

    class PaymentType(models.TextChoices):
        AD_PURCHASE = 'AD_PURCHASE', _('Achat annonce')
        AD_FEATURED = 'AD_FEATURED', _('Mise en vedette')
        AD_RESERVATION = 'AD_RESERVATION', _('Réservation annonce')
        MISSION_PAYMENT = 'MISSION_PAYMENT', _('Paiement mission')
        CARRIER_PAYOUT = 'CARRIER_PAYOUT', _('Versement transporteur')
        COMMISSION = 'COMMISSION', _('Commission Ebi3')
        WALLET_TOPUP = 'WALLET_TOPUP', _('Rechargement portefeuille')
        WALLET_TRANSFER = 'WALLET_TRANSFER', _('Transfert portefeuille')
        REFUND = 'REFUND', _('Remboursement')
        SUBSCRIPTION = 'SUBSCRIPTION', _('Abonnement')
        OTHER = 'OTHER', _('Autre')

    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = 'CREDIT_CARD', _('Carte de crédit')
        DEBIT_CARD = 'DEBIT_CARD', _('Carte de débit')
        PAYPAL = 'PAYPAL', _('PayPal')
        STRIPE = 'STRIPE', _('Stripe')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Virement bancaire')
        CASH = 'CASH', _('Espèces')
        EBI3_WALLET = 'EBI3_WALLET', _('Portefeuille Ebi3')
        PAYSTACK = 'PAYSTACK', _('Paystack')
        CINETPAY = 'CINETPAY', _('CinetPay')
        ORANGE_MONEY = 'ORANGE_MONEY', _('Orange Money')
        MTN_MONEY = 'MTN_MONEY', _('MTN Money')

    # Identifiants uniques
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("ID transaction")
    )
    reference = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_("Référence transaction")
    )

    # Parties impliquées
    payer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payment_sent',
        verbose_name=_("Payeur"),
        null=True,
        blank=True  # Pour les paiements système
    )
    payee = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payment_received',
        verbose_name=_("Bénéficiaire"),
        null=True,
        blank=True  # Pour les paiements système
    )

    # Montants
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_("Montant")
    )
    # MODIFICATION ICI : Utiliser la liste commune
    currency = models.CharField(
        max_length=3,
        default='EUR',
        choices=CURRENCY_CHOICES,  # ← Utilisation de la liste commune
        verbose_name=_("Devise")
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=1.0,
        verbose_name=_("Taux de change")
    )
    amount_converted = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        editable=False,
        verbose_name=_("Montant converti")
    )

    # Frais et taxes
    fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name=_("Frais de transaction")
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name=_("Montant taxes")
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        editable=False,
        verbose_name=_("Montant net")
    )

    # Métadonnées
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        verbose_name=_("Type de paiement")
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name=_("Méthode de paiement")
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("Statut")
    )

    # Intégration avec autres apps
    ad = models.ForeignKey(
        Ad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Annonce liée")
    )
    mission = models.ForeignKey(
        Mission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Mission liée")
    )
    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Transporteur lié")
    )
    transport_proposal = models.ForeignKey(
        TransportProposal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Proposition transport liée")
    )

    # Données de paiement sécurisées
    payment_token = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        verbose_name=_("Token de paiement")
    )
    payment_gateway_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("ID passerelle")
    )
    payment_gateway_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Données passerelle")
    )

    # 3D Secure
    three_d_secure = models.BooleanField(
        default=False,
        verbose_name=_("3D Secure activé")
    )
    three_d_secure_status = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('NOT_SUPPORTED', _('Non supporté')),
            ('SUCCESS', _('Succès')),
            ('FAILED', _('Échoué')),
            ('SKIPPED', _('Ignoré')),
        ],
        verbose_name=_("Statut 3D Secure")
    )

    # Fraude et sécurité
    fraud_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Score fraude")
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_("Adresse IP")
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_("User Agent")
    )
    risk_checked = models.BooleanField(
        default=False,
        verbose_name=_("Contrôle risque effectué")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Métadonnées supplémentaires
    metadata = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Métadonnées")
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes internes")
    )

    class Meta:
        verbose_name = _("Transaction de paiement")
        verbose_name_plural = _("Transactions de paiement")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payer', 'status']),
            models.Index(fields=['payee', 'status']),
            models.Index(fields=['payment_type', 'status']),
            models.Index(fields=['reference']),
            models.Index(fields=['payment_gateway_id']),
        ]
        permissions = [
            ('can_view_all_transactions', _('Peut voir toutes les transactions')),
            ('can_refund_transactions', _('Peut effectuer des remboursements')),
            ('can_export_financial_data', _('Peut exporter les données financières')),
            ('can_manage_fraud_detection', _('Peut gérer la détection de fraude')),
        ]

    def __str__(self):
        return f"{self.reference} - {self.get_payment_type_display()} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        # Génération automatique de la référence
        if not self.reference:
            prefix = "PAY"
            date_str = timezone.now().strftime("%Y%m%d")
            random_str = uuid.uuid4().hex[:6].upper()
            self.reference = f"{prefix}{date_str}{random_str}"

        # Calcul des montants
        if self.amount and self.exchange_rate:
            self.amount_converted = self.amount * self.exchange_rate

        if self.amount and self.fee_amount and self.tax_amount:
            self.net_amount = self.amount - self.fee_amount - self.tax_amount

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('payments:transaction_detail', kwargs={'transaction_id': str(self.transaction_id)})

    def is_refundable(self):
        """Vérifie si la transaction est remboursable"""
        if self.status not in [self.Status.COMPLETED, self.Status.PARTIALLY_REFUNDED]:
            return False
        if self.completed_at and timezone.now() - self.completed_at > timezone.timedelta(days=180):
            return False
        return True

    def calculate_refund_amount(self):
        """Calcule le montant maximum remboursable"""
        if not self.is_refundable():
            return Decimal('0')

        # Calculer le montant déjà remboursé
        from .models import Refund
        total_refunded = self.refunds.filter(
            status__in=[Refund.Status.APPROVED, Refund.Status.COMPLETED]
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        return self.amount - total_refunded

    def get_related_object(self):
        """Retourne l'objet lié à la transaction"""
        if self.ad:
            return self.ad
        elif self.mission:
            return self.mission
        elif self.carrier:
            return self.carrier
        elif self.transport_proposal:
            return self.transport_proposal
        return None

    def generate_receipt(self):
        """Génère un reçu numérique signé"""
        # Implémentation sécurisée dans utils.py
        pass


class PaymentMethod(models.Model):
    """Méthode de paiement enregistrée par l'utilisateur"""

    class MethodType(models.TextChoices):
        CARD = 'CARD', _('Carte bancaire')
        BANK_ACCOUNT = 'BANK_ACCOUNT', _('Compte bancaire')
        DIGITAL_WALLET = 'DIGITAL_WALLET', _('Portefeuille numérique')
        MOBILE_MONEY = 'MOBILE_MONEY', _('Mobile Money')

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_methods',
        verbose_name=_("Utilisateur")
    )
    method_type = models.CharField(
        max_length=20,
        choices=MethodType.choices,
        verbose_name=_("Type de méthode")
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Méthode par défaut")
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Vérifiée")
    )

    # Données chiffrées
    encrypted_data = models.TextField(
        verbose_name=_("Données chiffrées"),
        editable=False
    )
    encryption_key_id = models.CharField(
        max_length=100,
        editable=False,
        verbose_name=_("ID clé de chiffrement")
    )

    # Métadonnées
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dernière utilisation")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Méthode de paiement")
        verbose_name_plural = _("Méthodes de paiement")
        ordering = ['-is_default', '-last_used']
        unique_together = ['user', 'encryption_key_id']

    def __str__(self):
        return f"{self.user.username} - {self.get_method_type_display()}"

    def decrypt_data(self):
        """Déchiffre les données sensibles"""
        # Implémentation sécurisée dans utils.py
        pass

    def mask_display(self):
        """Retourne une version masquée pour l'affichage"""
        if self.method_type == self.MethodType.CARD:
            return "**** **** **** XXXX"
        elif self.method_type == self.MethodType.BANK_ACCOUNT:
            return "IBAN **** XXXX"
        return self.get_method_type_display()


class InvoiceItem(models.Model):
    """Élément d'une facture"""

    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Facture")
    )

    description = models.CharField(
        max_length=255,
        verbose_name=_("Description")
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
        verbose_name=_("Quantité")
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Prix unitaire")
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Taux de taxe (%)")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Date de modification")
    )

    class Meta:
        verbose_name = _("Élément de facture")
        verbose_name_plural = _("Éléments de facture")
        ordering = ['created_at']

    def __str__(self):
        return f"{self.description} - {self.quantity} × {self.unit_price}"

    def subtotal(self):
        """Calcule le sous-total (quantité × prix unitaire)"""
        return self.quantity * self.unit_price

    def tax_amount(self):
        """Calcule le montant de la taxe"""
        return self.subtotal() * (self.tax_rate / 100)

    def total(self):
        """Calcule le total (sous-total + taxe)"""
        return self.subtotal() + self.tax_amount()


class Invoice(models.Model):
    """Facture générée pour chaque transaction"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Brouillon')
        SENT = 'SENT', _('Envoyée')
        PAID = 'PAID', _('Payée')
        OVERDUE = 'OVERDUE', _('En retard')
        CANCELLED = 'CANCELLED', _('Annulée')

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_("Numéro de facture")
    )
    transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='invoice',
        verbose_name=_("Transaction")
    )

    # Détails de facturation
    billing_name = models.CharField(
        max_length=200,
        verbose_name=_("Nom de facturation")
    )
    billing_address = models.TextField(
        verbose_name=_("Adresse de facturation")
    )
    billing_country = CountryField(
        verbose_name=_("Pays de facturation")
    )
    billing_vat = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Numéro TVA")
    )

    # Montants détaillés
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Sous-total")
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Taux TVA (%)")
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Montant TVA")
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Montant total")
    )

    # Dates
    invoice_date = models.DateField(
        default=timezone.now,
        verbose_name=_("Date de facture")
    )
    due_date = models.DateField(
        verbose_name=_("Date d'échéance")
    )
    paid_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date de paiement")
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("Statut")
    )

    # Notes additionnelles
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes additionnelles")
    )

    # PDF généré
    pdf_file = models.FileField(
        upload_to='invoices/%Y/%m/',
        null=True,
        blank=True,
        verbose_name=_("Fichier PDF")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Facture")
        verbose_name_plural = _("Factures")
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"Facture {self.invoice_number} - {self.total_amount} {self.transaction.currency}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            prefix = "INV"
            year = timezone.now().strftime("%Y")
            month = timezone.now().strftime("%m")
            count = Invoice.objects.filter(
                invoice_date__year=year,
                invoice_date__month=month
            ).count() + 1
            self.invoice_number = f"{prefix}{year}{month}{count:04d}"

        super().save(*args, **kwargs)

    def is_overdue(self):
        """Vérifie si la facture est en retard"""
        if self.status == self.Status.PAID:
            return False
        return timezone.now().date() > self.due_date

    def generate_pdf(self):
        """Génère le PDF de la facture"""
        # Implémentation dans utils.py
        pass


class Refund(models.Model):
    """Demande et traitement de remboursement"""

    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', _('Demandé')
        UNDER_REVIEW = 'UNDER_REVIEW', _('En revue')
        APPROVED = 'APPROVED', _('Approuvé')
        REJECTED = 'REJECTED', _('Rejeté')
        PROCESSING = 'PROCESSING', _('En traitement')
        COMPLETED = 'COMPLETED', _('Complété')
        FAILED = 'FAILED', _('Échoué')

    class Reason(models.TextChoices):
        DUPLICATE_CHARGE = 'DUPLICATE_CHARGE', _('Double facturation')
        UNAUTHORIZED = 'UNAUTHORIZED', _('Non autorisé')
        PRODUCT_DEFECT = 'PRODUCT_DEFECT', _('Défaut produit')
        NOT_RECEIVED = 'NOT_RECEIVED', _('Non reçu')
        WRONG_AMOUNT = 'WRONG_AMOUNT', _('Mauvais montant')
        CANCELLED = 'CANCELLED', _('Annulé par client')
        OTHER = 'OTHER', _('Autre')

    refund_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("ID remboursement")
    )
    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name=_("Transaction originale")
    )

    # Demandeur
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='refunds_requested',
        verbose_name=_("Demandé par")
    )

    # Détails du remboursement
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_("Montant remboursé")
    )
    # MODIFICATION ICI : Utiliser la liste commune
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,  # ← Utilisation de la liste commune
        verbose_name=_("Devise")
    )
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        verbose_name=_("Raison")
    )
    description = models.TextField(
        verbose_name=_("Description détaillée")
    )
    evidence = models.FileField(
        upload_to='refunds/evidence/',
        null=True,
        blank=True,
        verbose_name=_("Preuve")
    )

    # Traitement
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
        verbose_name=_("Statut")
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds_reviewed',
        verbose_name=_("Revu par")
    )
    review_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de revue")
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_("Raison du rejet")
    )

    # Référence externe
    refund_gateway_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("ID remboursement passerelle")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Remboursement")
        verbose_name_plural = _("Remboursements")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['transaction', 'status']),
        ]

    def __str__(self):
        return f"Remboursement {self.refund_id} - {self.amount} {self.currency}"

    def can_be_processed(self):
        """Vérifie si le remboursement peut être traité"""
        return self.status == self.Status.APPROVED

    def process_refund(self):
        """Traite le remboursement"""
        # Implémentation dans views.py
        pass


class Commission(models.Model):
    """Commission perçue par Ebi3 sur chaque transaction"""

    transaction = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='commission',
        verbose_name=_("Transaction")
    )

    # Calcul de commission
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,  # 0.1000 pour 10%
        verbose_name=_("Taux de commission")
    )
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Montant commission")
    )
    vat_on_commission = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name=_("TVA sur commission")
    )
    net_commission = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Commission nette")
    )

    # Paiement de la commission
    is_paid = models.BooleanField(
        default=False,
        verbose_name=_("Commission payée")
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Payé le")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Commission")
        verbose_name_plural = _("Commissions")
        ordering = ['-created_at']

    def __str__(self):
        return f"Commission {self.net_commission} {self.transaction.currency}"

    def save(self, *args, **kwargs):
        if not self.commission_amount and self.transaction.amount:
            self.commission_amount = self.transaction.amount * self.commission_rate
            self.net_commission = self.commission_amount - self.vat_on_commission
        super().save(*args, **kwargs)


class Payout(models.Model):
    """Versement aux vendeurs/transporteurs"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        PROCESSING = 'PROCESSING', _('En traitement')
        COMPLETED = 'COMPLETED', _('Complété')
        FAILED = 'FAILED', _('Échoué')
        CANCELLED = 'CANCELLED', _('Annulé')

    class PayoutMethod(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', _('Virement bancaire')
        PAYPAL = 'PAYPAL', _('PayPal')
        STRIPE_CONNECT = 'STRIPE_CONNECT', _('Stripe Connect')
        EBI3_WALLET = 'EBI3_WALLET', _('Portefeuille Ebi3')
        WESTERN_UNION = 'WESTERN_UNION', _('Western Union')
        MONEYGRAM = 'MONEYGRAM', _('MoneyGram')

    payout_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("ID versement")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payouts',
        verbose_name=_("Bénéficiaire")
    )

    # Montants
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_("Montant")
    )
    # MODIFICATION ICI : Utiliser la liste commune
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,  # ← Utilisation de la liste commune
        verbose_name=_("Devise")
    )
    fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name=_("Frais de versement")
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Montant net")
    )

    # Méthode
    payout_method = models.CharField(
        max_length=20,
        choices=PayoutMethod.choices,
        verbose_name=_("Méthode de versement")
    )

    # Détails du bénéficiaire (chiffrés)
    beneficiary_data = models.TextField(
        verbose_name=_("Données bénéficiaire"),
        editable=False
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Statut")
    )

    # Transactions incluses
    transactions = models.ManyToManyField(
        PaymentTransaction,
        related_name='payouts',
        verbose_name=_("Transactions incluses")
    )

    # Référence externe
    payout_gateway_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("ID versement passerelle")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Versement")
        verbose_name_plural = _("Versements")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"Versement {self.payout_id} - {self.net_amount} {self.currency}"

    def save(self, *args, **kwargs):
        if not self.net_amount and self.amount and self.fee_amount:
            self.net_amount = self.amount - self.fee_amount
        super().save(*args, **kwargs)


class Wallet(models.Model):
    """Portefeuille Ebi3 d'un utilisateur"""

    class WalletStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Actif')
        SUSPENDED = 'SUSPENDED', _('Suspendu')
        LOCKED = 'LOCKED', _('Verrouillé')
        CLOSED = 'CLOSED', _('Fermé')

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wallet',
        verbose_name=_("Utilisateur")
    )

    # Soldes
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name=_("Solde")
    )
    # MODIFICATION ICI : Utiliser la liste commune
    currency = models.CharField(
        max_length=3,
        default='EUR',
        choices=CURRENCY_CHOICES,  # ← Utilisation de la liste commune
        verbose_name=_("Devise")
    )
    reserved_balance = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name=_("Solde réservé")
    )
    available_balance = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        editable=False,
        verbose_name=_("Solde disponible")
    )

    # Statut
    status = models.CharField(
        max_length=20,
        choices=WalletStatus.choices,
        default=WalletStatus.ACTIVE,
        verbose_name=_("Statut")
    )

    # Limites
    daily_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('1000'),
        verbose_name=_("Limite quotidienne")
    )
    monthly_limit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('5000'),
        verbose_name=_("Limite mensuelle")
    )

    # Sécurité
    pin_hash = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        verbose_name=_("Hash du PIN")
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_("Verrouillé")
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Verrouillé jusqu'à")
    )

    # Métadonnées
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_("Vérifié")
    )

    # Détection de fraude
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Score de risque")
    )
    blocked_balance = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name=_("Solde bloqué")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Portefeuille")
        verbose_name_plural = _("Portefeuilles")

    def __str__(self):
        return f"Portefeuille {self.user.username} - {self.balance} {self.currency}"

    def save(self, *args, **kwargs):
        self.available_balance = self.balance - self.reserved_balance - self.blocked_balance
        super().save(*args, **kwargs)

    def can_withdraw(self, amount):
        """Vérifie si le retrait est possible"""
        if self.is_locked or self.status != self.WalletStatus.ACTIVE:
            return False, _("Portefeuille verrouillé ou inactif")
        if amount > self.available_balance:
            return False, _("Solde insuffisant")
        if amount > self.daily_limit:
            return False, _("Limite quotidienne dépassée")
        return True, ""

    def get_monthly_stats(self):
        """Récupère les statistiques mensuelles"""
        # Implémentation dans utils.py
        pass

    def set_pin(self, pin):
        """Définit le code PIN du portefeuille"""
        from django.contrib.auth.hashers import make_password
        self.pin_hash = make_password(pin)

    def verify_pin(self, pin):
        """Vérifie le code PIN"""
        from django.contrib.auth.hashers import check_password
        return check_password(pin, self.pin_hash)

    def get_current_limits(self):
        """Retourne les limites actuelles"""
        return {
            'daily_limit': self.daily_limit,
            'monthly_limit': self.monthly_limit,
            'available_balance': self.available_balance
        }


class WalletTransaction(models.Model):
    """Transaction dans un portefeuille"""

    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', _('Dépôt')
        WITHDRAWAL = 'WITHDRAWAL', _('Retrait')
        TRANSFER = 'TRANSFER', _('Transfert')
        PAYMENT = 'PAYMENT', _('Paiement')
        REFUND = 'REFUND', _('Remboursement')
        COMMISSION = 'COMMISSION', _('Commission')
        BLOCK = 'BLOCK', _('Blocage')
        CREDIT = 'CREDIT', _('Crédit')
        DEBIT = 'DEBIT', _('Débit')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        PROCESSING = 'PROCESSING', _('En traitement')
        COMPLETED = 'COMPLETED', _('Complété')
        FAILED = 'FAILED', _('Échoué')
        CANCELLED = 'CANCELLED', _('Annulé')

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_("Portefeuille")
    )

    # Montant et type
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Montant")
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        verbose_name=_("Type de transaction")
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Statut")
    )

    # Références
    payment_transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        verbose_name=_("Transaction de paiement liée")
    )

    # Métadonnées
    description = models.CharField(
        max_length=255,
        verbose_name=_("Description")
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Référence")
    )
    metadata = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Métadonnées")
    )

    # Soldes avant/après
    balance_before = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Solde avant")
    )
    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Solde après")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Transaction portefeuille")
        verbose_name_plural = _("Transactions portefeuille")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} {self.wallet.currency}"


class Tax(models.Model):
    """Configuration des taxes par pays"""

    country = CountryField(
        unique=True,
        verbose_name=_("Pays")
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Taux TVA (%)")
    )
    tax_name = models.CharField(
        max_length=100,
        verbose_name=_("Nom de la taxe")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )

    # Exemptions
    exempt_categories = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Catégories exemptées")
    )
    minimum_amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name=_("Montant minimum")
    )

    class Meta:
        verbose_name = _("Taxe")
        verbose_name_plural = _("Taxes")

    def __str__(self):
        return f"{self.country.name} - {self.tax_rate}%"


class ExchangeRate(models.Model):
    """Taux de change pour les devises"""

    # MODIFICATION ICI : Utiliser la liste commune pour base_currency
    base_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,  # ← Utilisation de la liste commune
        verbose_name=_("Devise de base")
    )
    # MODIFICATION ICI : Utiliser la liste commune pour target_currency
    target_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,  # ← Utilisation de la liste commune
        verbose_name=_("Devise cible")
    )
    rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name=_("Taux")
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Dernière mise à jour")
    )
    source = models.CharField(
        max_length=50,
        verbose_name=_("Source")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )

    class Meta:
        verbose_name = _("Taux de change")
        verbose_name_plural = _("Taux de change")
        unique_together = ['base_currency', 'target_currency']

    def __str__(self):
        return f"{self.base_currency}/{self.target_currency}: {self.rate}"


class FraudAlert(models.Model):
    """Alerte de fraude détectée"""

    class Severity(models.TextChoices):
        LOW = 'LOW', _('Faible')
        MEDIUM = 'MEDIUM', _('Moyen')
        HIGH = 'HIGH', _('Élevé')
        CRITICAL = 'CRITICAL', _('Critique')

    transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.CASCADE,
        related_name='fraud_alerts',
        verbose_name=_("Transaction")
    )

    # Détection
    detected_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Détecté le")
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        verbose_name=_("Sévérité")
    )
    fraud_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Score de fraude")
    )

    # Raisons
    reasons = models.JSONField(
        verbose_name=_("Raisons de l'alerte")
    )

    # Actions
    action_taken = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Action prise")
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Revu par")
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Revu le")
    )
    review_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de revue")
    )

    # Résolution
    is_resolved = models.BooleanField(
        default=False,
        verbose_name=_("Résolu")
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Résolu le")
    )
    resolution_notes = models.TextField(
        blank=True,
        verbose_name=_("Notes de résolution")
    )

    class Meta:
        verbose_name = _("Alerte de fraude")
        verbose_name_plural = _("Alertes de fraude")
        ordering = ['-detected_at']

    def __str__(self):
        return f"Alerte {self.severity} - Transaction {self.transaction.reference}"


class AuditLog(models.Model):
    """Journal d'audit pour toutes les actions sensibles"""

    class ActionType(models.TextChoices):
        CREATE = 'CREATE', _('Création')
        UPDATE = 'UPDATE', _('Mise à jour')
        DELETE = 'DELETE', _('Suppression')
        APPROVE = 'APPROVE', _('Approbation')
        REJECT = 'REJECT', _('Rejet')
        REFUND = 'REFUND', _('Remboursement')
        PAYOUT = 'PAYOUT', _('Versement')
        LOGIN = 'LOGIN', _('Connexion')
        LOGOUT = 'LOGOUT', _('Déconnexion')
        WALLET_LOGIN = 'WALLET_LOGIN', _('Connexion portefeuille')
        WALLET_PIN_CHANGE = 'WALLET_PIN_CHANGE', _('Changement PIN portefeuille')
        WALLET_SECURITY_CHANGE = 'WALLET_SECURITY_CHANGE', _('Changement sécurité portefeuille')
        WALLET_CREATION = 'WALLET_CREATION', _('Création portefeuille')

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Utilisateur")
    )

    # Action
    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        verbose_name=_("Type d'action")
    )
    action_description = models.TextField(
        verbose_name=_("Description de l'action")
    )

    # Objet concerné
    object_type = models.CharField(
        max_length=100,
        verbose_name=_("Type d'objet")
    )
    object_id = models.CharField(
        max_length=100,
        verbose_name=_("ID de l'objet")
    )

    # Données
    old_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Anciennes données")
    )
    new_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Nouvelles données")
    )

    # Métadonnées
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("Adresse IP")
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_("User Agent")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Journal d'audit")
        verbose_name_plural = _("Journaux d'audit")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.object_type} - {self.created_at}"


# ============================================================================
# NOUVEAUX MODÈLES AJOUTÉS
# ============================================================================

class Plan(models.Model):
    """Plan d'abonnement"""

    class Interval(models.TextChoices):
        DAILY = 'DAILY', _('Quotidien')
        WEEKLY = 'WEEKLY', _('Hebdomadaire')
        MONTHLY = 'MONTHLY', _('Mensuel')
        QUARTERLY = 'QUARTERLY', _('Trimestriel')
        SEMI_ANNUAL = 'SEMI_ANNUAL', _('Semestriel')
        ANNUAL = 'ANNUAL', _('Annuel')

    name = models.CharField(max_length=100, verbose_name=_("Nom du plan"))
    description = models.TextField(verbose_name=_("Description"))
    price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Prix")
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='EUR',
        verbose_name=_("Devise")
    )
    interval = models.CharField(
        max_length=20,
        choices=Interval.choices,
        default='MONTHLY',
        verbose_name=_("Intervalle")
    )
    interval_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Nombre d'intervalles")
    )
    trial_period_days = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Période d'essai (jours)")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Actif"))
    features = models.JSONField(
        default=dict,
        verbose_name=_("Fonctionnalités")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Plan d'abonnement")
        verbose_name_plural = _("Plans d'abonnement")
        ordering = ['price']

    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}/{self.get_interval_display()}"


class Subscription(models.Model):
    """Abonnement utilisateur à un plan"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('En attente')
        ACTIVE = 'ACTIVE', _('Actif')
        PAST_DUE = 'PAST_DUE', _('En retard')
        CANCELLED = 'CANCELLED', _('Annulé')
        EXPIRED = 'EXPIRED', _('Expiré')
        SUSPENDED = 'SUSPENDED', _('Suspendu')

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name=_("Utilisateur")
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_("Plan")
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default='PENDING',
        verbose_name=_("Statut")
    )
    current_period_start = models.DateTimeField(
        verbose_name=_("Début de la période actuelle")
    )
    current_period_end = models.DateTimeField(
        verbose_name=_("Fin de la période actuelle")
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        verbose_name=_("Annuler à la fin de la période")
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Annulé le")
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Métadonnées")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Abonnement")
        verbose_name_plural = _("Abonnements")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['current_period_end']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.get_status_display()})"

    def is_active(self):
        return self.status == self.Status.ACTIVE

    def days_until_expiration(self):
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0


class Coupon(models.Model):
    """Coupon de réduction"""

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', _('Pourcentage')
        FIXED_AMOUNT = 'FIXED_AMOUNT', _('Montant fixe')
        FREE_SHIPPING = 'FREE_SHIPPING', _('Livraison gratuite')

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Code")
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        verbose_name=_("Type de réduction")
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Valeur de la réduction")
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Devise (pour montant fixe)")
    )
    valid_from = models.DateTimeField(verbose_name=_("Valide à partir de"))
    valid_until = models.DateTimeField(verbose_name=_("Valide jusqu'à"))
    max_uses = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Utilisations maximum")
    )
    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Utilisations")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Actif"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Coupon")
        verbose_name_plural = _("Coupons")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"

    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and
            self.used_count < self.max_uses and
            self.valid_from <= now <= self.valid_until
        )

    def calculate_discount(self, amount, currency='EUR'):
        if not self.is_valid():
            return Decimal('0')

        if self.discount_type == 'PERCENTAGE':
            return amount * (self.discount_value / 100)
        elif self.discount_type == 'FIXED_AMOUNT':
            if self.currency == currency:
                return min(amount, self.discount_value)
            else:
                # Conversion de devise nécessaire
                return Decimal('0')
        return Decimal('0')


class PaymentSession(models.Model):
    """Session de paiement temporaire"""

    session_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("ID de session")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payment_sessions',
        null=True,
        blank=True,
        verbose_name=_("Utilisateur")
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name=_("Montant")
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='EUR',
        verbose_name=_("Devise")
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentTransaction.PaymentMethod.choices,
        verbose_name=_("Méthode de paiement")
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentTransaction.Status.choices,
        default='PENDING',
        verbose_name=_("Statut")
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Métadonnées")
    )
    expires_at = models.DateTimeField(verbose_name=_("Expire à"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Session de paiement")
        verbose_name_plural = _("Sessions de paiement")
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.session_id} - {self.amount} {self.currency}"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def extend(self, minutes=30):
        self.expires_at = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save()


# ============================================================================
# NOUVEAU MODÈLE : Currency (pour views.py)
# ============================================================================

class Currency(models.Model):
    """Modèle pour les devises (pour compatibilité avec views.py)"""

    code = models.CharField(
        max_length=3,
        unique=True,
        verbose_name=_("Code devise")
    )
    name = models.CharField(
        max_length=50,
        verbose_name=_("Nom de la devise")
    )
    symbol = models.CharField(
        max_length=5,
        verbose_name=_("Symbole")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=1.0,
        verbose_name=_("Taux de change")
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Ordre d'affichage")
    )

    class Meta:
        verbose_name = _("Devise")
        verbose_name_plural = _("Devises")
        ordering = ['display_order', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"
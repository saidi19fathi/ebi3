# ~/ebi3/payments/exceptions.py
"""
Exceptions personnalisées pour l'application payments
"""

class PaymentException(Exception):
    """Exception de base pour les paiements"""
    default_message = "Une erreur de paiement est survenue"

    def __init__(self, message=None, **kwargs):
        self.message = message or self.default_message
        self.kwargs = kwargs
        super().__init__(self.message)


class PaymentProcessingError(PaymentException):
    """Erreur lors du traitement d'un paiement"""
    default_message = "Erreur lors du traitement du paiement"


class PaymentValidationError(PaymentException):
    """Erreur de validation des données de paiement"""
    default_message = "Validation des données de paiement échouée"


class PaymentGatewayError(PaymentException):
    """Erreur de la passerelle de paiement"""
    default_message = "Erreur de la passerelle de paiement"

    def __init__(self, gateway=None, **kwargs):
        self.gateway = gateway
        super().__init__(**kwargs)


class StripeError(PaymentGatewayError):
    """Erreur spécifique à Stripe"""
    default_message = "Erreur Stripe"

    def __init__(self, stripe_error=None, **kwargs):
        self.stripe_error = stripe_error
        super().__init__(gateway='stripe', **kwargs)


class PayPalError(PaymentGatewayError):
    """Erreur spécifique à PayPal"""
    default_message = "Erreur PayPal"

    def __init__(self, paypal_error=None, **kwargs):
        self.paypal_error = paypal_error
        super().__init__(gateway='paypal', **kwargs)


class InsufficientFundsError(PaymentException):
    """Fonds insuffisants"""
    default_message = "Fonds insuffisants"


class CardDeclinedError(PaymentException):
    """Carte refusée"""
    default_message = "Carte refusée"

    def __init__(self, decline_code=None, **kwargs):
        self.decline_code = decline_code
        super().__init__(**kwargs)


class ExpiredCardError(CardDeclinedError):
    """Carte expirée"""
    default_message = "Carte expirée"


class InvalidCardError(CardDeclinedError):
    """Carte invalide"""
    default_message = "Carte invalide"


class CVVError(CardDeclinedError):
    """Code CVV incorrect"""
    default_message = "Code de sécurité incorrect"


class TransactionNotFoundError(PaymentException):
    """Transaction non trouvée"""
    default_message = "Transaction non trouvée"


class InvoiceNotFoundError(PaymentException):
    """Facture non trouvée"""
    default_message = "Facture non trouvée"


class RefundNotAllowedError(PaymentException):
    """Remboursement non autorisé"""
    default_message = "Remboursement non autorisé"

    def __init__(self, reason=None, **kwargs):
        self.reason = reason
        super().__init__(**kwargs)


class RefundAmountExceededError(RefundNotAllowedError):
    """Montant de remboursement dépassé"""
    default_message = "Le montant du remboursement dépasse le montant disponible"


class RefundTimeLimitExceededError(RefundNotAllowedError):
    """Délai de remboursement dépassé"""
    default_message = "Le délai de remboursement est dépassé"


class CurrencyMismatchError(PaymentException):
    """Incompatibilité de devises"""
    default_message = "Incompatibilité de devises"

    def __init__(self, expected=None, received=None, **kwargs):
        self.expected = expected
        self.received = received
        super().__init__(**kwargs)


class RateLimitExceededError(PaymentException):
    """Limite de taux dépassée"""
    default_message = "Trop de tentatives. Veuillez réessayer plus tard."

    def __init__(self, retry_after=None, **kwargs):
        self.retry_after = retry_after
        super().__init__(**kwargs)


class WebhookVerificationError(PaymentException):
    """Erreur de vérification du webhook"""
    default_message = "Échec de la vérification du webhook"

    def __init__(self, signature=None, **kwargs):
        self.signature = signature
        super().__init__(**kwargs)


class FraudDetectionError(PaymentException):
    """Détection de fraude"""
    default_message = "Transaction suspecte détectée"

    def __init__(self, risk_level=None, **kwargs):
        self.risk_level = risk_level
        super().__init__(**kwargs)


class SubscriptionError(PaymentException):
    """Erreur d'abonnement"""
    default_message = "Erreur d'abonnement"


class PlanNotFoundError(SubscriptionError):
    """Plan non trouvé"""
    default_message = "Plan d'abonnement non trouvé"


class SubscriptionAlreadyExistsError(SubscriptionError):
    """Abonnement déjà existant"""
    default_message = "Un abonnement actif existe déjà"


class SubscriptionCancelledError(SubscriptionError):
    """Abonnement annulé"""
    default_message = "L'abonnement a été annulé"


class CouponError(PaymentException):
    """Erreur de coupon"""
    default_message = "Erreur de coupon"


class CouponNotFoundError(CouponError):
    """Coupon non trouvé"""
    default_message = "Coupon non trouvé"


class CouponExpiredError(CouponError):
    """Coupon expiré"""
    default_message = "Le coupon a expiré"


class CouponUsageLimitExceededError(CouponError):
    """Limite d'utilisation du coupon dépassée"""
    default_message = "Limite d'utilisation du coupon dépassée"


class TaxCalculationError(PaymentException):
    """Erreur de calcul des taxes"""
    default_message = "Erreur lors du calcul des taxes"


class AddressValidationError(PaymentException):
    """Erreur de validation d'adresse"""
    default_message = "Adresse invalide"


class PaymentSessionExpiredError(PaymentException):
    """Session de paiement expirée"""
    default_message = "La session de paiement a expiré"


class PaymentSessionNotFoundError(PaymentException):
    """Session de paiement non trouvée"""
    default_message = "Session de paiement non trouvée"


class PaymentMethodNotSupportedError(PaymentException):
    """Méthode de paiement non supportée"""
    default_message = "Méthode de paiement non supportée"

    def __init__(self, method=None, **kwargs):
        self.method = method
        super().__init__(**kwargs)


class BankTransferTimeoutError(PaymentException):
    """Timeout du virement bancaire"""
    default_message = "Le virement bancaire a expiré"


class MobilePaymentError(PaymentException):
    """Erreur de paiement mobile"""
    default_message = "Erreur de paiement mobile"


class CryptoPaymentError(PaymentException):
    """Erreur de paiement crypto"""
    default_message = "Erreur de paiement cryptomonnaie"


class PaymentReconciliationError(PaymentException):
    """Erreur de rapprochement de paiement"""
    default_message = "Erreur lors du rapprochement du paiement"


class InvoiceGenerationError(PaymentException):
    """Erreur de génération de facture"""
    default_message = "Erreur lors de la génération de la facture"


class PDFGenerationError(InvoiceGenerationError):
    """Erreur de génération de PDF"""
    default_message = "Erreur lors de la génération du PDF"


class EmailDeliveryError(PaymentException):
    """Erreur d'envoi d'email"""
    default_message = "Erreur lors de l'envoi de l'email"


class DatabaseIntegrityError(PaymentException):
    """Erreur d'intégrité de la base de données"""
    default_message = "Erreur d'intégrité de la base de données"


class PaymentMiddlewareError(PaymentException):
    """Erreur du middleware de paiement"""
    default_message = "Erreur du middleware de paiement"


class PaymentSecurityError(PaymentException):
    """Erreur de sécurité du paiement"""
    default_message = "Erreur de sécurité du paiement"


class PaymentTimeoutError(PaymentException):
    """Timeout du paiement"""
    default_message = "Le paiement a expiré"

    def __init__(self, timeout_seconds=None, **kwargs):
        self.timeout_seconds = timeout_seconds
        super().__init__(**kwargs)


class PartialPaymentError(PaymentException):
    """Erreur de paiement partiel"""
    default_message = "Paiement partiel non autorisé"


class PaymentAlreadyProcessedError(PaymentException):
    """Paiement déjà traité"""
    default_message = "Ce paiement a déjà été traité"


class PaymentCancelledError(PaymentException):
    """Paiement annulé"""
    default_message = "Le paiement a été annulé"


class PaymentRefundedError(PaymentException):
    """Paiement remboursé"""
    default_message = "Le paiement a été remboursé"


class PaymentChargebackError(PaymentException):
    """Contestation de paiement"""
    default_message = "Contestation de paiement reçue"


class PaymentGatewayUnavailableError(PaymentGatewayError):
    """Passerelle de paiement indisponible"""
    default_message = "Passerelle de paiement temporairement indisponible"


class PaymentConfigurationError(PaymentException):
    """Erreur de configuration du paiement"""
    default_message = "Erreur de configuration du paiement"

    def __init__(self, setting=None, **kwargs):
        self.setting = setting
        super().__init__(**kwargs)


class PaymentTestModeError(PaymentException):
    """Erreur en mode test"""
    default_message = "Erreur en mode test - Utilisez des cartes de test"


class PaymentLiveModeRequiredError(PaymentException):
    """Mode live requis"""
    default_message = "Le mode live est requis pour cette opération"


class PaymentTestModeRequiredError(PaymentException):
    """Mode test requis"""
    default_message = "Le mode test est requis pour cette opération"


def handle_payment_exception(exception):
    """
    Gestionnaire centralisé des exceptions de paiement
    """
    from django.contrib import messages
    from django.utils.translation import gettext_lazy as _

    error_messages = {
        'InsufficientFundsError': _("Fonds insuffisants sur votre compte."),
        'CardDeclinedError': _("Votre carte a été refusée. Veuillez contacter votre banque."),
        'ExpiredCardError': _("Votre carte a expiré. Utilisez une autre carte."),
        'InvalidCardError': _("Carte invalide. Vérifiez les informations saisies."),
        'CVVError': _("Code de sécurité incorrect."),
        'PaymentSessionExpiredError': _("Votre session a expiré. Veuillez recommencer."),
        'RateLimitExceededError': _("Trop de tentatives. Réessayez dans quelques minutes."),
        'FraudDetectionError': _("Transaction suspecte détectée. Contactez le support."),
        'PaymentGatewayUnavailableError': _("Service temporairement indisponible. Réessayez plus tard."),
    }

    exception_name = exception.__class__.__name__
    message = error_messages.get(exception_name, str(exception))

    return {
        'error': True,
        'message': message,
        'exception': exception_name,
        'code': getattr(exception, 'code', 'UNKNOWN_ERROR')
    }


class PaymentErrorCodes:
    """Codes d'erreur standardisés pour les paiements"""

    # Erreurs générales
    UNKNOWN_ERROR = 'PAYMENT_UNKNOWN_ERROR'
    VALIDATION_ERROR = 'PAYMENT_VALIDATION_ERROR'
    PROCESSING_ERROR = 'PAYMENT_PROCESSING_ERROR'

    # Erreurs de carte
    CARD_DECLINED = 'CARD_DECLINED'
    EXPIRED_CARD = 'EXPIRED_CARD'
    INVALID_CARD = 'INVALID_CARD'
    INCORRECT_CVV = 'INCORRECT_CVV'
    INSUFFICIENT_FUNDS = 'INSUFFICIENT_FUNDS'

    # Erreurs de sécurité
    FRAUD_DETECTED = 'FRAUD_DETECTED'
    RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
    SECURITY_VIOLATION = 'SECURITY_VIOLATION'

    # Erreurs de session
    SESSION_EXPIRED = 'SESSION_EXPIRED'
    SESSION_INVALID = 'SESSION_INVALID'

    # Erreurs de remboursement
    REFUND_NOT_ALLOWED = 'REFUND_NOT_ALLOWED'
    REFUND_AMOUNT_EXCEEDED = 'REFUND_AMOUNT_EXCEEDED'
    REFUND_TIME_LIMIT_EXCEEDED = 'REFUND_TIME_LIMIT_EXCEEDED'

    # Erreurs d'abonnement
    SUBSCRIPTION_ERROR = 'SUBSCRIPTION_ERROR'
    PLAN_NOT_FOUND = 'PLAN_NOT_FOUND'
    SUBSCRIPTION_EXISTS = 'SUBSCRIPTION_EXISTS'

    # Erreurs de coupon
    COUPON_INVALID = 'COUPON_INVALID'
    COUPON_EXPIRED = 'COUPON_EXPIRED'
    COUPON_LIMIT_EXCEEDED = 'COUPON_LIMIT_EXCEEDED'

    # Erreurs de passerelle
    GATEWAY_ERROR = 'GATEWAY_ERROR'
    GATEWAY_UNAVAILABLE = 'GATEWAY_UNAVAILABLE'
    GATEWAY_TIMEOUT = 'GATEWAY_TIMEOUT'

    # Erreurs de configuration
    CONFIGURATION_ERROR = 'CONFIGURATION_ERROR'
    TEST_MODE_REQUIRED = 'TEST_MODE_REQUIRED'
    LIVE_MODE_REQUIRED = 'LIVE_MODE_REQUIRED'

    # Erreurs de devise
    CURRENCY_MISMATCH = 'CURRENCY_MISMATCH'
    CURRENCY_NOT_SUPPORTED = 'CURRENCY_NOT_SUPPORTED'

    # Erreurs de taxe
    TAX_CALCULATION_ERROR = 'TAX_CALCULATION_ERROR'
    TAX_RATE_INVALID = 'TAX_RATE_INVALID'
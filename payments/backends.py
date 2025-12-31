# ~/ebi3/payments/backends.py
"""
Backends de paiement pour différentes passerelles
"""

import logging
from abc import ABC, abstractmethod
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .exceptions import (
    StripeError, PayPalError, PaymentGatewayError,
    CardDeclinedError, InsufficientFundsError
)

logger = logging.getLogger(__name__)


class PaymentBackend(ABC):
    """Interface de base pour les backends de paiement"""

    def __init__(self, **kwargs):
        self.config = kwargs

    @abstractmethod
    def create_payment_intent(self, amount, currency, **kwargs):
        """Créer une intention de paiement"""
        pass

    @abstractmethod
    def confirm_payment(self, payment_intent_id, **kwargs):
        """Confirmer un paiement"""
        pass

    @abstractmethod
    def refund_payment(self, payment_intent_id, amount=None, **kwargs):
        """Rembourser un paiement"""
        pass

    @abstractmethod
    def get_payment_status(self, payment_intent_id):
        """Obtenir le statut d'un paiement"""
        pass

    @abstractmethod
    def create_customer(self, user_data, **kwargs):
        """Créer un client"""
        pass

    @abstractmethod
    def setup_subscription(self, customer_id, plan_data, **kwargs):
        """Configurer un abonnement"""
        pass

    def validate_amount(self, amount):
        """Valider le montant"""
        if amount <= 0:
            raise ValueError(_("Le montant doit être positif"))
        return amount

    def validate_currency(self, currency):
        """Valider la devise"""
        supported_currencies = getattr(self, 'supported_currencies', ['EUR', 'USD'])
        if currency not in supported_currencies:
            raise ValueError(_(f"Devise non supportée: {currency}"))
        return currency


class StripeBackend(PaymentBackend):
    """Backend Stripe"""

    supported_currencies = ['EUR', 'USD', 'GBP', 'CAD', 'AUD', 'JPY']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import stripe

        # Configuration Stripe
        api_key = kwargs.get('api_key', settings.STRIPE_SECRET_KEY)
        stripe.api_key = api_key

        self.stripe = stripe
        self.webhook_secret = kwargs.get('webhook_secret', settings.STRIPE_WEBHOOK_SECRET)

        logger.info("Stripe backend initialized")

    def create_payment_intent(self, amount, currency, **kwargs):
        """Créer une intention de paiement Stripe"""
        try:
            # Convertir le montant en centimes pour Stripe
            amount_in_cents = int(amount * 100)

            intent_data = {
                'amount': amount_in_cents,
                'currency': currency.lower(),
                'automatic_payment_methods': {
                    'enabled': True,
                },
                'metadata': kwargs.get('metadata', {}),
            }

            # Ajouter le client si fourni
            if 'customer_id' in kwargs:
                intent_data['customer'] = kwargs['customer_id']

            # Ajouter la description
            if 'description' in kwargs:
                intent_data['description'] = kwargs['description']

            # Créer l'intention de paiement
            intent = self.stripe.PaymentIntent.create(**intent_data)

            logger.info(f"Stripe payment intent created: {intent.id}")

            return {
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'status': intent.status,
                'amount': intent.amount / 100,
                'currency': intent.currency.upper(),
                'next_action': intent.get('next_action'),
            }

        except self.stripe.error.CardError as e:
            logger.error(f"Stripe card error: {e.user_message}")
            raise CardDeclinedError(
                message=e.user_message,
                decline_code=e.code,
                stripe_error=e
            )
        except self.stripe.error.RateLimitError as e:
            logger.error(f"Stripe rate limit error: {str(e)}")
            raise PaymentGatewayError(
                message=_("Trop de requêtes. Veuillez réessayer plus tard."),
                gateway='stripe'
            )
        except self.stripe.error.InvalidRequestError as e:
            logger.error(f"Stripe invalid request: {str(e)}")
            raise PaymentGatewayError(
                message=_("Requête invalide."),
                gateway='stripe'
            )
        except self.stripe.error.AuthenticationError as e:
            logger.error(f"Stripe authentication error: {str(e)}")
            raise PaymentGatewayError(
                message=_("Erreur d'authentification Stripe."),
                gateway='stripe'
            )
        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeError(stripe_error=e)
        except Exception as e:
            logger.error(f"Unexpected error creating Stripe payment intent: {str(e)}")
            raise PaymentGatewayError(
                message=_("Erreur inattendue lors de la création du paiement."),
                gateway='stripe'
            )

    def confirm_payment(self, payment_intent_id, **kwargs):
        """Confirmer un paiement Stripe"""
        try:
            intent = self.stripe.PaymentIntent.confirm(
                payment_intent_id,
                **kwargs
            )

            logger.info(f"Stripe payment confirmed: {intent.id}")

            return {
                'payment_intent_id': intent.id,
                'status': intent.status,
                'amount_received': intent.amount_received / 100 if intent.amount_received else 0,
                'currency': intent.currency.upper(),
                'charges': [
                    {
                        'id': charge.id,
                        'amount': charge.amount / 100,
                        'status': charge.status,
                        'payment_method': charge.payment_method_details.type if charge.payment_method_details else None
                    }
                    for charge in intent.charges.data
                ] if intent.charges else []
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {str(e)}")
            raise StripeError(stripe_error=e)

    def refund_payment(self, payment_intent_id, amount=None, **kwargs):
        """Rembourser un paiement Stripe"""
        try:
            # Récupérer le paiement
            intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)

            # Créer le remboursement
            refund_data = {
                'payment_intent': payment_intent_id,
                'metadata': kwargs.get('metadata', {}),
            }

            if amount:
                # Convertir en centimes
                refund_data['amount'] = int(amount * 100)

            if 'reason' in kwargs:
                refund_data['reason'] = kwargs['reason']

            refund = self.stripe.Refund.create(**refund_data)

            logger.info(f"Stripe refund created: {refund.id}")

            return {
                'refund_id': refund.id,
                'amount': refund.amount / 100,
                'currency': refund.currency.upper(),
                'status': refund.status,
                'reason': refund.reason,
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {str(e)}")
            raise StripeError(stripe_error=e)

    def get_payment_status(self, payment_intent_id):
        """Obtenir le statut d'un paiement Stripe"""
        try:
            intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)

            return {
                'payment_intent_id': intent.id,
                'status': intent.status,
                'amount': intent.amount / 100,
                'currency': intent.currency.upper(),
                'charges': [
                    {
                        'id': charge.id,
                        'status': charge.status,
                        'paid': charge.paid,
                        'refunded': charge.refunded,
                        'amount_refunded': charge.amount_refunded / 100,
                    }
                    for charge in intent.charges.data
                ] if intent.charges else []
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving payment: {str(e)}")
            raise StripeError(stripe_error=e)

    def create_customer(self, user_data, **kwargs):
        """Créer un client Stripe"""
        try:
            customer_data = {
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'metadata': {
                    'user_id': str(user_data.get('id')),
                    'username': user_data.get('username'),
                }
            }

            if 'phone' in user_data:
                customer_data['phone'] = user_data['phone']

            if 'address' in user_data:
                customer_data['address'] = user_data['address']

            customer = self.stripe.Customer.create(**customer_data)

            logger.info(f"Stripe customer created: {customer.id}")

            return {
                'customer_id': customer.id,
                'email': customer.email,
                'name': customer.name,
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            raise StripeError(stripe_error=e)

    def setup_subscription(self, customer_id, plan_data, **kwargs):
        """Configurer un abonnement Stripe"""
        try:
            # Créer le produit et le prix si nécessaire
            product = self.stripe.Product.create(
                name=plan_data['name'],
                description=plan_data.get('description', ''),
            )

            price = self.stripe.Price.create(
                product=product.id,
                unit_amount=int(plan_data['price'] * 100),
                currency=plan_data.get('currency', 'eur').lower(),
                recurring={
                    'interval': plan_data.get('interval', 'month'),
                    'interval_count': plan_data.get('interval_count', 1),
                },
            )

            # Créer l'abonnement
            subscription_data = {
                'customer': customer_id,
                'items': [{'price': price.id}],
                'payment_behavior': 'default_incomplete',
                'expand': ['latest_invoice.payment_intent'],
            }

            if 'trial_period_days' in kwargs:
                subscription_data['trial_period_days'] = kwargs['trial_period_days']

            subscription = self.stripe.Subscription.create(**subscription_data)

            logger.info(f"Stripe subscription created: {subscription.id}")

            return {
                'subscription_id': subscription.id,
                'status': subscription.status,
                'current_period_start': subscription.current_period_start,
                'current_period_end': subscription.current_period_end,
                'latest_invoice': {
                    'id': subscription.latest_invoice.id,
                    'payment_intent': {
                        'id': subscription.latest_invoice.payment_intent.id,
                        'client_secret': subscription.latest_invoice.payment_intent.client_secret,
                    } if subscription.latest_invoice.payment_intent else None,
                } if subscription.latest_invoice else None,
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error setting up subscription: {str(e)}")
            raise StripeError(stripe_error=e)

    def verify_webhook(self, payload, signature):
        """Vérifier la signature d'un webhook Stripe"""
        try:
            event = self.stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return event
        except self.stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook signature verification failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error verifying Stripe webhook: {str(e)}")
            raise

    def create_checkout_session(self, success_url, cancel_url, **kwargs):
        """Créer une session de checkout Stripe"""
        try:
            session_data = {
                'success_url': success_url,
                'cancel_url': cancel_url,
                'mode': kwargs.get('mode', 'payment'),
                'payment_method_types': kwargs.get('payment_method_types', ['card']),
                'client_reference_id': kwargs.get('client_reference_id'),
                'metadata': kwargs.get('metadata', {}),
            }

            if kwargs.get('mode') == 'payment':
                session_data['line_items'] = [{
                    'price_data': {
                        'currency': kwargs.get('currency', 'eur').lower(),
                        'product_data': {
                            'name': kwargs.get('name', 'Purchase'),
                            'description': kwargs.get('description', ''),
                        },
                        'unit_amount': int(kwargs['amount'] * 100),
                    },
                    'quantity': kwargs.get('quantity', 1),
                }]

            elif kwargs.get('mode') == 'subscription':
                session_data['line_items'] = [{
                    'price': kwargs['price_id'],
                    'quantity': kwargs.get('quantity', 1),
                }]

            if 'customer_id' in kwargs:
                session_data['customer'] = kwargs['customer_id']
            elif 'customer_email' in kwargs:
                session_data['customer_email'] = kwargs['customer_email']

            session = self.stripe.checkout.Session.create(**session_data)

            logger.info(f"Stripe checkout session created: {session.id}")

            return {
                'session_id': session.id,
                'url': session.url,
                'payment_intent': session.payment_intent if hasattr(session, 'payment_intent') else None,
                'subscription': session.subscription if hasattr(session, 'subscription') else None,
            }

        except self.stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {str(e)}")
            raise StripeError(stripe_error=e)


class PayPalBackend(PaymentBackend):
    """Backend PayPal"""

    supported_currencies = ['EUR', 'USD', 'GBP', 'CAD', 'AUD']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment

        # Configuration PayPal
        client_id = kwargs.get('client_id', settings.PAYPAL_CLIENT_ID)
        client_secret = kwargs.get('client_secret', settings.PAYPAL_CLIENT_SECRET)
        environment = kwargs.get('environment', settings.PAYPAL_ENVIRONMENT)

        if environment == 'sandbox':
            paypal_environment = SandboxEnvironment(
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            paypal_environment = LiveEnvironment(
                client_id=client_id,
                client_secret=client_secret
            )

        self.client = PayPalHttpClient(paypal_environment)
        self.environment = environment

        logger.info(f"PayPal backend initialized ({environment})")

    def create_payment_intent(self, amount, currency, **kwargs):
        """Créer une intention de paiement PayPal"""
        try:
            from paypalcheckoutsdk.orders import OrdersCreateRequest

            request = OrdersCreateRequest()
            request.prefer('return=representation')

            request.request_body({
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": currency.upper(),
                            "value": str(amount)
                        },
                        "description": kwargs.get('description', ''),
                        "custom_id": kwargs.get('custom_id'),
                    }
                ],
                "application_context": {
                    "return_url": kwargs.get('return_url'),
                    "cancel_url": kwargs.get('cancel_url'),
                    "brand_name": kwargs.get('brand_name', settings.SITE_NAME),
                    "user_action": "PAY_NOW",
                }
            })

            response = self.client.execute(request)
            order = response.result

            logger.info(f"PayPal order created: {order.id}")

            return {
                'order_id': order.id,
                'status': order.status,
                'amount': amount,
                'currency': currency,
                'approval_url': next(
                    link.href for link in order.links if link.rel == 'approve'
                ),
            }

        except Exception as e:
            logger.error(f"PayPal error creating order: {str(e)}")
            raise PayPalError(paypal_error=e)

    def confirm_payment(self, order_id, **kwargs):
        """Confirmer un paiement PayPal"""
        try:
            from paypalcheckoutsdk.orders import OrdersCaptureRequest

            request = OrdersCaptureRequest(order_id)
            response = self.client.execute(request)
            capture = response.result

            logger.info(f"PayPal order captured: {capture.id}")

            return {
                'order_id': capture.id,
                'status': capture.status,
                'amount': float(capture.purchase_units[0].payments.captures[0].amount.value),
                'currency': capture.purchase_units[0].payments.captures[0].amount.currency_code,
            }

        except Exception as e:
            logger.error(f"PayPal error capturing order: {str(e)}")
            raise PayPalError(paypal_error=e)

    def refund_payment(self, capture_id, amount=None, **kwargs):
        """Rembourser un paiement PayPal"""
        try:
            from paypalcheckoutsdk.payments import CapturesRefundRequest

            request = CapturesRefundRequest(capture_id)
            request.prefer('return=representation')

            refund_data = {}
            if amount:
                refund_data['amount'] = {
                    'value': str(amount),
                    'currency_code': kwargs.get('currency', 'EUR')
                }

            if 'note' in kwargs:
                refund_data['note_to_payer'] = kwargs['note']

            request.request_body(refund_data)

            response = self.client.execute(request)
            refund = response.result

            logger.info(f"PayPal refund created: {refund.id}")

            return {
                'refund_id': refund.id,
                'amount': float(refund.amount.value),
                'currency': refund.amount.currency_code,
                'status': refund.status,
            }

        except Exception as e:
            logger.error(f"PayPal error creating refund: {str(e)}")
            raise PayPalError(paypal_error=e)

    def get_payment_status(self, order_id):
        """Obtenir le statut d'un paiement PayPal"""
        try:
            from paypalcheckoutsdk.orders import OrdersGetRequest

            request = OrdersGetRequest(order_id)
            response = self.client.execute(request)
            order = response.result

            return {
                'order_id': order.id,
                'status': order.status,
                'amount': float(order.purchase_units[0].amount.value),
                'currency': order.purchase_units[0].amount.currency_code,
            }

        except Exception as e:
            logger.error(f"PayPal error getting order: {str(e)}")
            raise PayPalError(paypal_error=e)

    def create_customer(self, user_data, **kwargs):
        """Créer un client PayPal (pour les abonnements)"""
        # PayPal n'a pas de concept de client comme Stripe
        # On retourne un identifiant basé sur l'email
        return {
            'customer_id': f"paypal_{user_data.get('email')}",
            'email': user_data.get('email'),
            'name': user_data.get('name'),
        }

    def setup_subscription(self, customer_id, plan_data, **kwargs):
        """Configurer un abonnement PayPal"""
        try:
            from paypalcheckoutsdk.subscriptions import SubscriptionsCreateRequest

            request = SubscriptionsCreateRequest()
            request.prefer('return=representation')

            subscription_data = {
                "plan_id": plan_data['plan_id'],
                "start_time": kwargs.get('start_time'),
                "quantity": kwargs.get('quantity', '1'),
                "shipping_amount": {
                    "currency_code": plan_data.get('currency', 'EUR'),
                    "value": "0"
                },
                "subscriber": {
                    "name": {
                        "given_name": kwargs.get('first_name'),
                        "surname": kwargs.get('last_name')
                    },
                    "email_address": kwargs.get('email'),
                    "shipping_address": kwargs.get('shipping_address', {})
                },
                "application_context": {
                    "brand_name": kwargs.get('brand_name', settings.SITE_NAME),
                    "locale": kwargs.get('locale', 'fr-FR'),
                    "shipping_preference": "SET_PROVIDED_ADDRESS",
                    "user_action": "SUBSCRIBE_NOW",
                    "payment_method": {
                        "payer_selected": "PAYPAL",
                        "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED"
                    },
                    "return_url": kwargs.get('return_url'),
                    "cancel_url": kwargs.get('cancel_url')
                }
            }

            request.request_body(subscription_data)
            response = self.client.execute(request)
            subscription = response.result

            logger.info(f"PayPal subscription created: {subscription.id}")

            return {
                'subscription_id': subscription.id,
                'status': subscription.status,
                'approval_url': next(
                    link.href for link in subscription.links if link.rel == 'approve'
                ),
            }

        except Exception as e:
            logger.error(f"PayPal error setting up subscription: {str(e)}")
            raise PayPalError(paypal_error=e)

    def verify_webhook(self, payload, signature, transmission_id):
        """Vérifier un webhook PayPal"""
        try:
            from paypalcheckoutsdk.core import PayPalWebhookEvent

            # Vérification de la signature PayPal
            # Cette logique dépend de la configuration PayPal
            event = PayPalWebhookEvent(payload, transmission_id, signature)

            return event
        except Exception as e:
            logger.error(f"PayPal webhook verification failed: {str(e)}")
            raise


class BankTransferBackend(PaymentBackend):
    """Backend pour virements bancaires"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bank_details = kwargs.get('bank_details', {
            'bank_name': settings.BANK_NAME,
            'account_holder': settings.BANK_ACCOUNT_HOLDER,
            'iban': settings.BANK_IBAN,
            'bic': settings.BANK_BIC,
        })

        logger.info("Bank transfer backend initialized")

    def create_payment_intent(self, amount, currency, **kwargs):
        """Créer une intention de paiement pour virement"""
        reference = kwargs.get('reference', f"PAY-{kwargs.get('user_id', '000000')}")

        return {
            'payment_intent_id': reference,
            'status': 'PENDING',
            'amount': amount,
            'currency': currency,
            'bank_details': self.bank_details,
            'reference': reference,
            'instructions': _(
                "Veuillez effectuer un virement bancaire avec la référence ci-dessus. "
                "Votre paiement sera confirmé manuellement après réception des fonds."
            ),
        }

    def confirm_payment(self, payment_intent_id, **kwargs):
        """Confirmer un virement (manuellement)"""
        return {
            'payment_intent_id': payment_intent_id,
            'status': 'MANUAL_CONFIRMATION_REQUIRED',
            'message': _("Le virement doit être confirmé manuellement par un administrateur."),
        }

    def refund_payment(self, payment_intent_id, amount=None, **kwargs):
        """Rembourser un virement"""
        return {
            'refund_id': f"REFUND-{payment_intent_id}",
            'status': 'MANUAL_PROCESSING_REQUIRED',
            'message': _("Le remboursement nécessite un traitement manuel."),
        }

    def get_payment_status(self, payment_intent_id):
        """Obtenir le statut d'un virement"""
        return {
            'payment_intent_id': payment_intent_id,
            'status': 'PENDING',
            'message': _("En attente de virement bancaire."),
        }

    def create_customer(self, user_data, **kwargs):
        """Créer un client pour virement"""
        return {
            'customer_id': f"BANK_{user_data.get('id', '000000')}",
            'name': user_data.get('name'),
            'email': user_data.get('email'),
        }

    def setup_subscription(self, customer_id, plan_data, **kwargs):
        """Les virements ne supportent pas les abonnements"""
        raise PaymentGatewayError(
            message=_("Les abonnements ne sont pas supportés pour les virements bancaires."),
            gateway='bank_transfer'
        )


class PaymentBackendFactory:
    """Factory pour créer les backends de paiement"""

    @staticmethod
    def get_backend(backend_name, **kwargs):
        """
        Récupérer un backend de paiement par nom

        Args:
            backend_name: Nom du backend ('stripe', 'paypal', 'bank_transfer')
            **kwargs: Arguments de configuration

        Returns:
            PaymentBackend instance
        """
        backends = {
            'stripe': StripeBackend,
            'paypal': PayPalBackend,
            'bank_transfer': BankTransferBackend,
        }

        backend_class = backends.get(backend_name.lower())

        if not backend_class:
            raise ValueError(_(f"Backend de paiement inconnu: {backend_name}"))

        return backend_class(**kwargs)

    @staticmethod
    def get_available_backends():
        """Obtenir la liste des backends disponibles"""
        return [
            {
                'name': 'stripe',
                'display_name': 'Stripe',
                'currencies': StripeBackend.supported_currencies,
                'supports_subscriptions': True,
                'supports_refunds': True,
            },
            {
                'name': 'paypal',
                'display_name': 'PayPal',
                'currencies': PayPalBackend.supported_currencies,
                'supports_subscriptions': True,
                'supports_refunds': True,
            },
            {
                'name': 'bank_transfer',
                'display_name': 'Virement Bancaire',
                'currencies': ['EUR', 'USD', 'GBP'],
                'supports_subscriptions': False,
                'supports_refunds': True,
            },
        ]

    @staticmethod
    def get_default_backend():
        """Obtenir le backend par défaut"""
        default_backend = getattr(settings, 'DEFAULT_PAYMENT_BACKEND', 'stripe')
        return PaymentBackendFactory.get_backend(default_backend)
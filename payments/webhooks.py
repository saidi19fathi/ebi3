# ~/ebi3/payments/webhooks.py
"""
Gestion des webhooks pour les paiements
"""

import logging
import json
import hmac
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .exceptions import WebhookVerificationError
from .models import Transaction, Invoice, Refund, Subscription
from .backends import PaymentBackendFactory
from .tasks import (
    notify_transaction_completed,
    generate_invoice_pdf_task,
    send_invoice_email
)

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Gestionnaire de base pour les webhooks"""

    def __init__(self, backend_name):
        self.backend_name = backend_name
        self.backend = PaymentBackendFactory.get_backend(backend_name)

    def verify_signature(self, payload, signature, headers=None):
        """Vérifier la signature du webhook"""
        raise NotImplementedError

    def handle_event(self, event):
        """Traiter un événement de webhook"""
        raise NotImplementedError


class StripeWebhookHandler(WebhookHandler):
    """Gestionnaire de webhooks Stripe"""

    def __init__(self):
        super().__init__('stripe')

    def verify_signature(self, payload, signature, headers=None):
        """Vérifier la signature Stripe"""
        try:
            event = self.backend.verify_webhook(payload, signature)
            return event
        except Exception as e:
            logger.error(f"Stripe webhook signature verification failed: {str(e)}")
            raise WebhookVerificationError(
                message="Signature verification failed",
                signature=signature
            )

    def handle_event(self, event):
        """Traiter un événement Stripe"""
        event_type = event['type']
        event_data = event['data']['object']

        logger.info(f"Processing Stripe webhook: {event_type}")

        handlers = {
            'payment_intent.succeeded': self._handle_payment_intent_succeeded,
            'payment_intent.payment_failed': self._handle_payment_intent_failed,
            'payment_intent.canceled': self._handle_payment_intent_canceled,
            'charge.refunded': self._handle_charge_refunded,
            'charge.dispute.created': self._handle_charge_dispute_created,
            'invoice.payment_succeeded': self._handle_invoice_payment_succeeded,
            'invoice.payment_failed': self._handle_invoice_payment_failed,
            'customer.subscription.created': self._handle_subscription_created,
            'customer.subscription.updated': self._handle_subscription_updated,
            'customer.subscription.deleted': self._handle_subscription_deleted,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(event_data)

        logger.debug(f"Unhandled Stripe event type: {event_type}")
        return {'status': 'unhandled', 'event_type': event_type}

    def _handle_payment_intent_succeeded(self, payment_intent):
        """Traiter un paiement réussi"""
        try:
            with transaction.atomic():
                # Trouver la transaction
                transaction_obj = Transaction.objects.filter(
                    transaction_id=payment_intent['id']
                ).first()

                if not transaction_obj:
                    logger.warning(f"Transaction not found for payment intent: {payment_intent['id']}")
                    return {'status': 'transaction_not_found'}

                # Mettre à jour la transaction
                transaction_obj.status = 'COMPLETED'
                transaction_obj.processed_at = timezone.now()
                transaction_obj.gateway_response = json.dumps(payment_intent)
                transaction_obj.save()

                # Créer une facture
                invoice = Invoice.objects.create(
                    user=transaction_obj.user,
                    transaction=transaction_obj,
                    amount=transaction_obj.amount,
                    currency=transaction_obj.currency,
                    status='PAID',
                    invoice_number=Invoice.generate_invoice_number(),
                    due_date=timezone.now().date(),
                    paid_at=timezone.now()
                )

                logger.info(f"Payment succeeded: Transaction {transaction_obj.id}, Invoice {invoice.invoice_number}")

                # Tâches asynchrones
                notify_transaction_completed.delay(transaction_obj.id)
                generate_invoice_pdf_task.delay(invoice.id)

                return {
                    'status': 'success',
                    'transaction_id': transaction_obj.id,
                    'invoice_id': invoice.id
                }

        except Exception as e:
            logger.error(f"Error handling payment intent succeeded: {str(e)}")
            raise

    def _handle_payment_intent_failed(self, payment_intent):
        """Traiter un paiement échoué"""
        try:
            transaction_obj = Transaction.objects.filter(
                transaction_id=payment_intent['id']
            ).first()

            if transaction_obj:
                transaction_obj.status = 'FAILED'
                transaction_obj.gateway_response = json.dumps(payment_intent)
                transaction_obj.save()

                logger.info(f"Payment failed: Transaction {transaction_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling payment intent failed: {str(e)}")
            raise

    def _handle_payment_intent_canceled(self, payment_intent):
        """Traiter un paiement annulé"""
        try:
            transaction_obj = Transaction.objects.filter(
                transaction_id=payment_intent['id']
            ).first()

            if transaction_obj:
                transaction_obj.status = 'CANCELED'
                transaction_obj.gateway_response = json.dumps(payment_intent)
                transaction_obj.save()

                logger.info(f"Payment canceled: Transaction {transaction_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling payment intent canceled: {str(e)}")
            raise

    def _handle_charge_refunded(self, charge):
        """Traiter un remboursement"""
        try:
            with transaction.atomic():
                # Trouver la transaction originale
                transaction_obj = Transaction.objects.filter(
                    transaction_id=charge['payment_intent']
                ).first()

                if not transaction_obj:
                    logger.warning(f"Original transaction not found for refund: {charge['id']}")
                    return {'status': 'transaction_not_found'}

                # Créer un enregistrement de remboursement
                refund_amount = charge['amount_refunded'] / 100

                refund = Refund.objects.create(
                    transaction=transaction_obj,
                    amount=refund_amount,
                    currency=transaction_obj.currency,
                    reason='PROCESSOR_REFUND',
                    status='COMPLETED',
                    gateway_refund_id=charge['id'],
                    processed_at=timezone.now()
                )

                # Mettre à jour la transaction
                transaction_obj.refunded_amount = refund_amount
                transaction_obj.save()

                logger.info(f"Refund processed: Transaction {transaction_obj.id}, Refund {refund.id}")

                return {
                    'status': 'success',
                    'refund_id': refund.id,
                    'amount': refund_amount
                }

        except Exception as e:
            logger.error(f"Error handling charge refunded: {str(e)}")
            raise

    def _handle_charge_dispute_created(self, dispute):
        """Traiter une contestation (chargeback)"""
        try:
            transaction_obj = Transaction.objects.filter(
                transaction_id=dispute['payment_intent']
            ).first()

            if transaction_obj:
                transaction_obj.has_chargeback = True
                transaction_obj.chargeback_reason = dispute.get('reason', 'unknown')
                transaction_obj.save()

                logger.warning(f"Chargeback created: Transaction {transaction_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling charge dispute: {str(e)}")
            raise

    def _handle_invoice_payment_succeeded(self, invoice):
        """Traiter une facture payée (abonnement)"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return {'status': 'no_subscription'}

            # Trouver l'abonnement
            subscription = Subscription.objects.filter(
                gateway_subscription_id=subscription_id
            ).first()

            if subscription:
                # Créer une transaction pour le paiement de l'abonnement
                transaction_obj = Transaction.objects.create(
                    user=subscription.user,
                    amount=invoice['amount_paid'] / 100,
                    currency=invoice['currency'].upper(),
                    payment_method='CREDIT_CARD',
                    purpose='SUBSCRIPTION_PAYMENT',
                    status='COMPLETED',
                    transaction_id=invoice.get('payment_intent'),
                    gateway_response=json.dumps(invoice),
                    processed_at=timezone.now()
                )

                # Mettre à jour l'abonnement
                subscription.last_payment_date = timezone.now().date()
                subscription.next_billing_date = timezone.datetime.fromtimestamp(
                    invoice.get('lines', {}).get('data', [{}])[0].get('period', {}).get('end', 0)
                ).date() if invoice.get('lines') else None
                subscription.save()

                logger.info(f"Subscription payment succeeded: Subscription {subscription.id}, Transaction {transaction_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling invoice payment: {str(e)}")
            raise

    def _handle_invoice_payment_failed(self, invoice):
        """Traiter un échec de paiement de facture"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return {'status': 'no_subscription'}

            subscription = Subscription.objects.filter(
                gateway_subscription_id=subscription_id
            ).first()

            if subscription:
                subscription.status = 'PAST_DUE'
                subscription.save()

                logger.warning(f"Subscription payment failed: Subscription {subscription.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling invoice payment failed: {str(e)}")
            raise

    def _handle_subscription_created(self, subscription_data):
        """Traiter la création d'un abonnement"""
        try:
            # Cette logique dépend de votre implémentation d'abonnement
            logger.info(f"Subscription created: {subscription_data['id']}")
            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling subscription created: {str(e)}")
            raise

    def _handle_subscription_updated(self, subscription_data):
        """Traiter la mise à jour d'un abonnement"""
        try:
            subscription = Subscription.objects.filter(
                gateway_subscription_id=subscription_data['id']
            ).first()

            if subscription:
                subscription.status = subscription_data['status'].upper()
                subscription.save()

                logger.info(f"Subscription updated: {subscription.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling subscription updated: {str(e)}")
            raise

    def _handle_subscription_deleted(self, subscription_data):
        """Traiter la suppression d'un abonnement"""
        try:
            subscription = Subscription.objects.filter(
                gateway_subscription_id=subscription_data['id']
            ).first()

            if subscription:
                subscription.status = 'CANCELED'
                subscription.canceled_at = timezone.now()
                subscription.save()

                logger.info(f"Subscription canceled: {subscription.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling subscription deleted: {str(e)}")
            raise


class PayPalWebhookHandler(WebhookHandler):
    """Gestionnaire de webhooks PayPal"""

    def __init__(self):
        super().__init__('paypal')

    def verify_signature(self, payload, signature, headers=None):
        """Vérifier la signature PayPal"""
        # PayPal utilise un header spécifique pour la transmission ID
        transmission_id = headers.get('PAYPAL-TRANSMISSION-ID') if headers else None

        if not transmission_id:
            raise WebhookVerificationError(message="Missing PayPal transmission ID")

        try:
            event = self.backend.verify_webhook(payload, signature, transmission_id)
            return event
        except Exception as e:
            logger.error(f"PayPal webhook verification failed: {str(e)}")
            raise WebhookVerificationError(
                message="Signature verification failed",
                signature=signature
            )

    def handle_event(self, event):
        """Traiter un événement PayPal"""
        event_type = event.get('event_type')

        logger.info(f"Processing PayPal webhook: {event_type}")

        handlers = {
            'PAYMENT.CAPTURE.COMPLETED': self._handle_payment_capture_completed,
            'PAYMENT.CAPTURE.DENIED': self._handle_payment_capture_denied,
            'PAYMENT.CAPTURE.REFUNDED': self._handle_payment_capture_refunded,
            'PAYMENT.CAPTURE.REVERSED': self._handle_payment_capture_reversed,
            'BILLING.SUBSCRIPTION.ACTIVATED': self._handle_subscription_activated,
            'BILLING.SUBSCRIPTION.CANCELLED': self._handle_subscription_cancelled,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(event.get('resource', {}))

        logger.debug(f"Unhandled PayPal event type: {event_type}")
        return {'status': 'unhandled', 'event_type': event_type}

    def _handle_payment_capture_completed(self, capture):
        """Traiter un paiement capturé"""
        try:
            with transaction.atomic():
                # Trouver la transaction
                transaction_obj = Transaction.objects.filter(
                    transaction_id=capture.get('id')
                ).first()

                if not transaction_obj:
                    logger.warning(f"Transaction not found for PayPal capture: {capture.get('id')}")
                    return {'status': 'transaction_not_found'}

                # Mettre à jour la transaction
                transaction_obj.status = 'COMPLETED'
                transaction_obj.processed_at = timezone.now()
                transaction_obj.gateway_response = json.dumps(capture)
                transaction_obj.save()

                # Créer une facture
                invoice = Invoice.objects.create(
                    user=transaction_obj.user,
                    transaction=transaction_obj,
                    amount=float(capture.get('amount', {}).get('value', 0)),
                    currency=capture.get('amount', {}).get('currency_code', 'EUR'),
                    status='PAID',
                    invoice_number=Invoice.generate_invoice_number(),
                    due_date=timezone.now().date(),
                    paid_at=timezone.now()
                )

                logger.info(f"PayPal payment completed: Transaction {transaction_obj.id}")

                # Tâches asynchrones
                notify_transaction_completed.delay(transaction_obj.id)
                generate_invoice_pdf_task.delay(invoice.id)

                return {
                    'status': 'success',
                    'transaction_id': transaction_obj.id,
                    'invoice_id': invoice.id
                }

        except Exception as e:
            logger.error(f"Error handling PayPal payment completed: {str(e)}")
            raise

    def _handle_payment_capture_denied(self, capture):
        """Traiter un paiement refusé"""
        try:
            transaction_obj = Transaction.objects.filter(
                transaction_id=capture.get('id')
            ).first()

            if transaction_obj:
                transaction_obj.status = 'FAILED'
                transaction_obj.gateway_response = json.dumps(capture)
                transaction_obj.save()

                logger.info(f"PayPal payment denied: Transaction {transaction_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling PayPal payment denied: {str(e)}")
            raise

    def _handle_payment_capture_refunded(self, refund):
        """Traiter un remboursement PayPal"""
        try:
            with transaction.atomic():
                # Trouver la capture originale
                capture_id = refund.get('capture_id')
                transaction_obj = Transaction.objects.filter(
                    transaction_id=capture_id
                ).first()

                if not transaction_obj:
                    logger.warning(f"Original transaction not found for PayPal refund: {capture_id}")
                    return {'status': 'transaction_not_found'}

                # Créer un enregistrement de remboursement
                refund_amount = float(refund.get('amount', {}).get('value', 0))

                refund_obj = Refund.objects.create(
                    transaction=transaction_obj,
                    amount=refund_amount,
                    currency=refund.get('amount', {}).get('currency_code', 'EUR'),
                    reason='PROCESSOR_REFUND',
                    status='COMPLETED',
                    gateway_refund_id=refund.get('id'),
                    processed_at=timezone.now()
                )

                # Mettre à jour la transaction
                transaction_obj.refunded_amount = refund_amount
                transaction_obj.save()

                logger.info(f"PayPal refund processed: Transaction {transaction_obj.id}")

                return {
                    'status': 'success',
                    'refund_id': refund_obj.id,
                    'amount': refund_amount
                }

        except Exception as e:
            logger.error(f"Error handling PayPal refund: {str(e)}")
            raise

    def _handle_payment_capture_reversed(self, capture):
        """Traiter un paiement annulé"""
        try:
            transaction_obj = Transaction.objects.filter(
                transaction_id=capture.get('id')
            ).first()

            if transaction_obj:
                transaction_obj.status = 'REVERSED'
                transaction_obj.gateway_response = json.dumps(capture)
                transaction_obj.save()

                logger.info(f"PayPal payment reversed: Transaction {transaction_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling PayPal payment reversed: {str(e)}")
            raise

    def _handle_subscription_activated(self, subscription):
        """Traiter l'activation d'un abonnement"""
        try:
            subscription_id = subscription.get('id')
            subscription_obj = Subscription.objects.filter(
                gateway_subscription_id=subscription_id
            ).first()

            if subscription_obj:
                subscription_obj.status = 'ACTIVE'
                subscription_obj.save()

                logger.info(f"PayPal subscription activated: {subscription_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling PayPal subscription activated: {str(e)}")
            raise

    def _handle_subscription_cancelled(self, subscription):
        """Traiter l'annulation d'un abonnement"""
        try:
            subscription_id = subscription.get('id')
            subscription_obj = Subscription.objects.filter(
                gateway_subscription_id=subscription_id
            ).first()

            if subscription_obj:
                subscription_obj.status = 'CANCELED'
                subscription_obj.canceled_at = timezone.now()
                subscription_obj.save()

                logger.info(f"PayPal subscription canceled: {subscription_obj.id}")

            return {'status': 'handled'}

        except Exception as e:
            logger.error(f"Error handling PayPal subscription canceled: {str(e)}")
            raise


class CustomWebhookHandler(WebhookHandler):
    """Gestionnaire de webhooks personnalisés"""

    def verify_signature(self, payload, signature, headers=None):
        """Vérifier la signature avec HMAC"""
        secret = getattr(settings, 'CUSTOM_WEBHOOK_SECRET', '')

        if not secret:
            logger.warning("Custom webhook secret not configured")
            return payload

        # Calculer le HMAC
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise WebhookVerificationError(
                message="HMAC signature verification failed",
                signature=signature
            )

        return json.loads(payload)

    def handle_event(self, event):
        """Traiter un événement personnalisé"""
        event_type = event.get('type')

        logger.info(f"Processing custom webhook: {event_type}")

        # Logique de traitement personnalisée
        # À adapter selon vos besoins

        return {'status': 'handled', 'event_type': event_type}


class WebhookView(View):
    """Vue de base pour les webhooks"""

    @method_decorator(csrf_exempt)
    @method_decorator(require_POST)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_handler(self):
        """Obtenir le gestionnaire de webhook approprié"""
        raise NotImplementedError

    def post(self, request, *args, **kwargs):
        """Traiter un webhook POST"""
        try:
            # Récupérer les données
            payload = request.body.decode('utf-8')
            signature = request.headers.get('Stripe-Signature') or \
                       request.headers.get('PAYPAL-AUTH-ALGO') or \
                       request.headers.get('X-Signature') or \
                       request.headers.get('Signature', '')

            # Obtenir le gestionnaire
            handler = self.get_handler()

            # Vérifier la signature
            event = handler.verify_signature(payload, signature, request.headers)

            # Traiter l'événement
            result = handler.handle_event(event)

            logger.info(f"Webhook processed successfully: {result}")

            return JsonResponse({'status': 'success', 'result': result})

        except WebhookVerificationError as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({'error': 'Invalid signature'}, status=400)
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)


class StripeWebhookView(WebhookView):
    """Vue pour les webhooks Stripe"""

    def get_handler(self):
        return StripeWebhookHandler()


class PayPalWebhookView(WebhookView):
    """Vue pour les webhooks PayPal"""

    def get_handler(self):
        return PayPalWebhookHandler()


class CustomWebhookView(WebhookView):
    """Vue pour les webhooks personnalisés"""

    def get_handler(self):
        return CustomWebhookHandler()


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Endpoint webhook Stripe"""
    view = StripeWebhookView()
    return view.post(request)


@csrf_exempt
@require_POST
def paypal_webhook(request):
    """Endpoint webhook PayPal"""
    view = PayPalWebhookView()
    return view.post(request)


@csrf_exempt
@require_POST
def custom_webhook(request):
    """Endpoint webhook personnalisé"""
    view = CustomWebhookView()
    return view.post(request)


def test_webhook(request):
    """Endpoint de test pour les webhooks (développement uniquement)"""
    if not settings.DEBUG:
        return JsonResponse({'error': 'Not available in production'}, status=403)

    # Simuler un événement de test
    test_event = {
        'type': 'payment_intent.succeeded',
        'data': {
            'object': {
                'id': 'test_pi_123',
                'amount': 1000,
                'currency': 'eur',
                'status': 'succeeded',
            }
        }
    }

    handler = StripeWebhookHandler()
    result = handler.handle_event(test_event)

    return JsonResponse({
        'status': 'test_completed',
        'result': result
    })
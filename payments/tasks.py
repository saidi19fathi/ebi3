# ~/ebi3/payments/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import logging
from datetime import timedelta

from .models import Transaction, Invoice
from .utils import generate_invoice_pdf

logger = logging.getLogger(__name__)

@shared_task
def process_pending_transactions():
    """
    Tâche périodique pour traiter les transactions en attente
    et mettre à jour leur statut si nécessaire.
    """
    try:
        # Transactions en attente depuis plus de 30 minutes
        cutoff_time = timezone.now() - timedelta(minutes=30)
        pending_transactions = Transaction.objects.filter(
            status='PENDING',
            created_at__lt=cutoff_time
        ).exclude(payment_method__in=['CASH', 'BANK_TRANSFER'])

        for transaction in pending_transactions:
            transaction.status = 'EXPIRED'
            transaction.save(update_fields=['status'])

            # Envoyer une notification
            notify_transaction_expired.delay(transaction.id)

        logger.info(f"Processed {pending_transactions.count()} expired transactions")
        return f"Processed {pending_transactions.count()} expired transactions"

    except Exception as e:
        logger.error(f"Error processing pending transactions: {str(e)}")
        raise

@shared_task
def generate_invoice_pdf_task(invoice_id):
    """
    Générer un PDF d'invoice en arrière-plan
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        pdf_path = generate_invoice_pdf(invoice)

        invoice.invoice_pdf = pdf_path
        invoice.save(update_fields=['invoice_pdf'])

        logger.info(f"Invoice PDF generated for invoice {invoice.invoice_number}")
        return pdf_path

    except Invoice.DoesNotExist:
        logger.error(f"Invoice with id {invoice_id} does not exist")
        return None
    except Exception as e:
        logger.error(f"Error generating invoice PDF: {str(e)}")
        raise

@shared_task
def notify_transaction_created(transaction_id):
    """
    Envoyer une notification par email lorsqu'une transaction est créée
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        context = {
            'transaction': transaction,
            'user': transaction.user,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
        }

        # Email au vendeur
        if transaction.user and transaction.user.email:
            seller_subject = _("Nouvelle transaction créée - {site_name}").format(
                site_name=settings.SITE_NAME
            )
            seller_message = render_to_string(
                'payments/emails/transaction_created_seller.html',
                context
            )

            send_mail(
                subject=seller_subject,
                message=seller_subject,
                html_message=seller_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.user.email],
                fail_silently=True
            )

        # Email à l'acheteur (si différent du vendeur)
        if hasattr(transaction, 'ad') and transaction.ad.seller.email:
            if transaction.user != transaction.ad.seller:
                buyer_subject = _("Votre paiement a été initié - {site_name}").format(
                    site_name=settings.SITE_NAME
                )
                buyer_message = render_to_string(
                    'payments/emails/transaction_created_buyer.html',
                    context
                )

                send_mail(
                    subject=buyer_subject,
                    message=buyer_subject,
                    html_message=buyer_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[transaction.ad.seller.email],
                    fail_silently=True
                )

        logger.info(f"Notification sent for transaction {transaction.id}")
        return True

    except Transaction.DoesNotExist:
        logger.error(f"Transaction with id {transaction_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error sending transaction notification: {str(e)}")
        raise

@shared_task
def notify_transaction_completed(transaction_id):
    """
    Envoyer une notification par email lorsqu'une transaction est complétée
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        context = {
            'transaction': transaction,
            'user': transaction.user,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
        }

        subject = _("Transaction complétée - {site_name}").format(
            site_name=settings.SITE_NAME
        )

        # Email au vendeur
        if transaction.user and transaction.user.email:
            seller_message = render_to_string(
                'payments/emails/transaction_completed_seller.html',
                context
            )

            send_mail(
                subject=subject,
                message=subject,
                html_message=seller_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.user.email],
                fail_silently=True
            )

        # Email à l'acheteur (si ad liée)
        if hasattr(transaction, 'ad') and transaction.ad.seller.email:
            buyer_message = render_to_string(
                'payments/emails/transaction_completed_buyer.html',
                context
            )

            send_mail(
                subject=subject,
                message=subject,
                html_message=buyer_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.ad.seller.email],
                fail_silently=True
            )

        logger.info(f"Completion notification sent for transaction {transaction.id}")
        return True

    except Transaction.DoesNotExist:
        logger.error(f"Transaction with id {transaction_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error sending completion notification: {str(e)}")
        raise

@shared_task
def notify_transaction_expired(transaction_id):
    """
    Envoyer une notification par email lorsqu'une transaction a expiré
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        context = {
            'transaction': transaction,
            'user': transaction.user,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
        }

        subject = _("Transaction expirée - {site_name}").format(
            site_name=settings.SITE_NAME
        )

        if transaction.user and transaction.user.email:
            message = render_to_string(
                'payments/emails/transaction_expired.html',
                context
            )

            send_mail(
                subject=subject,
                message=subject,
                html_message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.user.email],
                fail_silently=True
            )

        logger.info(f"Expiration notification sent for transaction {transaction.id}")
        return True

    except Transaction.DoesNotExist:
        logger.error(f"Transaction with id {transaction_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error sending expiration notification: {str(e)}")
        raise

@shared_task
def send_invoice_email(invoice_id):
    """
    Envoyer une facture par email
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)

        if not invoice.invoice_pdf:
            # Générer le PDF si pas encore fait
            generate_invoice_pdf_task.delay(invoice_id)
            return "PDF generation queued"

        context = {
            'invoice': invoice,
            'user': invoice.user,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
        }

        subject = _("Votre facture {invoice_number} - {site_name}").format(
            invoice_number=invoice.invoice_number,
            site_name=settings.SITE_NAME
        )

        message = render_to_string('payments/emails/invoice_sent.html', context)

        # Préparer l'email avec pièce jointe
        from django.core.mail import EmailMessage

        email = EmailMessage(
            subject=subject,
            body=subject,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.user.email] if invoice.user.email else []
        )

        email.attach_file(invoice.invoice_pdf.path)
        email.content_subtype = "html"
        email.send()

        invoice.sent_at = timezone.now()
        invoice.save(update_fields=['sent_at'])

        logger.info(f"Invoice email sent for invoice {invoice.invoice_number}")
        return True

    except Invoice.DoesNotExist:
        logger.error(f"Invoice with id {invoice_id} does not exist")
        return False
    except Exception as e:
        logger.error(f"Error sending invoice email: {str(e)}")
        raise

@shared_task
def cleanup_old_payment_sessions():
    """
    Nettoyer les anciennes sessions de paiement
    """
    try:
        from .models import PaymentSession
        cutoff_time = timezone.now() - timedelta(hours=24)

        deleted_count, _ = PaymentSession.objects.filter(
            created_at__lt=cutoff_time,
            status__in=['PENDING', 'EXPIRED']
        ).delete()

        logger.info(f"Cleaned up {deleted_count} old payment sessions")
        return f"Cleaned up {deleted_count} old payment sessions"

    except Exception as e:
        logger.error(f"Error cleaning up payment sessions: {str(e)}")
        raise

@shared_task
def process_recurring_payments():
    """
    Traiter les paiements récurrents
    """
    try:
        from .models import Subscription
        today = timezone.now().date()

        # Trouver les abonnements à renouveler
        subscriptions = Subscription.objects.filter(
            status='ACTIVE',
            next_billing_date__lte=today,
            auto_renew=True
        )

        renewed_count = 0
        for subscription in subscriptions:
            try:
                # Créer une nouvelle transaction
                from .models import Transaction

                transaction = Transaction.objects.create(
                    user=subscription.user,
                    amount=subscription.plan.price,
                    currency=subscription.plan.currency,
                    payment_method=subscription.payment_method,
                    purpose='SUBSCRIPTION_RENEWAL',
                    status='PENDING',
                    metadata={
                        'subscription_id': subscription.id,
                        'plan_id': subscription.plan.id,
                        'renewal_period': subscription.current_period_end
                    }
                )

                # Mettre à jour la date de prochain paiement
                subscription.current_period_end = subscription.next_billing_date
                subscription.next_billing_date = subscription.next_billing_date + timedelta(
                    days=subscription.plan.billing_cycle_days
                )
                subscription.save()

                renewed_count += 1
                logger.info(f"Renewed subscription {subscription.id}")

            except Exception as e:
                logger.error(f"Error renewing subscription {subscription.id}: {str(e)}")
                continue

        return f"Processed {renewed_count} recurring payments"

    except Exception as e:
        logger.error(f"Error processing recurring payments: {str(e)}")
        raise

@shared_task(bind=True, max_retries=3)
def retry_failed_payment(self, transaction_id):
    """
    Réessayer un paiement échoué
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)

        if transaction.status != 'FAILED':
            return "Transaction not in FAILED status"

        # Logique de réessai
        # À adapter selon le backend de paiement

        transaction.status = 'PENDING'
        transaction.retry_count = transaction.retry_count + 1
        transaction.save(update_fields=['status', 'retry_count'])

        logger.info(f"Retried failed payment for transaction {transaction.id}")
        return True

    except Transaction.DoesNotExist:
        logger.error(f"Transaction with id {transaction_id} does not exist")
        return False
    except Exception as exc:
        logger.error(f"Error retrying payment: {str(exc)}")
        self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)
        raise
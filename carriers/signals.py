# ~/ebi3/carriers/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.models import Group
import logging

logger = logging.getLogger(__name__)


@receiver(post_save)
def update_user_role(sender, instance, created, **kwargs):
    """
    Met à jour le rôle de l'utilisateur quand un transporteur est créé/modifié.
    """
    # Vérifier si c'est le modèle Carrier
    if sender.__name__ == 'Carrier':
        try:
            if created:
                # Ajouter l'utilisateur au groupe des transporteurs
                from django.contrib.auth.models import Group
                carrier_group, _ = Group.objects.get_or_create(name='Carriers')
                instance.user.groups.add(carrier_group)

                # Créer les statistiques
                from .models import CarrierStatistics
                CarrierStatistics.objects.create(carrier=instance)

                logger.info(f"Utilisateur {instance.user.username} ajouté au groupe Carriers")

            # Mettre à jour le statut de l'utilisateur
            if instance.status == 'APPROVED':  # Utiliser la valeur string directement
                instance.user.is_active = True
                instance.user.save(update_fields=['is_active'])

                # Notification
                from .models import CarrierNotification
                CarrierNotification.objects.create(
                    carrier=instance,
                    notification_type='STATUS_CHANGED',  # Utiliser la valeur string
                    title=_("Compte approuvé"),
                    message=_("Votre compte transporteur a été approuvé. Vous pouvez maintenant accepter des missions."),
                    is_important=True
                )

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du rôle utilisateur: {e}")


@receiver(post_save)
def handle_mission_status_change(sender, instance, created, **kwargs):
    """
    Gère les changements de statut des missions.
    """
    # Vérifier si c'est le modèle Mission
    if sender.__name__ == 'Mission':
        try:
            if not created:
                from .models import CarrierNotification

                # Notification pour le transporteur
                if instance.status == 'ACCEPTED':  # Utiliser la valeur string
                    CarrierNotification.objects.create(
                        carrier=instance.carrier,
                        notification_type='MISSION_UPDATE',
                        title=_("Mission acceptée"),
                        message=_("Vous avez accepté la mission {}").format(instance.mission_number),
                        related_object_id=instance.id,
                        related_object_type='mission'
                    )

                elif instance.status == 'DELIVERED':  # Utiliser la valeur string
                    # Mettre à jour les statistiques
                    instance.carrier.completed_missions += 1
                    instance.carrier.save(update_fields=['completed_missions'])

                    # Notification
                    CarrierNotification.objects.create(
                        carrier=instance.carrier,
                        notification_type='MISSION_UPDATE',
                        title=_("Mission livrée"),
                        message=_("La mission {} a été livrée avec succès.").format(instance.mission_number),
                        related_object_id=instance.id,
                        related_object_type='mission'
                    )

                    # Notification pour l'expéditeur pour laisser un avis
                    CarrierNotification.objects.create(
                        carrier=instance.carrier,
                        notification_type='REVIEW_RECEIVED',
                        title=_("Mission terminée"),
                        message=_("La mission {} a été livrée. Vous pouvez laisser un avis.").format(instance.mission_number),
                        related_object_id=instance.id,
                        related_object_type='mission'
                    )

        except Exception as e:
            logger.error(f"Erreur lors du traitement du changement de statut de mission: {e}")


@receiver(post_save)
def handle_new_review(sender, instance, created, **kwargs):
    """
    Gère les nouveaux avis.
    """
    # Vérifier si c'est le modèle CarrierReview
    if sender.__name__ == 'CarrierReview':
        try:
            if created:
                from .models import CarrierNotification

                # Notification pour le transporteur
                CarrierNotification.objects.create(
                    carrier=instance.carrier,
                    notification_type='REVIEW_RECEIVED',
                    title=_("Nouvel avis reçu"),
                    message=_("Vous avez reçu un nouvel avis de {}").format(instance.reviewer.get_full_name()),
                    related_object_id=instance.id,
                    related_object_type='review'
                )

        except Exception as e:
            logger.error(f"Erreur lors du traitement du nouvel avis: {e}")


@receiver(post_save)
def handle_new_transaction(sender, instance, created, **kwargs):
    """
    Gères les nouvelles transactions financières.
    """
    # Vérifier si c'est le modèle FinancialTransaction
    if sender.__name__ == 'FinancialTransaction':
        try:
            if created and instance.transaction_type == 'PAYMENT':  # Utiliser la valeur string
                from .models import CarrierNotification

                # Notification pour le transporteur
                CarrierNotification.objects.create(
                    carrier=instance.carrier,
                    notification_type='PAYMENT_RECEIVED',
                    title=_("Paiement reçu"),
                    message=_("Vous avez reçu un paiement de {} {}").format(
                        instance.amount, instance.currency
                    ),
                    related_object_id=instance.id,
                    related_object_type='transaction'
                )

        except Exception as e:
            logger.error(f"Erreur lors du traitement de la nouvelle transaction: {e}")


@receiver(pre_save)
def check_document_expiry(sender, instance, **kwargs):
    """
    Vérifie l'expiration des documents.
    """
    # Vérifier si c'est le modèle CarrierDocument
    if sender.__name__ == 'CarrierDocument':
        try:
            if instance.expiry_date and instance.expiry_date < timezone.now().date():
                from .models import CarrierNotification

                # Notification d'expiration
                CarrierNotification.objects.create(
                    carrier=instance.carrier,
                    notification_type='DOCUMENT_EXPIRY',
                    title=_("Document expiré"),
                    message=_("Le document {} a expiré le {}").format(
                        instance.get_document_type_display(),
                        instance.expiry_date
                    ),
                    alert_level='URGENT',
                    related_object_id=instance.id,
                    related_object_type='document'
                )

        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'expiration du document: {e}")


@receiver(post_delete)
def update_carrier_stats_on_delete(sender, instance, **kwargs):
    """
    Met à jour les statistiques du transporteur quand une mission est supprimée.
    """
    # Vérifier si c'est le modèle Mission
    if sender.__name__ == 'Mission':
        try:
            if instance.carrier and instance.status == 'DELIVERED':  # Utiliser la valeur string
                instance.carrier.completed_missions = max(0, instance.carrier.completed_missions - 1)
                instance.carrier.save(update_fields=['completed_missions'])

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des stats après suppression: {e}")
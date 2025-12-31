# ~/ebi3/colis/signals.py
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
import logging

from .models import (
    Package, PackageCategory, PackageImage,
    TransportOffer, PackageView, PackageFavorite,
    PackageReport
)
from users.models import User
from carriers.models import Carrier, CarrierNotification
from .utils.signal_helpers import create_conversation_for_offer
from messaging.models import Conversation, Message

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Offer)
def handle_offer_save(sender, instance, created, **kwargs):
    """Gère la sauvegarde d'une offre"""
    if created:
        logger.info(f"Nouvelle offre créée: {instance.id}")

        # Créer une conversation en utilisant la fonction utilitaire
        conversation = create_conversation_for_offer(instance)
        if conversation:
            logger.info(f"Conversation créée: {conversation.id}")

# ============================================================================
# SIGNALS PACKAGE (COLIS)
# ============================================================================

@receiver(pre_save, sender=Package)
def update_package_status_dates(sender, instance, **kwargs):
    """
    Met à jour les dates automatiquement lors des changements de statut
    et calcule le volume automatiquement.
    """
    if instance.pk:
        try:
            old_instance = Package.objects.get(pk=instance.pk)

            # Calcul automatique du volume
            if instance.length and instance.width and instance.height:
                instance.volume = (instance.length * instance.width * instance.height) / 1000

            # Mise à jour des dates de statut
            if instance.status != old_instance.status:
                if instance.status == Package.Status.AVAILABLE and not instance.published_at:
                    instance.published_at = timezone.now()
                    logger.info(f"Package {instance.id} marked as AVAILABLE")

                elif instance.status == Package.Status.RESERVED and not instance.reserved_at:
                    instance.reserved_at = timezone.now()
                    logger.info(f"Package {instance.id} marked as RESERVED")

                elif instance.status == Package.Status.IN_TRANSIT and not instance.in_transit_at:
                    instance.in_transit_at = timezone.now()
                    logger.info(f"Package {instance.id} marked as IN_TRANSIT")

                elif instance.status == Package.Status.DELIVERED and not instance.delivered_at:
                    instance.delivered_at = timezone.now()
                    logger.info(f"Package {instance.id} marked as DELIVERED")

                elif instance.status == Package.Status.EXPIRED and not instance.expired_at:
                    instance.expired_at = timezone.now()
                    logger.info(f"Package {instance.id} marked as EXPIRED")

            # Vérification d'expiration automatique
            if (instance.status == Package.Status.AVAILABLE and
                instance.delivery_date and
                instance.delivery_date < timezone.now().date()):
                instance.status = Package.Status.EXPIRED
                instance.expired_at = timezone.now()
                logger.info(f"Package {instance.id} auto-expired")

        except Package.DoesNotExist:
            pass  # Nouvelle instance, pas d'ancienne version


@receiver(post_save, sender=Package)
def update_category_count(sender, instance, created, **kwargs):
    """
    Met à jour le compteur de colis dans la catégorie
    """
    if instance.category:
        try:
            instance.category.update_package_count()
            logger.debug(f"Updated package count for category {instance.category.id}")
        except Exception as e:
            logger.error(f"Error updating category count: {e}")


@receiver(post_save, sender=Package)
def notify_package_status_change(sender, instance, created, **kwargs):
    """
    Envoie des notifications lors des changements de statut d'un colis
    """
    if not created:  # Seulement pour les mises à jour
        try:
            from .tasks import send_package_status_notification
            send_package_status_notification.delay(instance.id)
            logger.info(f"Queued status notification for package {instance.id}")
        except Exception as e:
            logger.error(f"Error queuing status notification: {e}")


@receiver(pre_delete, sender=Package)
def cleanup_package_files(sender, instance, **kwargs):
    """
    Nettoie les fichiers associés à un colis avant suppression
    """
    try:
        # Supprimer les images (géré par django-cleanup)
        for image in instance.images.all():
            image.delete()

        logger.info(f"Cleaned up files for package {instance.id}")
    except Exception as e:
        logger.error(f"Error cleaning package files: {e}")


# ============================================================================
# SIGNALS PACKAGE IMAGE
# ============================================================================

@receiver(pre_save, sender=PackageImage)
def set_primary_image(sender, instance, **kwargs):
    """
    S'assure qu'il y a toujours une image principale
    et qu'il n'y en a qu'une seule
    """
    if not instance.pk:  # Nouvelle image
        # Si c'est la première image du colis, la marquer comme principale
        if not instance.package.images.exists() and not instance.is_primary:
            instance.is_primary = True

    if instance.is_primary:
        # Désactiver les autres images principales du même colis
        PackageImage.objects.filter(
            package=instance.package,
            is_primary=True
        ).exclude(pk=instance.pk).update(is_primary=False)
        logger.debug(f"Set image {instance.id} as primary for package {instance.package.id}")


@receiver(post_save, sender=PackageImage)
def update_package_image_count(sender, instance, created, **kwargs):
    """
    Met à jour le compteur d'images payantes utilisées
    """
    if created and instance.is_paid and instance.payment_status == 'PAID':
        try:
            package = instance.package
            package.paid_images_used = package.images.filter(
                is_paid=True,
                payment_status='PAID'
            ).count()
            package.save(update_fields=['paid_images_used'])
            logger.debug(f"Updated paid images count for package {package.id}")
        except Exception as e:
            logger.error(f"Error updating paid images count: {e}")


# ============================================================================
# SIGNALS TRANSPORT OFFER (OFFRES DE TRANSPORT)
# ============================================================================

@receiver(pre_save, sender=TransportOffer)
def set_offer_expiry(sender, instance, **kwargs):
    """
    Définit la date d'expiration d'une offre si elle n'est pas déjà définie
    """
    if not instance.expires_at:
        # Par défaut, une offre expire dans 72h
        instance.expires_at = timezone.now() + timezone.timedelta(hours=72)
        logger.debug(f"Set expiry date for offer {instance.id}")


@receiver(pre_save, sender=TransportOffer)
def validate_offer_status(sender, instance, **kwargs):
    """
    Valide les transitions de statut d'une offre
    """
    if instance.pk:
        try:
            old_instance = TransportOffer.objects.get(pk=instance.pk)

            # Vérifier que l'offre n'est pas déjà expirée
            if old_instance.is_expired() and instance.status == TransportOffer.Status.PENDING:
                instance.status = TransportOffer.Status.EXPIRED
                logger.warning(f"Offer {instance.id} auto-expired")

            # Marquer la date d'acceptation
            if (instance.status == TransportOffer.Status.ACCEPTED and
                old_instance.status != TransportOffer.Status.ACCEPTED):
                instance.accepted_at = timezone.now()
                logger.info(f"Offer {instance.id} accepted at {instance.accepted_at}")

        except TransportOffer.DoesNotExist:
            pass


@receiver(post_save, sender=TransportOffer)
def handle_accepted_offer(sender, instance, created, **kwargs):
    """
    Gère les actions lorsqu'une offre est acceptée
    """
    if instance.status == TransportOffer.Status.ACCEPTED:
        with transaction.atomic():
            try:
                # Mettre à jour le statut du colis
                package = instance.package
                package.status = Package.Status.RESERVED
                package.reserved_at = timezone.now()
                package.save(update_fields=['status', 'reserved_at'])

                # Rejeter automatiquement les autres offres en attente
                TransportOffer.objects.filter(
                    package=package,
                    status=TransportOffer.Status.PENDING
                ).exclude(pk=instance.pk).update(
                    status=TransportOffer.Status.REJECTED,
                    rejection_reason=_("Une autre offre a été acceptée")
                )

                # Créer une conversation entre les parties
                create_conversation_for_accepted_offer(instance)

                # Envoyer des notifications
                send_offer_accepted_notifications(instance)

                logger.info(f"Offer {instance.id} accepted, package {package.id} reserved")

            except Exception as e:
                logger.error(f"Error handling accepted offer {instance.id}: {e}")


def create_conversation_for_accepted_offer(offer):
    """
    Crée une conversation entre l'expéditeur et le transporteur
    lorsqu'une offre est acceptée
    """
    try:
        conversation, created = Conversation.objects.get_or_create(
            participant_a=offer.package.sender,
            participant_b=offer.carrier.user,
            defaults={
                'subject': f"Colis accepté: {offer.package.title}",
                'last_message_at': timezone.now()
            }
        )

        if created or not conversation.messages.exists():
            Message.objects.create(
                conversation=conversation,
                sender=offer.package.sender,
                content=_(
                    "Bonjour, j'ai accepté votre offre de {price}€ pour le transport de mon colis. "
                    "Nous pouvons maintenant organiser les détails du transport."
                ).format(price=offer.price)
            )

        logger.debug(f"Created conversation for accepted offer {offer.id}")

    except Exception as e:
        logger.error(f"Error creating conversation for offer {offer.id}: {e}")


def send_offer_accepted_notifications(offer):
    """
    Envoie des notifications par email lorsque une offre est acceptée
    """
    try:
        # Notification au transporteur
        subject_to_carrier = _("Votre offre a été acceptée !")
        message_to_carrier = render_to_string('colis/email/offer_accepted_carrier.html', {
            'offer': offer,
            'package': offer.package,
        })

        send_mail(
            subject_to_carrier,
            message_to_carrier,
            settings.DEFAULT_FROM_EMAIL,
            [offer.carrier.user.email],
            html_message=message_to_carrier,
            fail_silently=True
        )

        # Notification à l'expéditeur
        subject_to_sender = _("Vous avez accepté une offre")
        message_to_sender = render_to_string('colis/email/offer_accepted_sender.html', {
            'offer': offer,
            'package': offer.package,
        })

        send_mail(
            subject_to_sender,
            message_to_sender,
            settings.DEFAULT_FROM_EMAIL,
            [offer.package.sender.email],
            html_message=message_to_sender,
            fail_silently=True
        )

        logger.info(f"Sent acceptance notifications for offer {offer.id}")

    except Exception as e:
        logger.error(f"Error sending acceptance notifications: {e}")


@receiver(post_save, sender=TransportOffer)
def notify_new_offer(sender, instance, created, **kwargs):
    """
    Envoie une notification lorsqu'une nouvelle offre est créée
    """
    if created:
        try:
            from .tasks import send_new_offer_notification
            send_new_offer_notification.delay(instance.id)
            logger.info(f"Queued new offer notification for package {instance.package.id}")
        except Exception as e:
            logger.error(f"Error queuing new offer notification: {e}")


@receiver(post_save, sender=TransportOffer)
def update_package_offer_count(sender, instance, created, **kwargs):
    """
    Met à jour le compteur d'offres du colis
    """
    try:
        package = instance.package
        package.offer_count = TransportOffer.objects.filter(package=package).count()
        package.save(update_fields=['offer_count'])
        logger.debug(f"Updated offer count for package {package.id}")
    except Exception as e:
        logger.error(f"Error updating offer count: {e}")


# ============================================================================
# SIGNALS PACKAGE VIEW (VUES)
# ============================================================================

@receiver(post_save, sender=PackageView)
def update_package_view_count(sender, instance, created, **kwargs):
    """
    Met à jour le compteur de vues d'un colis
    """
    if created:
        try:
            package = instance.package
            package.view_count = PackageView.objects.filter(package=package).count()
            package.save(update_fields=['view_count'])
            logger.debug(f"Updated view count for package {package.id}")
        except Exception as e:
            logger.error(f"Error updating view count: {e}")


# ============================================================================
# SIGNALS PACKAGE FAVORITE (FAVORIS)
# ============================================================================

@receiver(post_save, sender=PackageFavorite)
def update_package_favorite_count_on_save(sender, instance, created, **kwargs):
    """
    Met à jour le compteur de favoris d'un colis lors de l'ajout
    """
    if created:
        try:
            package = instance.package
            package.favorite_count = PackageFavorite.objects.filter(package=package).count()
            package.save(update_fields=['favorite_count'])
            logger.debug(f"Updated favorite count for package {package.id} on save")
        except Exception as e:
            logger.error(f"Error updating favorite count on save: {e}")


@receiver(post_delete, sender=PackageFavorite)
def update_package_favorite_count_on_delete(sender, instance, **kwargs):
    """
    Met à jour le compteur de favoris d'un colis lors de la suppression
    """
    try:
        package = instance.package
        package.favorite_count = PackageFavorite.objects.filter(package=package).count()
        package.save(update_fields=['favorite_count'])
        logger.debug(f"Updated favorite count for package {package.id} on delete")
    except Exception as e:
        logger.error(f"Error updating favorite count on delete: {e}")


# ============================================================================
# SIGNALS PACKAGE REPORT (SIGNALEMENTS)
# ============================================================================

@receiver(post_save, sender=PackageReport)
def handle_new_report(sender, instance, created, **kwargs):
    """
    Gère les nouveaux signalements
    """
    if created:
        try:
            # Envoyer une notification à l'admin
            subject = _("Nouveau signalement de colis")
            message = render_to_string('colis/email/new_report.html', {
                'report': instance,
                'package': instance.package,
            })

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                html_message=message,
                fail_silently=True
            )

            logger.info(f"New report {instance.id} created, notification sent to admin")

            # Créer une notification pour l'équipe de modération
            if hasattr(settings, 'MODERATION_TEAM_EMAILS'):
                for email in settings.MODERATION_TEAM_EMAILS:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        html_message=message,
                        fail_silently=True
                    )

        except Exception as e:
            logger.error(f"Error handling new report {instance.id}: {e}")


@receiver(pre_save, sender=PackageReport)
def update_report_resolution(sender, instance, **kwargs):
    """
    Met à jour les dates de résolution des signalements
    """
    if instance.pk:
        try:
            old_instance = PackageReport.objects.get(pk=instance.pk)

            # Si le statut passe à résolu ou rejeté
            if (instance.status in ['RESOLVED', 'DISMISSED'] and
                old_instance.status not in ['RESOLVED', 'DISMISSED']):
                instance.resolved_at = timezone.now()
                logger.info(f"Report {instance.id} resolved at {instance.resolved_at}")

        except PackageReport.DoesNotExist:
            pass


# ============================================================================
# SIGNALS PACKAGE CATEGORY (CATÉGORIES)
# ============================================================================

@receiver(pre_save, sender=PackageCategory)
def generate_category_slug(sender, instance, **kwargs):
    """
    Génère automatiquement le slug d'une catégorie si vide
    """
    if not instance.slug and instance.name:
        from django.utils.text import slugify
        instance.slug = slugify(instance.name)
        logger.debug(f"Generated slug for category: {instance.slug}")


@receiver(post_save, sender=PackageCategory)
def invalidate_category_cache(sender, instance, **kwargs):
    """
    Invalide le cache des catégories après modification
    """
    try:
        from django.core.cache import cache
        cache_keys = [
            'package_categories_menu',
            'package_categories_all',
            f'package_category_{instance.slug}'
        ]
        for key in cache_keys:
            cache.delete(key)
        logger.debug(f"Invalidated cache for category {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating category cache: {e}")


# ============================================================================
# SIGNALS LIÉS AUX UTILISATEURS
# ============================================================================

@receiver(post_save, sender=User)
def create_welcome_package_for_new_user(sender, instance, created, **kwargs):
    """
    Crée un colis d'exemple pour les nouveaux utilisateurs
    (optionnel, pour aider à la découverte)
    """
    if created and settings.CREATE_SAMPLE_PACKAGE_FOR_NEW_USERS:
        try:
            # Attendre un peu pour éviter les problèmes de timing
            import threading
            timer = threading.Timer(
                5.0,  # 5 secondes après la création
                create_sample_package,
                args=[instance]
            )
            timer.start()
            logger.info(f"Scheduled sample package creation for user {instance.id}")

        except Exception as e:
            logger.error(f"Error scheduling sample package: {e}")


def create_sample_package(user):
    """
    Crée un colis d'exemple pour un nouvel utilisateur
    """
    try:
        # Trouver une catégorie par défaut
        from .models import PackageCategory
        default_category = PackageCategory.objects.filter(is_active=True).first()

        if default_category:
            sample_package = Package.objects.create(
                sender=user,
                category=default_category,
                title=_("Exemple de colis - Modèle"),
                description=_(
                    "Ceci est un exemple de colis pour vous montrer comment remplir votre annonce. "
                    "Vous pouvez le modifier ou le supprimer à tout moment.\n\n"
                    "Conseils :\n"
                    "• Donnez un titre clair et descriptif\n"
                    "• Indiquez toutes les dimensions et le poids\n"
                    "• Prenez des photos de bonne qualité\n"
                    "• Soyez précis sur les dates de disponibilité"
                ),
                package_type=Package.PackageType.SMALL_PACKAGE,
                weight=10.5,
                length=40,
                width=30,
                height=20,
                pickup_country='FR',
                pickup_city=_("Paris"),
                delivery_country='FR',
                delivery_city=_("Lyon"),
                pickup_date=timezone.now().date() + timezone.timedelta(days=7),
                delivery_date=timezone.now().date() + timezone.timedelta(days=14),
                price_type=Package.PriceType.NEGOTIABLE,
                asking_price=50.00,
                currency='EUR',
                status=Package.Status.DRAFT,
                is_featured=False
            )

            logger.info(f"Created sample package {sample_package.id} for user {user.id}")

    except Exception as e:
        logger.error(f"Error creating sample package: {e}")


# ============================================================================
# SIGNALS DE NETTOYAGE AUTOMATIQUE
# ============================================================================

@receiver(pre_save, sender=TransportOffer)
def cleanup_expired_offers(sender, instance, **kwargs):
    """
    Nettoie automatiquement les offres expirées
    """
    if instance.is_expired() and instance.status == TransportOffer.Status.PENDING:
        instance.status = TransportOffer.Status.EXPIRED
        logger.info(f"Auto-expired offer {instance.id}")


# ============================================================================
# SIGNALS DE SYNCHRONISATION AVEC L'APP CARRIERS
# ============================================================================

@receiver(post_save, sender=Carrier)
def update_carrier_availability(sender, instance, **kwargs):
    """
    Met à jour la disponibilité des offres lorsqu'un transporteur change de statut
    """
    if instance.status != Carrier.Status.APPROVED or not instance.is_available:
        try:
            # Marquer toutes les offres en attente comme expirées
            expired_count = TransportOffer.objects.filter(
                carrier=instance,
                status=TransportOffer.Status.PENDING
            ).update(status=TransportOffer.Status.EXPIRED)

            if expired_count > 0:
                logger.info(f"Expired {expired_count} offers for carrier {instance.id}")

        except Exception as e:
            logger.error(f"Error updating carrier offers: {e}")


# ============================================================================
# SIGNALS POUR LES STATISTIQUES
# ============================================================================

@receiver(post_save, sender=Package)
@receiver(post_save, sender=TransportOffer)
@receiver(post_save, sender=PackageView)
@receiver(post_save, sender=PackageFavorite)
def invalidate_statistics_cache(sender, instance, **kwargs):
    """
    Invalide le cache des statistiques après modification des données
    """
    try:
        from django.core.cache import cache
        cache.delete_pattern('stats_*')
        cache.delete('dashboard_stats')
        logger.debug("Invalidated statistics cache")
    except Exception as e:
        logger.error(f"Error invalidating statistics cache: {e}")


# ============================================================================
# CONNEXION DES SIGNALS
# ============================================================================

def connect_signals():
    """
    Connecte tous les signaux (appelé dans apps.py)
    """
    # Les signaux sont automatiquement connectés via les décorateurs @receiver
    # Cette fonction est utile pour une connexion explicite si nécessaire
    pass


def disconnect_signals():
    """
    Déconnecte tous les signaux (pour les tests)
    """
    from django.db.models.signals import post_save, pre_save, post_delete, pre_delete

    # Déconnecter tous les signaux liés aux modèles de colis
    models = [Package, PackageImage, TransportOffer, PackageView,
              PackageFavorite, PackageReport, PackageCategory]

    for model in models:
        post_save.disconnect(receiver=None, sender=model)
        pre_save.disconnect(receiver=None, sender=model)
        post_delete.disconnect(receiver=None, sender=model)
        pre_delete.disconnect(receiver=None, sender=model)

    logger.info("Disconnected all colis signals")
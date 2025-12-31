# ~/ebi3/logistics/signals.py

from django.db.models.signals import (
    post_save, pre_save, post_delete, m2m_changed, pre_delete
)
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.core.cache import cache

from .models import (
    Reservation, Mission, Route, TransportProposal, TrackingEvent,
    LogisticsSettings, ReservationStatus, MissionStatus, RouteStatus,
    TransportProposalStatus, LogisticsOption
)
from ads.models import Ad
from carriers.models import CarrierProfile
from users.models import User, Notification
from core.models import ActivityLog
from messaging.models import Conversation, Message


# ============================================================================
# SIGNALS POUR LES RÉSERVATIONS
# ============================================================================

@receiver(pre_save, sender=Reservation)
def reservation_pre_save(sender, instance, **kwargs):
    """
    Avant de sauvegarder une réservation
    """
    # Calculer le prix total si nécessaire
    if not instance.total_price or instance.pk is None:
        instance.total_price = (
            (instance.price_agreed or 0) +
            (instance.shipping_cost or 0) +
            (instance.insurance_cost or 0)
        )

    # Si c'est une nouvelle réservation, vérifier que l'annonce peut être réservée
    if instance.pk is None:
        if not instance.ad.can_be_reserved:
            raise ValueError(_("Cette annonce n'est pas disponible pour réservation."))

        # Marquer l'annonce comme réservée
        instance.ad.is_reserved = True
        instance.ad.save(update_fields=['is_reserved', 'updated_at'])

    # Si la réservation est annulée, marquer l'annonce comme disponible
    if instance.pk and instance.status == ReservationStatus.CANCELLED:
        old_instance = Reservation.objects.get(pk=instance.pk)
        if old_instance.status != ReservationStatus.CANCELLED:
            instance.ad.is_reserved = False
            instance.ad.save(update_fields=['is_reserved', 'updated_at'])
            instance.cancelled_at = timezone.now()


@receiver(post_save, sender=Reservation)
def reservation_post_save(sender, instance, created, **kwargs):
    """
    Après avoir sauvegardé une réservation
    """
    if created:
        # Créer un log d'activité
        ActivityLog.objects.create(
            user=instance.buyer,
            action_type='RESERVATION_CREATED',
            object_id=instance.id,
            details={
                'ad_id': instance.ad.id,
                'ad_title': instance.ad.title,
                'logistics_option': instance.logistics_option,
                'total_price': str(instance.total_price)
            }
        )

        # Mettre à jour les statistiques du vendeur
        if hasattr(instance.ad.seller, 'profile'):
            profile = instance.ad.seller.profile
            profile.total_reservations = (profile.total_reservations or 0) + 1
            profile.save(update_fields=['total_reservations', 'updated_at'])

        # Invalider le cache des annonces
        cache_keys = [
            f'ad_{instance.ad.id}_details',
            f'user_{instance.buyer.id}_reservations',
            f'user_{instance.ad.seller.id}_seller_stats'
        ]
        for key in cache_keys:
            cache.delete(key)

    # Si le statut a changé
    if instance.pk and not created:
        old_instance = Reservation.objects.get(pk=instance.pk)
        if old_instance.status != instance.status:
            # Créer un log d'activité pour le changement de statut
            ActivityLog.objects.create(
                user=instance.buyer,
                action_type='RESERVATION_STATUS_CHANGED',
                object_id=instance.id,
                details={
                    'old_status': old_instance.status,
                    'new_status': instance.status,
                    'ad_id': instance.ad.id
                }
            )

            # Si la réservation est passée en transit et a un transporteur, créer une mission
            if (instance.status == ReservationStatus.IN_TRANSIT and
                instance.carrier and
                not hasattr(instance, 'mission')):

                Mission.objects.create(
                    reservation=instance,
                    carrier=instance.carrier,
                    status=MissionStatus.IN_TRANSIT,
                    estimated_delivery=instance.delivery_date
                )

            # Si la réservation est livrée, mettre à jour les statistiques
            if instance.status == ReservationStatus.DELIVERED:
                # Mettre à jour le nombre de transactions réussies
                if hasattr(instance.ad.seller, 'profile'):
                    profile = instance.ad.seller.profile
                    profile.successful_transactions = (profile.successful_transactions or 0) + 1
                    profile.save(update_fields=['successful_transactions', 'updated_at'])

                # Mettre à jour les statistiques du transporteur
                if instance.carrier and hasattr(instance.carrier, 'completed_missions'):
                    instance.carrier.completed_missions = (instance.carrier.completed_missions or 0) + 1
                    instance.carrier.save(update_fields=['completed_missions', 'updated_at'])


@receiver(pre_delete, sender=Reservation)
def reservation_pre_delete(sender, instance, **kwargs):
    """
    Avant de supprimer une réservation
    """
    # Marquer l'annonce comme disponible
    instance.ad.is_reserved = False
    instance.ad.save(update_fields=['is_reserved', 'updated_at'])

    # Créer un log d'activité
    ActivityLog.objects.create(
        user=instance.buyer,
        action_type='RESERVATION_DELETED',
        object_id=instance.id,
        details={
            'ad_id': instance.ad.id,
            'ad_title': instance.ad.title,
            'status': instance.status
        }
    )


# ============================================================================
# SIGNALS POUR LES MISSIONS
# ============================================================================

@receiver(pre_save, sender=Mission)
def mission_pre_save(sender, instance, **kwargs):
    """
    Avant de sauvegarder une mission
    """
    # Si la mission est marquée comme livrée, définir la date de livraison
    if instance.status == MissionStatus.DELIVERED and not instance.actual_delivery:
        instance.actual_delivery = timezone.now()

    # Si la mission est retardée et qu'il n'y a pas de raison
    if instance.status == MissionStatus.DELAYED and not instance.delay_reason:
        instance.delay_reason = _("Raison non spécifiée")


@receiver(post_save, sender=Mission)
def mission_post_save(sender, instance, created, **kwargs):
    """
    Après avoir sauvegardé une mission
    """
    if created:
        # Créer un log d'activité
        ActivityLog.objects.create(
            user=instance.carrier.user,
            action_type='MISSION_CREATED',
            object_id=instance.id,
            details={
                'reservation_id': instance.reservation.id,
                'ad_title': instance.reservation.ad.title,
                'status': instance.status
            }
        )

        # Créer une conversation entre les parties
        create_mission_conversation(instance)

    # Si le statut a changé
    if instance.pk and not created:
        old_instance = Mission.objects.get(pk=instance.pk)
        if old_instance.status != instance.status:
            # Créer un log d'activité
            ActivityLog.objects.create(
                user=instance.carrier.user,
                action_type='MISSION_STATUS_CHANGED',
                object_id=instance.id,
                details={
                    'old_status': old_instance.status,
                    'new_status': instance.status
                }
            )

            # Si la mission est livrée, mettre à jour la réservation
            if instance.status == MissionStatus.DELIVERED:
                reservation = instance.reservation
                reservation.status = ReservationStatus.DELIVERED
                reservation.actual_delivery_date = timezone.now().date()
                reservation.save()

                # Notifier l'acheteur et le vendeur
                create_delivery_notifications(reservation)


def create_mission_conversation(mission):
    """
    Créer une conversation pour une mission
    """
    try:
        # Participants : acheteur, vendeur, transporteur
        participants = [
            mission.reservation.buyer,
            mission.reservation.ad.seller,
            mission.carrier.user
        ]

        # Créer ou récupérer la conversation
        conversation, created = Conversation.objects.get_or_create(
            subject=f"Mission #{mission.id} - {mission.reservation.ad.title}",
            defaults={
                'created_by': mission.carrier.user
            }
        )

        if created:
            conversation.participants.set(participants)

            # Message d'introduction
            Message.objects.create(
                conversation=conversation,
                sender=mission.carrier.user,
                content=_(
                    "Bonjour,\n\n"
                    "Je suis votre transporteur pour l'objet '{}'. "
                    "N'hésitez pas à utiliser cette conversation pour coordonner "
                    "la logistique et poser vos questions.\n\n"
                    "Statut actuel : {}\n"
                    "Livraison estimée : {}"
                ).format(
                    mission.reservation.ad.title,
                    mission.get_status_display(),
                    mission.estimated_delivery.strftime('%d/%m/%Y') if mission.estimated_delivery else _('À définir')
                )
            )
    except Exception as e:
        # Log l'erreur mais ne pas bloquer
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur création conversation mission: {e}")


def create_delivery_notifications(reservation):
    """
    Créer des notifications pour une livraison
    """
    # Notification à l'acheteur
    Notification.objects.create(
        user=reservation.buyer,
        title=_("Livraison effectuée"),
        message=_("Votre objet '{}' a été livré avec succès !").format(reservation.ad.title),
        url=reservation.get_absolute_url(),
        notification_type='DELIVERY_COMPLETED',
        priority='HIGH'
    )

    # Notification au vendeur
    Notification.objects.create(
        user=reservation.ad.seller,
        title=_("Livraison effectuée"),
        message=_("L'objet '{}' a été livré à l'acheteur.").format(reservation.ad.title),
        url=reservation.get_absolute_url(),
        notification_type='DELIVERY_COMPLETED',
        priority='HIGH'
    )


# ============================================================================
# SIGNALS POUR LES ÉVÉNEMENTS DE SUIVI
# ============================================================================

@receiver(post_save, sender=TrackingEvent)
def tracking_event_post_save(sender, instance, created, **kwargs):
    """
    Après avoir sauvegardé un événement de suivi
    """
    if created:
        # Mettre à jour la localisation de la mission si nécessaire
        if instance.location and instance.mission.current_location != instance.location:
            instance.mission.current_location = instance.location
            instance.mission.save(update_fields=['current_location', 'updated_at'])

        # Créer un log d'activité
        ActivityLog.objects.create(
            user=instance.created_by,
            action_type='TRACKING_EVENT_CREATED',
            object_id=instance.id,
            details={
                'mission_id': instance.mission.id,
                'event_type': instance.event_type,
                'location': instance.location
            }
        )

        # Notifier l'acheteur
        if instance.mission.reservation.buyer != instance.created_by:
            Notification.objects.create(
                user=instance.mission.reservation.buyer,
                title=_("Mise à jour de suivi"),
                message=_("Nouvel événement : {} - {}").format(
                    instance.get_event_type_display(),
                    instance.description[:100]
                ),
                url=instance.mission.get_absolute_url(),
                notification_type='TRACKING_UPDATED'
            )

        # Notifier le vendeur
        if instance.mission.reservation.ad.seller != instance.created_by:
            Notification.objects.create(
                user=instance.mission.reservation.ad.seller,
                title=_("Mise à jour de suivi"),
                message=_("Nouvel événement : {}").format(instance.get_event_type_display()),
                url=instance.mission.get_absolute_url(),
                notification_type='TRACKING_UPDATED'
            )


# ============================================================================
# SIGNALS POUR LES ROUTES
# ============================================================================

@receiver(pre_save, sender=Route)
def route_pre_save(sender, instance, **kwargs):
    """
    Avant de sauvegarder une route
    """
    # Vérifier que les dates sont valides
    if instance.arrival_date < instance.departure_date:
        raise ValueError(_("La date d'arrivée doit être après la date de départ."))

    # Vérifier les capacités
    if instance.available_weight > instance.max_weight:
        raise ValueError(_("Le poids disponible ne peut pas dépasser le poids maximum."))

    if instance.available_volume > instance.max_volume:
        raise ValueError(_("Le volume disponible ne peut pas dépasser le volume maximum."))

    # Mettre à jour le statut si la route est complète
    if instance.available_weight == 0 and instance.available_volume == 0:
        instance.status = RouteStatus.FULL
    elif instance.status == RouteStatus.FULL and (instance.available_weight > 0 or instance.available_volume > 0):
        instance.status = RouteStatus.ACTIVE


@receiver(post_save, sender=Route)
def route_post_save(sender, instance, created, **kwargs):
    """
    Après avoir sauvegardé une route
    """
    if created:
        # Créer un log d'activité
        ActivityLog.objects.create(
            user=instance.carrier.user,
            action_type='ROUTE_CREATED',
            object_id=instance.id,
            details={
                'route': f"{instance.start_city} → {instance.end_city}",
                'departure_date': instance.departure_date.strftime('%d/%m/%Y'),
                'capacity': f"{instance.available_weight}kg / {instance.available_volume}m³"
            }
        )

        # Invalider le cache des routes
        cache.delete('available_routes_list')
        cache.delete(f'carrier_{instance.carrier.id}_routes')

    # Si le statut a changé
    if instance.pk and not created:
        old_instance = Route.objects.get(pk=instance.pk)
        if old_instance.status != instance.status:
            ActivityLog.objects.create(
                user=instance.carrier.user,
                action_type='ROUTE_STATUS_CHANGED',
                object_id=instance.id,
                details={
                    'old_status': old_instance.status,
                    'new_status': instance.status
                }
            )


@receiver(m2m_changed, sender=Route.carrier.through)
def route_carrier_changed(sender, instance, action, **kwargs):
    """
    Quand un transporteur est ajouté ou retiré d'une route
    """
    if action in ['post_add', 'post_remove']:
        # Invalider le cache
        cache.delete('available_routes_list')
        if hasattr(instance, 'carrier'):
            cache.delete(f'carrier_{instance.carrier.id}_routes')


# ============================================================================
# SIGNALS POUR LES PROPOSITIONS DE TRANSPORT
# ============================================================================

@receiver(pre_save, sender=TransportProposal)
def transport_proposal_pre_save(sender, instance, **kwargs):
    """
    Avant de sauvegarder une proposition de transport
    """
    # Définir la date d'expiration par défaut
    if not instance.expires_at:
        settings = LogisticsSettings.load()
        instance.expires_at = timezone.now() + timezone.timedelta(days=settings.proposal_expiry_days)

    # Vérifier que la proposition n'est pas expirée
    if instance.expires_at and timezone.now() > instance.expires_at:
        instance.status = TransportProposalStatus.EXPIRED

    # Vérifier que le transporteur a les capacités nécessaires
    if instance.ad and instance.carrier:
        if instance.ad.weight and instance.carrier.max_weight < instance.ad.weight:
            raise ValueError(_("Le transporteur n'a pas la capacité nécessaire pour cet objet."))

        if hasattr(instance.ad, 'volume') and instance.ad.volume and instance.carrier.max_volume < instance.ad.volume:
            raise ValueError(_("Le transporteur n'a pas le volume nécessaire pour cet objet."))


@receiver(post_save, sender=TransportProposal)
def transport_proposal_post_save(sender, instance, created, **kwargs):
    """
    Après avoir sauvegardé une proposition de transport
    """
    if created:
        # Créer un log d'activité
        ActivityLog.objects.create(
            user=instance.carrier.user,
            action_type='PROPOSAL_CREATED',
            object_id=instance.id,
            details={
                'ad_id': instance.ad.id,
                'ad_title': instance.ad.title,
                'proposed_price': str(instance.proposed_price)
            }
        )

        # Notifier le vendeur
        Notification.objects.create(
            user=instance.ad.seller,
            title=_("Nouvelle proposition de transport"),
            message=_("{} a fait une proposition pour votre annonce '{}'.").format(
                instance.carrier.user.username,
                instance.ad.title[:50]
            ),
            url=instance.get_absolute_url(),
            notification_type='PROPOSAL_RECEIVED',
            priority='MEDIUM'
        )

    # Si le statut a changé
    if instance.pk and not created:
        old_instance = TransportProposal.objects.get(pk=instance.pk)
        if old_instance.status != instance.status:
            ActivityLog.objects.create(
                user=instance.ad.seller if instance.status == 'ACCEPTED' else instance.carrier.user,
                action_type='PROPOSAL_STATUS_CHANGED',
                object_id=instance.id,
                details={
                    'old_status': old_instance.status,
                    'new_status': instance.status
                }
            )

            # Si la proposition est acceptée, créer une réservation
            if instance.status == TransportProposalStatus.ACCEPTED:
                create_reservation_from_proposal(instance)


def create_reservation_from_proposal(proposal):
    """
    Créer une réservation à partir d'une proposition acceptée
    """
    try:
        with transaction.atomic():
            reservation = Reservation.objects.create(
                ad=proposal.ad,
                buyer=None,  # L'acheteur sera défini plus tard
                carrier=proposal.carrier,
                logistics_option=LogisticsOption.WITH_CARRIER,
                price_agreed=proposal.ad.price,
                shipping_cost=proposal.proposed_price,
                total_price=proposal.ad.price + proposal.proposed_price,
                requires_insurance=proposal.includes_insurance,
                insurance_value=proposal.insurance_value,
                requires_packaging=proposal.includes_packaging,
                pickup_date=proposal.estimated_pickup_date,
                delivery_date=proposal.estimated_delivery_date,
                status=ReservationStatus.PENDING,
                buyer_notes=_("Proposition acceptée automatiquement")
            )

            # Notifier le transporteur
            Notification.objects.create(
                user=proposal.carrier.user,
                title=_("Proposition acceptée !"),
                message=_("Votre proposition pour '{}' a été acceptée. Une réservation a été créée.").format(
                    proposal.ad.title
                ),
                url=reservation.get_absolute_url(),
                notification_type='PROPOSAL_ACCEPTED',
                priority='HIGH'
            )

            return reservation
    except Exception as e:
        # Log l'erreur
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur création réservation depuis proposition: {e}")
        raise


# ============================================================================
# SIGNALS POUR LES INTERACTIONS AVEC D'AUTRES APPS
# ============================================================================

@receiver(post_save, sender=Ad)
def ad_post_save(sender, instance, created, **kwargs):
    """
    Quand une annonce est sauvegardée
    """
    # Si l'annonce est marquée comme réservée mais n'a pas de réservation active
    if instance.is_reserved and not instance.reservations.filter(
        status__in=['PENDING', 'CONFIRMED', 'PAID', 'IN_TRANSIT']
    ).exists():
        instance.is_reserved = False
        instance.save(update_fields=['is_reserved', 'updated_at'])


@receiver(post_save, sender=CarrierProfile)
def carrier_profile_post_save(sender, instance, created, **kwargs):
    """
    Quand un profil transporteur est sauvegardé
    """
    if created:
        # Ajouter le rôle transporteur à l'utilisateur
        if instance.user.role != 'CARRIER':
            instance.user.role = 'CARRIER'
            instance.user.save(update_fields=['role', 'updated_at'])

        # Créer un log d'activité
        ActivityLog.objects.create(
            user=instance.user,
            action_type='CARRIER_PROFILE_CREATED',
            object_id=instance.id,
            details={
                'company_name': instance.company_name,
                'carrier_type': instance.carrier_type
            }
        )


@receiver(pre_delete, sender=CarrierProfile)
def carrier_profile_pre_delete(sender, instance, **kwargs):
    """
    Avant de supprimer un profil transporteur
    """
    # Annuler toutes les missions actives
    active_missions = instance.missions.filter(
        status__in=['SCHEDULED', 'PICKUP_PENDING', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY']
    )

    for mission in active_missions:
        mission.status = MissionStatus.CANCELLED
        mission.save()

        # Annuler la réservation associée
        reservation = mission.reservation
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = timezone.now()
        reservation.save()

        # Notifier les parties
        Notification.objects.create(
            user=reservation.buyer,
            title=_("Mission annulée"),
            message=_("La mission pour '{}' a été annulée car le transporteur a supprimé son compte.").format(
                reservation.ad.title
            ),
            url=reservation.ad.get_absolute_url(),
            notification_type='MISSION_CANCELLED'
        )


# ============================================================================
# SIGNALS POUR LES TÂCHES AUTOMATIQUES
# ============================================================================

@receiver(pre_save, sender=Reservation)
def check_reservation_expiry(sender, instance, **kwargs):
    """
    Vérifier l'expiration des réservations
    """
    if instance.status == ReservationStatus.PENDING:
        settings = LogisticsSettings.load()
        expiry_hours = settings.reservation_expiry_hours

        if instance.created_at and (timezone.now() - instance.created_at).total_seconds() > expiry_hours * 3600:
            instance.status = ReservationStatus.CANCELLED
            instance.cancelled_at = timezone.now()
            instance.cancellation_reason = _("Expiration automatique")

            # Marquer l'annonce comme disponible
            instance.ad.is_reserved = False
            instance.ad.save(update_fields=['is_reserved', 'updated_at'])

            # Notifier l'acheteur
            Notification.objects.create(
                user=instance.buyer,
                title=_("Réservation expirée"),
                message=_("Votre réservation pour '{}' a expiré automatiquement.").format(
                    instance.ad.title
                ),
                url=instance.ad.get_absolute_url(),
                notification_type='RESERVATION_EXPIRED'
            )


@receiver(pre_save, sender=TransportProposal)
def check_proposal_expiry(sender, instance, **kwargs):
    """
    Vérifier l'expiration des propositions
    """
    if instance.status == TransportProposalStatus.PENDING and instance.expires_at:
        if timezone.now() > instance.expires_at:
            instance.status = TransportProposalStatus.EXPIRED

            # Notifier le transporteur
            Notification.objects.create(
                user=instance.carrier.user,
                title=_("Proposition expirée"),
                message=_("Votre proposition pour '{}' a expiré.").format(
                    instance.ad.title
                ),
                url=instance.ad.get_absolute_url(),
                notification_type='PROPOSAL_EXPIRED'
            )


# ============================================================================
# SIGNALS POUR LES STATISTIQUES ET CACHE
# ============================================================================

@receiver(post_save, sender=Reservation)
@receiver(post_delete, sender=Reservation)
def update_reservation_stats(sender, instance, **kwargs):
    """
    Mettre à jour les statistiques des réservations
    """
    # Mettre à jour le cache des statistiques du vendeur
    if hasattr(instance.ad.seller, 'profile'):
        cache_key = f'user_{instance.ad.seller.id}_seller_stats'
        cache.delete(cache_key)

    # Mettre à jour le cache des statistiques de l'acheteur
    cache_key = f'user_{instance.buyer.id}_buyer_stats'
    cache.delete(cache_key)

    # Mettre à jour le cache global
    cache.delete('global_reservation_stats')


@receiver(post_save, sender=Mission)
@receiver(post_delete, sender=Mission)
def update_mission_stats(sender, instance, **kwargs):
    """
    Mettre à jour les statistiques des missions
    """
    # Mettre à jour les statistiques du transporteur
    if instance.carrier:
        # Recalculer le taux de réussite
        total_missions = instance.carrier.missions.count()
        completed_missions = instance.carrier.missions.filter(status='DELIVERED').count()

        if total_missions > 0:
            instance.carrier.success_rate = (completed_missions / total_missions) * 100
            instance.carrier.save(update_fields=['success_rate', 'updated_at'])

        # Invalider le cache
        cache.delete(f'carrier_{instance.carrier.id}_stats')


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_reservation_notification(reservation, notification_type, recipient=None):
    """
    Créer une notification pour une réservation
    """
    if not recipient:
        recipient = reservation.ad.seller

    notification_map = {
        'CREATED': {
            'title': _("Nouvelle réservation"),
            'message': _("Votre annonce '{}' a été réservée par {}.").format(
                reservation.ad.title, reservation.buyer.username
            )
        },
        'CANCELLED': {
            'title': _("Réservation annulée"),
            'message': _("La réservation pour '{}' a été annulée.").format(
                reservation.ad.title
            )
        },
        'STATUS_CHANGED': {
            'title': _("Statut mis à jour"),
            'message': _("Le statut de la réservation pour '{}' est maintenant '{}'.").format(
                reservation.ad.title, reservation.get_status_display()
            )
        }
    }

    if notification_type in notification_map:
        Notification.objects.create(
            user=recipient,
            title=notification_map[notification_type]['title'],
            message=notification_map[notification_type]['message'],
            url=reservation.get_absolute_url(),
            notification_type=f'RESERVATION_{notification_type}'
        )


# ============================================================================
# CONNEXION DES SIGNALS
# ============================================================================

def connect_signals():
    """
    Connecter tous les signaux
    """
    # Les signaux sont automatiquement connectés via les décorateurs @receiver
    pass


def disconnect_signals():
    """
    Déconnecter tous les signaux (pour les tests)
    """
    from django.db.models import signals

    # Déconnecter tous les signaux de logistics
    signals.pre_save.disconnect(reservation_pre_save, sender=Reservation)
    signals.post_save.disconnect(reservation_post_save, sender=Reservation)
    signals.pre_delete.disconnect(reservation_pre_delete, sender=Reservation)

    signals.pre_save.disconnect(mission_pre_save, sender=Mission)
    signals.post_save.disconnect(mission_post_save, sender=Mission)

    signals.post_save.disconnect(tracking_event_post_save, sender=TrackingEvent)

    signals.pre_save.disconnect(route_pre_save, sender=Route)
    signals.post_save.disconnect(route_post_save, sender=Route)

    signals.pre_save.disconnect(transport_proposal_pre_save, sender=TransportProposal)
    signals.post_save.disconnect(transport_proposal_post_save, sender=TransportProposal)

    signals.post_save.disconnect(ad_post_save, sender=Ad)
    signals.post_save.disconnect(carrier_profile_post_save, sender=CarrierProfile)
    signals.pre_delete.disconnect(carrier_profile_pre_delete, sender=CarrierProfile)


# Import pour s'assurer que les signaux sont enregistrés
default_app_config = 'logistics.apps.LogisticsConfig'
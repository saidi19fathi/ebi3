# ~/ebi3/logistics/tasks.py

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, F, Count, Sum
from django.core.cache import cache
from django.conf import settings

from .models import (
    Reservation, Mission, Route, TransportProposal,
    ReservationStatus, MissionStatus, RouteStatus, TransportProposalStatus,
    LogisticsSettings
)
from users.models import Notification
from core.models import ActivityLog

logger = get_task_logger(__name__)


# ============================================================================
# TÂCHES DE NETTOYAGE ET MAINTENANCE
# ============================================================================

@shared_task(bind=True, max_retries=3)
def expire_old_reservations(self):
    """
    Expirer automatiquement les réservations en attente trop longtemps
    """
    try:
        settings_obj = LogisticsSettings.load()
        expiry_hours = settings_obj.reservation_expiry_hours

        expiry_threshold = timezone.now() - timezone.timedelta(hours=expiry_hours)

        # Trouver les réservations en attente expirées
        expired_reservations = Reservation.objects.filter(
            status=ReservationStatus.PENDING,
            created_at__lt=expiry_threshold
        )

        count = expired_reservations.count()

        for reservation in expired_reservations.select_related('ad', 'buyer'):
            # Marquer comme annulée
            reservation.status = ReservationStatus.CANCELLED
            reservation.cancelled_at = timezone.now()
            reservation.cancellation_reason = _("Expiration automatique")
            reservation.save()

            # Marquer l'annonce comme disponible
            reservation.ad.is_reserved = False
            reservation.ad.save(update_fields=['is_reserved', 'updated_at'])

            # Créer une notification
            Notification.objects.create(
                user=reservation.buyer,
                title=_("Réservation expirée"),
                message=_("Votre réservation pour '{}' a expiré automatiquement après {} heures.").format(
                    reservation.ad.title, expiry_hours
                ),
                url=reservation.ad.get_absolute_url(),
                notification_type='RESERVATION_EXPIRED'
            )

            # Log d'activité
            ActivityLog.objects.create(
                user=reservation.buyer,
                action_type='RESERVATION_EXPIRED_AUTO',
                object_id=reservation.id,
                details={
                    'ad_id': reservation.ad.id,
                    'ad_title': reservation.ad.title,
                    'waiting_hours': expiry_hours
                }
            )

        logger.info(f"Expiré {count} réservations anciennes")
        return {'expired_count': count}

    except Exception as exc:
        logger.error(f"Erreur expiration réservations: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def expire_old_proposals(self):
    """
    Expirer automatiquement les propositions de transport trop anciennes
    """
    try:
        expired_proposals = TransportProposal.objects.filter(
            status=TransportProposalStatus.PENDING,
            expires_at__lt=timezone.now()
        )

        count = expired_proposals.count()

        for proposal in expired_proposals.select_related('carrier', 'carrier__user', 'ad'):
            proposal.status = TransportProposalStatus.EXPIRED
            proposal.save()

            # Notification au transporteur
            Notification.objects.create(
                user=proposal.carrier.user,
                title=_("Proposition expirée"),
                message=_("Votre proposition pour '{}' a expiré.").format(proposal.ad.title),
                url=proposal.ad.get_absolute_url(),
                notification_type='PROPOSAL_EXPIRED'
            )

            # Log d'activité
            ActivityLog.objects.create(
                user=proposal.carrier.user,
                action_type='PROPOSAL_EXPIRED_AUTO',
                object_id=proposal.id,
                details={
                    'ad_id': proposal.ad.id,
                    'ad_title': proposal.ad.title
                }
            )

        logger.info(f"Expiré {count} propositions anciennes")
        return {'expired_count': count}

    except Exception as exc:
        logger.error(f"Erreur expiration propositions: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_route_statuses(self):
    """
    Mettre à jour les statuts des routes (actives -> terminées après la date)
    """
    try:
        # Marquer les routes comme terminées après la date d'arrivée
        completed_routes = Route.objects.filter(
            status=RouteStatus.ACTIVE,
            arrival_date__lt=timezone.now().date()
        )

        completed_count = completed_routes.update(status=RouteStatus.COMPLETED)

        # Marquer les routes comme complètes si pas de capacité
        full_routes = Route.objects.filter(
            status=RouteStatus.ACTIVE,
            available_weight=0,
            available_volume=0
        )

        full_count = full_routes.update(status=RouteStatus.FULL)

        logger.info(f"Mis à jour {completed_count} routes terminées, {full_count} routes complètes")
        return {'completed_count': completed_count, 'full_count': full_count}

    except Exception as exc:
        logger.error(f"Erreur mise à jour statuts routes: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_old_tracking_events(self, days_old=90):
    """
    Nettoyer les anciens événements de suivi
    """
    try:
        from .models import TrackingEvent

        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        deleted_count, _ = TrackingEvent.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Nettoyé {deleted_count} anciens événements de suivi")
        return {'deleted_count': deleted_count}

    except Exception as exc:
        logger.error(f"Erreur nettoyage événements suivi: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TÂCHES DE NOTIFICATION ET RAPPEL
# ============================================================================

@shared_task(bind=True, max_retries=3)
def send_delivery_reminders(self):
    """
    Envoyer des rappels pour les livraisons à venir
    """
    try:
        # Missions avec livraison dans les 24 heures
        upcoming_missions = Mission.objects.filter(
            status__in=[MissionStatus.IN_TRANSIT, MissionStatus.OUT_FOR_DELIVERY],
            estimated_delivery__range=[
                timezone.now(),
                timezone.now() + timezone.timedelta(hours=24)
            ]
        ).select_related('reservation', 'reservation__buyer', 'carrier', 'carrier__user')

        count = 0

        for mission in upcoming_missions:
            # Notification à l'acheteur
            Notification.objects.create(
                user=mission.reservation.buyer,
                title=_("Livraison prévue bientôt"),
                message=_("Votre objet '{}' est prévu pour livraison le {}.").format(
                    mission.reservation.ad.title,
                    mission.estimated_delivery.strftime('%d/%m/%Y à %H:%M')
                ),
                url=mission.get_absolute_url(),
                notification_type='DELIVERY_REMINDER'
            )

            # Notification au transporteur
            Notification.objects.create(
                user=mission.carrier.user,
                title=_("Livraison prévue"),
                message=_("La livraison pour '{}' est prévue le {}.").format(
                    mission.reservation.ad.title,
                    mission.estimated_delivery.strftime('%d/%m/%Y à %H:%M')
                ),
                url=mission.get_absolute_url(),
                notification_type='DELIVERY_REMINDER'
            )

            count += 1

        logger.info(f"Envoyé {count} rappels de livraison")
        return {'reminders_sent': count}

    except Exception as exc:
        logger.error(f"Erreur envoi rappels livraison: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_payment_reminders(self):
    """
    Envoyer des rappels pour les paiements en attente
    """
    try:
        # Réservations avec paiement en attente depuis plus de 24h
        unpaid_reservations = Reservation.objects.filter(
            status=ReservationStatus.PAYMENT_PENDING,
            created_at__lt=timezone.now() - timezone.timedelta(hours=24)
        ).select_related('buyer', 'ad')

        count = 0

        for reservation in unpaid_reservations:
            Notification.objects.create(
                user=reservation.buyer,
                title=_("Paiement en attente"),
                message=_("Votre réservation pour '{}' attend votre paiement.").format(
                    reservation.ad.title
                ),
                url=reservation.get_absolute_url(),
                notification_type='PAYMENT_REMINDER'
            )

            count += 1

        logger.info(f"Envoyé {count} rappels de paiement")
        return {'reminders_sent': count}

    except Exception as exc:
        logger.error(f"Erreur envoi rappels paiement: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_proposal_expiry_warnings(self, days_before=2):
    """
    Avertir les transporteurs de l'expiration proche de leurs propositions
    """
    try:
        expiry_threshold = timezone.now() + timezone.timedelta(days=days_before)

        expiring_proposals = TransportProposal.objects.filter(
            status=TransportProposalStatus.PENDING,
            expires_at__range=[timezone.now(), expiry_threshold]
        ).select_related('carrier', 'carrier__user', 'ad')

        count = 0

        for proposal in expiring_proposals:
            days_left = (proposal.expires_at - timezone.now()).days

            Notification.objects.create(
                user=proposal.carrier.user,
                title=_("Proposition expirant bientôt"),
                message=_("Votre proposition pour '{}' expire dans {} jours.").format(
                    proposal.ad.title, days_left
                ),
                url=proposal.get_absolute_url(),
                notification_type='PROPOSAL_EXPIRY_WARNING'
            )

            count += 1

        logger.info(f"Envoyé {count} avertissements d'expiration de propositions")
        return {'warnings_sent': count}

    except Exception as exc:
        logger.error(f"Erreur envoi avertissements expiration: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TÂCHES DE STATISTIQUES ET RAPPORTS
# ============================================================================

@shared_task(bind=True, max_retries=3)
def update_daily_statistics(self):
    """
    Mettre à jour les statistiques quotidiennes
    """
    try:
        today = timezone.now().date()
        yesterday = today - timezone.timedelta(days=1)

        # Statistiques des réservations
        reservation_stats = {
            'date': today.isoformat(),
            'total_reservations': Reservation.objects.count(),
            'new_today': Reservation.objects.filter(created_at__date=today).count(),
            'completed_today': Reservation.objects.filter(
                status=ReservationStatus.DELIVERED,
                actual_delivery_date=today
            ).count(),
            'cancelled_today': Reservation.objects.filter(
                status=ReservationStatus.CANCELLED,
                cancelled_at__date=today
            ).count(),
            'revenue_today': Reservation.objects.filter(
                status=ReservationStatus.DELIVERED,
                actual_delivery_date=today
            ).aggregate(total=Sum('total_price'))['total'] or 0
        }

        # Statistiques des missions
        mission_stats = {
            'date': today.isoformat(),
            'total_missions': Mission.objects.count(),
            'active_missions': Mission.objects.filter(
                status__in=[
                    MissionStatus.SCHEDULED, MissionStatus.PICKUP_PENDING,
                    MissionStatus.PICKED_UP, MissionStatus.IN_TRANSIT,
                    MissionStatus.OUT_FOR_DELIVERY
                ]
            ).count(),
            'delivered_today': Mission.objects.filter(
                status=MissionStatus.DELIVERED,
                actual_delivery__date=today
            ).count(),
            'delayed_missions': Mission.objects.filter(
                status=MissionStatus.DELAYED
            ).count()
        }

        # Statistiques des routes
        route_stats = {
            'date': today.isoformat(),
            'total_routes': Route.objects.count(),
            'active_routes': Route.objects.filter(status=RouteStatus.ACTIVE).count(),
            'routes_today': Route.objects.filter(departure_date=today).count(),
            'available_capacity': Route.objects.filter(
                status=RouteStatus.ACTIVE
            ).aggregate(
                total_weight=Sum('available_weight'),
                total_volume=Sum('available_volume')
            )
        }

        # Mettre en cache
        cache_key = f'logistics_daily_stats_{today}'
        cache.set(cache_key, {
            'reservations': reservation_stats,
            'missions': mission_stats,
            'routes': route_stats,
            'updated_at': timezone.now().isoformat()
        }, timeout=86400)  # 24 heures

        logger.info(f"Statistiques quotidiennes mises à jour pour {today}")
        return {
            'reservation_stats': reservation_stats,
            'mission_stats': mission_stats,
            'route_stats': route_stats
        }

    except Exception as exc:
        logger.error(f"Erreur mise à jour statistiques: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_weekly_report(self):
    """
    Générer un rapport hebdomadaire pour les administrateurs
    """
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives

        week_start = timezone.now() - timezone.timedelta(days=7)

        # Données du rapport
        report_data = {
            'period': f"{week_start.date()} - {timezone.now().date()}",
            'reservations': {
                'total': Reservation.objects.filter(created_at__gte=week_start).count(),
                'by_status': Reservation.objects.filter(
                    created_at__gte=week_start
                ).values('status').annotate(count=Count('id')),
                'revenue': Reservation.objects.filter(
                    created_at__gte=week_start,
                    status=ReservationStatus.DELIVERED
                ).aggregate(total=Sum('total_price'))['total'] or 0
            },
            'missions': {
                'completed': Mission.objects.filter(
                    status=MissionStatus.DELIVERED,
                    actual_delivery__gte=week_start
                ).count(),
                'in_progress': Mission.objects.filter(
                    status__in=[
                        MissionStatus.SCHEDULED, MissionStatus.PICKUP_PENDING,
                        MissionStatus.PICKED_UP, MissionStatus.IN_TRANSIT,
                        MissionStatus.OUT_FOR_DELIVERY
                    ]
                ).count()
            },
            'routes': {
                'created': Route.objects.filter(created_at__gte=week_start).count(),
                'active': Route.objects.filter(status=RouteStatus.ACTIVE).count()
            },
            'top_carriers': Mission.objects.filter(
                actual_delivery__gte=week_start
            ).values(
                'carrier__user__username',
                'carrier__company_name'
            ).annotate(
                missions=Count('id'),
                revenue=Sum('reservation__shipping_cost')
            ).order_by('-revenue')[:5]
        }

        # Rendre le template HTML
        html_content = render_to_string('logistics/emails/weekly_report.html', {
            'report': report_data
        })

        # Envoyer aux administrateurs
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_staff=True, is_active=True)

        for admin in admins:
            email = EmailMultiAlternatives(
                subject=f"Rapport hebdomadaire logistique - {report_data['period']}",
                body="Veuillez activer HTML pour voir ce message.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

        logger.info(f"Rapport hebdomadaire généré pour {report_data['period']}")
        return {'report_sent': True, 'admin_count': admins.count()}

    except Exception as exc:
        logger.error(f"Erreur génération rapport: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_carrier_ratings(self):
    """
    Recalculer les notes moyennes des transporteurs
    """
    try:
        from carriers.models import CarrierProfile
        from reviews.models import Review  # Supposant qu'une app reviews existe

        carriers = CarrierProfile.objects.all()

        for carrier in carriers:
            # Calculer la note moyenne à partir des avis
            reviews = Review.objects.filter(
                mission__carrier=carrier,
                mission__status=MissionStatus.DELIVERED
            )

            if reviews.exists():
                avg_rating = reviews.aggregate(
                    avg_communication=Avg('communication'),
                    avg_punctuality=Avg('punctuality'),
                    avg_handling=Avg('handling'),
                    avg_professionalism=Avg('professionalism')
                )

                # Calculer la note globale
                overall_rating = (
                    avg_rating['avg_communication'] +
                    avg_rating['avg_punctuality'] +
                    avg_rating['avg_handling'] +
                    avg_rating['avg_professionalism']
                ) / 4

                carrier.average_rating = round(overall_rating, 1)
                carrier.total_reviews = reviews.count()
                carrier.save(update_fields=['average_rating', 'total_reviews', 'updated_at'])

        logger.info(f"Notes de {carriers.count()} transporteurs mises à jour")
        return {'carriers_updated': carriers.count()}

    except Exception as exc:
        logger.error(f"Erreur mise à jour notes transporteurs: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TÂCHES D'INTÉGRATION ET SYNCHRONISATION
# ============================================================================

@shared_task(bind=True, max_retries=3)
def sync_with_shipping_apis(self):
    """
    Synchroniser avec les APIs de transport externes
    """
    try:
        # Missions en transit qui pourraient avoir un suivi externe
        missions = Mission.objects.filter(
            status=MissionStatus.IN_TRANSIT,
            tracking_number__isnull=False
        ).select_related('reservation')

        updated_count = 0

        for mission in missions:
            # Ici, on intègrerait avec une API de transporteur
            # Exemple: DHL, UPS, FedEx, etc.
            # Pour l'instant, c'est un placeholder

            # Simuler une mise à jour
            # En production, on appellerait l'API du transporteur
            pass

        logger.info(f"Synchronisé {updated_count} missions avec APIs externes")
        return {'missions_synced': updated_count}

    except Exception as exc:
        logger.error(f"Erreur synchronisation APIs: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def calculate_route_distances(self):
    """
    Calculer les distances pour les routes sans distance
    """
    try:
        from geopy.distance import geodesic

        routes_without_distance = Route.objects.filter(
            distance_km__isnull=True
        ).select_related('start_country', 'end_country')

        updated_count = 0

        for route in routes_without_distance:
            try:
                # Pour l'exemple, utiliser des coordonnées fictives
                # En production, utiliser geocoding pour obtenir les coordonnées
                start_coords = (48.8566, 2.3522)  # Paris
                end_coords = (51.5074, -0.1278)   # Londres

                distance = geodesic(start_coords, end_coords).kilometers
                route.distance_km = round(distance, 2)
                route.save(update_fields=['distance_km', 'updated_at'])

                updated_count += 1

            except Exception as e:
                logger.warning(f"Erreur calcul distance route {route.id}: {e}")
                continue

        logger.info(f"Calculé distances pour {updated_count} routes")
        return {'routes_updated': updated_count}

    except Exception as exc:
        logger.error(f"Erreur calcul distances routes: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TÂCHES DE SAUVEGARDE ET BACKUP
# ============================================================================

@shared_task(bind=True, max_retries=3)
def backup_logistics_data(self):
    """
    Sauvegarder les données logistiques importantes
    """
    try:
        import json
        from django.core.files.storage import default_storage
        from django.core.serializers import serialize

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        # Données à sauvegarder
        data_to_backup = {
            'timestamp': timestamp,
            'reservations': json.loads(serialize('json', Reservation.objects.all()[:1000])),
            'missions': json.loads(serialize('json', Mission.objects.all()[:1000])),
            'routes': json.loads(serialize('json', Route.objects.all()[:1000])),
            'statistics': {
                'total_reservations': Reservation.objects.count(),
                'total_missions': Mission.objects.count(),
                'total_routes': Route.objects.count(),
                'active_missions': Mission.objects.filter(
                    status__in=['IN_TRANSIT', 'OUT_FOR_DELIVERY']
                ).count()
            }
        }

        # Sauvegarder dans un fichier
        backup_filename = f'logistics_backup_{timestamp}.json'
        backup_content = json.dumps(data_to_backup, indent=2, ensure_ascii=False)

        # Sauvegarder dans le stockage par défaut
        default_storage.save(f'backups/{backup_filename}', backup_content)

        logger.info(f"Sauvegarde créée: {backup_filename}")
        return {'backup_filename': backup_filename}

    except Exception as exc:
        logger.error(f"Erreur sauvegarde données: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TÂCHES DE SURVEILLANCE ET ALERTES
# ============================================================================

@shared_task(bind=True, max_retries=3)
def monitor_system_health(self):
    """
    Surveiller la santé du système logistique
    """
    try:
        alerts = []

        # Vérifier les missions en retard
        delayed_missions = Mission.objects.filter(
            status__in=[MissionStatus.IN_TRANSIT, MissionStatus.OUT_FOR_DELIVERY],
            estimated_delivery__lt=timezone.now()
        ).count()

        if delayed_missions > 0:
            alerts.append({
                'type': 'DELAYED_MISSIONS',
                'count': delayed_missions,
                'message': f"{delayed_missions} missions sont en retard"
            })

        # Vérifier les réservations en attente de paiement
        unpaid_count = Reservation.objects.filter(
            status=ReservationStatus.PAYMENT_PENDING,
            created_at__lt=timezone.now() - timezone.timedelta(hours=48)
        ).count()

        if unpaid_count > 0:
            alerts.append({
                'type': 'UNPAID_RESERVATIONS',
                'count': unpaid_count,
                'message': f"{unpaid_count} réservations attendent un paiement depuis plus de 48h"
            })

        # Vérifier les routes sans capacité
        full_routes = Route.objects.filter(
            status=RouteStatus.ACTIVE,
            available_weight=0,
            available_volume=0
        ).count()

        if full_routes > 0:
            alerts.append({
                'type': 'FULL_ROUTES',
                'count': full_routes,
                'message': f"{full_routes} routes sont pleines mais toujours marquées comme actives"
            })

        # Enregistrer les alertes
        if alerts:
            cache_key = 'logistics_health_alerts'
            cache.set(cache_key, alerts, timeout=3600)  # 1 heure

            # Notifier les administrateurs si nécessaire
            if len(alerts) > 3:  # Seuil configurable
                from django.contrib.auth import get_user_model
                User = get_user_model()

                for admin in User.objects.filter(is_staff=True, is_superuser=True):
                    Notification.objects.create(
                        user=admin,
                        title=_("Alertes système logistique"),
                        message=_("{} problèmes détectés dans le système logistique.").format(len(alerts)),
                        url='/admin/logistics/',
                        notification_type='SYSTEM_ALERT',
                        priority='HIGH'
                    )

        logger.info(f"Surveillance système: {len(alerts)} alertes détectées")
        return {'alerts': alerts, 'alert_count': len(alerts)}

    except Exception as exc:
        logger.error(f"Erreur surveillance système: {exc}")
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# CONFIGURATION DES TÂCHES PÉRIODIQUES
# ============================================================================

CELERY_BEAT_SCHEDULE = {
    # Nettoyage quotidien
    'expire-old-reservations': {
        'task': 'logistics.tasks.expire_old_reservations',
        'schedule': 3600,  # Toutes les heures
    },
    'expire-old-proposals': {
        'task': 'logistics.tasks.expire_old_proposals',
        'schedule': 3600,  # Toutes les heures
    },
    'update-route-statuses': {
        'task': 'logistics.tasks.update_route_statuses',
        'schedule': 1800,  # Toutes les 30 minutes
    },

    # Notifications
    'send-delivery-reminders': {
        'task': 'logistics.tasks.send_delivery_reminders',
        'schedule': 3600,  # Toutes les heures
    },
    'send-payment-reminders': {
        'task': 'logistics.tasks.send_payment_reminders',
        'schedule': 7200,  # Toutes les 2 heures
    },
    'send-proposal-expiry-warnings': {
        'task': 'logistics.tasks.send_proposal_expiry_warnings',
        'schedule': 86400,  # Tous les jours
    },

    # Statistiques
    'update-daily-statistics': {
        'task': 'logistics.tasks.update_daily_statistics',
        'schedule': 300,  # Toutes les 5 minutes
    },
    'generate-weekly-report': {
        'task': 'logistics.tasks.generate_weekly_report',
        'schedule': 604800,  # Toutes les semaines
    },
    'update-carrier-ratings': {
        'task': 'logistics.tasks.update_carrier_ratings',
        'schedule': 86400,  # Tous les jours
    },

    # Maintenance
    'cleanup-old-tracking-events': {
        'task': 'logistics.tasks.cleanup_old_tracking_events',
        'schedule': 86400,  # Tous les jours
    },
    'calculate-route-distances': {
        'task': 'logistics.tasks.calculate_route_distances',
        'schedule': 43200,  # Toutes les 12 heures
    },

    # Surveillance
    'monitor-system-health': {
        'task': 'logistics.tasks.monitor_system_health',
        'schedule': 900,  # Toutes les 15 minutes
    },

    # Sauvegarde
    'backup-logistics-data': {
        'task': 'logistics.tasks.backup_logistics_data',
        'schedule': 86400,  # Tous les jours
    },
}
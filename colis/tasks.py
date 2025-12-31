# ~/ebi3/colis/tasks.py
"""
Tâches asynchrones pour l'application colis
Utilise Celery pour les opérations longues, périodiques ou groupées
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict, Any
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.db.models import Count, Q, F, Avg, Sum, Case, When, IntegerField
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.sites.models import Site
from celery import shared_task, group, chain, chord
from celery.utils.log import get_task_logger

from .models import (
    Package, TransportOffer, PackageCategory, PackageImage,
    PackageView, PackageFavorite, PackageReport
)
from users.models import User
from messaging.models import Conversation, Message
from carriers.models import Carrier, CarrierReview

logger = get_task_logger(__name__)


# ============================================================================
# TÂCHES POUR LES PACKAGES
# ============================================================================

@shared_task(name='colis.tasks.update_package_statuses')
def update_package_statuses():
    """
    Tâche périodique pour mettre à jour les statuts des colis
    - Expiration des colis disponibles
    - Passage en transit après date de départ
    - Passage en livré après date d'arrivée
    """
    now = timezone.now()
    updated_count = 0

    # Colis disponibles qui ont expiré
    expired_packages = Package.objects.filter(
        status=Package.Status.AVAILABLE,
        available_until__lt=now.date()
    )

    for package in expired_packages:
        package.status = Package.Status.EXPIRED
        package.expired_at = now
        package.save(update_fields=['status', 'expired_at', 'updated_at'])
        updated_count += 1

        # Notifier l'expéditeur
        send_package_status_notification.delay(
            package_id=package.id,
            old_status='AVAILABLE',
            new_status='EXPIRED'
        )

    # Colis réservés dont la date de départ est passée
    reserved_to_transit = Package.objects.filter(
        status=Package.Status.RESERVED,
        departure_date__lt=now.date()
    )

    for package in reserved_to_transit:
        package.status = Package.Status.IN_TRANSIT
        package.save(update_fields=['status', 'updated_at'])
        updated_count += 1

        send_package_status_notification.delay(
            package_id=package.id,
            old_status='RESERVED',
            new_status='IN_TRANSIT'
        )

    # Colis en transit dont la date d'arrivée est passée
    transit_to_delivered = Package.objects.filter(
        status=Package.Status.IN_TRANSIT,
        arrival_date__lt=now.date()
    )

    for package in transit_to_delivered:
        package.status = Package.Status.DELIVERED
        package.delivered_at = now
        package.save(update_fields=['status', 'delivered_at', 'updated_at'])
        updated_count += 1

        send_package_status_notification.delay(
            package_id=package.id,
            old_status='IN_TRANSIT',
            new_status='DELIVERED'
        )

    logger.info(f"Mise à jour de {updated_count} statuts de colis")
    return updated_count


@shared_task(name='colis.tasks.cleanup_old_packages')
def cleanup_old_packages(days_old: int = 365):
    """
    Nettoie les anciens colis (archivage ou suppression)
    Args:
        days_old: Nombre de jours après lesquels un colis est considéré comme ancien
    """
    cutoff_date = timezone.now() - timedelta(days=days_old)
    old_packages = Package.objects.filter(
        Q(created_at__lt=cutoff_date) &
        Q(status__in=['DELIVERED', 'CANCELLED', 'EXPIRED'])
    )

    # Archive les anciens colis
    archived_count = old_packages.update(
        is_archived=True,
        archived_at=timezone.now()
    )

    # Supprime les colis très anciens (plus de 2 ans)
    very_old_cutoff = timezone.now() - timedelta(days=730)
    very_old_packages = Package.objects.filter(
        created_at__lt=very_old_cutoff,
        is_archived=True
    )

    deleted_count = very_old_packages.count()
    # Note: La suppression est commentée par sécurité
    # very_old_packages.delete()

    logger.info(f"Archivé {archived_count} colis, {deleted_count} supprimables")
    return {'archived': archived_count, 'deletable': deleted_count}


@shared_task(name='colis.tasks.calculate_package_statistics')
def calculate_package_statistics():
    """
    Calcule les statistiques globales des colis et met en cache
    """
    stats = Package.objects.aggregate(
        total_packages=Count('id'),
        available_packages=Count('id', filter=Q(status='AVAILABLE')),
        reserved_packages=Count('id', filter=Q(status='RESERVED')),
        in_transit_packages=Count('id', filter=Q(status='IN_TRANSIT')),
        delivered_packages=Count('id', filter=Q(status='DELIVERED')),
        total_weight=Sum('weight'),
        average_price=Avg('price'),
        total_offers=Sum('offers_count'),
    )

    # Statistiques par catégorie
    category_stats = PackageCategory.objects.annotate(
        package_count=Count('packages', filter=Q(packages__status='AVAILABLE'))
    ).values('id', 'name', 'package_count').order_by('-package_count')[:10]

    # Top destinations
    top_destinations = Package.objects.filter(status='AVAILABLE').values(
        'country_to', 'city_to'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    cache_data = {
        'global_stats': stats,
        'category_stats': list(category_stats),
        'top_destinations': list(top_destinations),
        'calculated_at': timezone.now().isoformat(),
    }

    # Mettre en cache pour 1 heure
    cache.set('colis_statistics', cache_data, timeout=3600)
    logger.info("Statistiques des colis calculées et mises en cache")

    return cache_data


# ============================================================================
# TÂCHES POUR LES OFFRES DE TRANSPORT
# ============================================================================

@shared_task(name='colis.tasks.process_expired_offers')
def process_expired_offers():
    """
    Traite les offres de transport expirées
    - Marque les offres comme expirées
    - Notifie les transporteurs
    """
    expired_offers = TransportOffer.objects.filter(
        status=TransportOffer.Status.PENDING,
        expires_at__lt=timezone.now()
    )

    expired_count = expired_offers.count()

    for offer in expired_offers:
        offer.status = TransportOffer.Status.EXPIRED
        offer.save(update_fields=['status', 'updated_at'])

        # Notifier le transporteur
        send_transport_offer_notification.delay(
            offer_id=offer.id,
            notification_type='OFFER_EXPIRED'
        )

        # Notifier l'expéditeur si c'était la seule offre
        package_offers = TransportOffer.objects.filter(
            package=offer.package,
            status=TransportOffer.Status.PENDING
        ).count()

        if package_offers == 0:
            send_package_notification.delay(
                package_id=offer.package.id,
                notification_type='NO_ACTIVE_OFFERS'
            )

    logger.info(f"Traiter {expired_count} offres expirées")
    return expired_count


@shared_task(name='colis.tasks.find_matching_carriers')
def find_matching_carriers(package_id: int):
    """
    Trouve les transporteurs correspondant à un colis
    Args:
        package_id: ID du colis
    """
    try:
        package = Package.objects.get(id=package_id)
    except Package.DoesNotExist:
        logger.error(f"Colis {package_id} non trouvé")
        return 0

    # Critères de correspondance
    matching_carriers = Carrier.objects.filter(
        # Disponibilité
        is_available=True,
        status='APPROVED',
        # Capacités
        max_weight__gte=package.weight or 0,
        max_volume__gte=package.volume or 0,
        # Destination
        routes__end_country=package.country_to,
        routes__end_city__icontains=package.city_to,
        routes__is_active=True,
        routes__departure_date__gte=package.departure_date,
    ).distinct()

    matching_count = matching_carriers.count()
    logger.info(f"Trouvé {matching_count} transporteurs pour le colis {package_id}")

    # Notifier les transporteurs correspondants
    for carrier in matching_carriers:
        send_carrier_match_notification.delay(
            carrier_id=carrier.id,
            package_id=package.id
        )

    return matching_count


@shared_task(name='colis.tasks.create_auto_offer')
def create_auto_offer(package_id: int, carrier_id: int):
    """
    Crée une offre automatique pour un transporteur correspondant
    """
    try:
        package = Package.objects.get(id=package_id)
        carrier = Carrier.objects.get(id=carrier_id)
    except (Package.DoesNotExist, Carrier.DoesNotExist) as e:
        logger.error(f"Erreur création offre auto: {e}")
        return None

    # Calcul du prix automatique (prix du colis + marge transporteur)
    base_price = package.price or Decimal('0.00')
    carrier_margin = carrier.base_price_per_km or Decimal('1.00')

    # Estimation de distance (simplifiée)
    estimated_distance = Decimal('500.00')  # En km
    transport_price = estimated_distance * carrier_margin

    total_price = base_price + transport_price

    # Création de l'offre
    offer = TransportOffer.objects.create(
        package=package,
        carrier=carrier.user,
        price=total_price,
        currency=package.currency,
        notes=f"Offre automatique générée le {timezone.now().strftime('%d/%m/%Y')}",
        expires_at=timezone.now() + timedelta(days=7)
    )

    logger.info(f"Offre automatique {offer.id} créée pour transporteur {carrier_id}")

    # Notifier l'expéditeur
    send_transport_offer_notification.delay(
        offer_id=offer.id,
        notification_type='NEW_AUTO_OFFER'
    )

    return offer.id


# ============================================================================
# TÂCHES DE NOTIFICATION
# ============================================================================

@shared_task(name='colis.tasks.send_package_status_notification')
def send_package_status_notification(package_id: int, old_status: str, new_status: str):
    """
    Envoie une notification de changement de statut
    """
    try:
        package = Package.objects.get(id=package_id)
        sender = package.sender
    except Package.DoesNotExist:
        logger.error(f"Colis {package_id} non trouvé")
        return False

    # Préparer l'email
    subject = f"Colis '{package.title}' - Statut mis à jour"

    context = {
        'package': package,
        'old_status': old_status,
        'new_status': new_status,
        'new_status_display': package.get_status_display(),
        'site': Site.objects.get_current(),
        'user': sender,
    }

    html_content = render_to_string('colis/emails/package_status_change.html', context)
    text_content = render_to_string('colis/emails/package_status_change.txt', context)

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[sender.email],
            reply_to=[settings.REPLY_TO_EMAIL]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Notification de statut envoyée pour le colis {package_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification: {e}")
        return False


@shared_task(name='colis.tasks.send_transport_offer_notification')
def send_transport_offer_notification(offer_id: int, notification_type: str):
    """
    Envoie des notifications relatives aux offres de transport
    Types: NEW_OFFER, OFFER_ACCEPTED, OFFER_REJECTED, OFFER_EXPIRED
    """
    try:
        offer = TransportOffer.objects.get(id=offer_id)
        carrier = offer.carrier
        package = offer.package
    except TransportOffer.DoesNotExist:
        logger.error(f"Offre {offer_id} non trouvé")
        return False

    # Déterminer le sujet et le destinataire
    if notification_type in ['NEW_OFFER', 'OFFER_ACCEPTED', 'OFFER_REJECTED']:
        recipient = package.sender
        recipient_type = 'sender'
    elif notification_type in ['OFFER_EXPIRED', 'NEW_AUTO_OFFER']:
        recipient = carrier
        recipient_type = 'carrier'
    else:
        logger.error(f"Type de notification invalide: {notification_type}")
        return False

    # Mapper les types aux sujets
    subject_map = {
        'NEW_OFFER': f"Nouvelle offre pour votre colis '{package.title}'",
        'OFFER_ACCEPTED': f"Votre offre pour le colis '{package.title}' a été acceptée",
        'OFFER_REJECTED': f"Votre offre pour le colis '{package.title}' a été refusée",
        'OFFER_EXPIRED': f"Votre offre pour le colis '{package.title}' a expiré",
        'NEW_AUTO_OFFER': f"Nouvelle opportunité de transport : {package.title}",
    }

    subject = subject_map.get(notification_type, "Mise à jour de votre offre")

    context = {
        'offer': offer,
        'package': package,
        'notification_type': notification_type,
        'recipient_type': recipient_type,
        'site': Site.objects.get_current(),
        'user': recipient,
    }

    template_name = f'colis/emails/transport_offer_{notification_type.lower()}.html'
    txt_template_name = f'colis/emails/transport_offer_{notification_type.lower()}.txt'

    try:
        html_content = render_to_string(template_name, context)
        text_content = render_to_string(txt_template_name, context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
            reply_to=[settings.REPLY_TO_EMAIL]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Notification {notification_type} envoyée pour l'offre {offer_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification offre: {e}")
        return False


@shared_task(name='colis.tasks.send_carrier_match_notification')
def send_carrier_match_notification(carrier_id: int, package_id: int):
    """
    Notifie un transporteur d'un colis correspondant à ses critères
    """
    try:
        carrier = Carrier.objects.get(id=carrier_id)
        package = Package.objects.get(id=package_id)
    except (Carrier.DoesNotExist, Package.DoesNotExist) as e:
        logger.error(f"Erreur notification match: {e}")
        return False

    subject = f"💼 Nouveau colis correspondant à votre profil"

    context = {
        'carrier': carrier,
        'package': package,
        'site': Site.objects.get_current(),
        'user': carrier.user,
    }

    try:
        html_content = render_to_string('colis/emails/carrier_match_notification.html', context)
        text_content = render_to_string('colis/emails/carrier_match_notification.txt', context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[carrier.user.email],
            reply_to=[settings.REPLY_TO_EMAIL]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Notification de match envoyée au transporteur {carrier_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification match: {e}")
        return False


@shared_task(name='colis.tasks.send_package_notification')
def send_package_notification(package_id: int, notification_type: str):
    """
    Notifications générales sur les colis
    Types: NO_ACTIVE_OFFERS, DELIVERY_REMINDER, REVIEW_REMINDER
    """
    try:
        package = Package.objects.get(id=package_id)
    except Package.DoesNotExist:
        logger.error(f"Colis {package_id} non trouvé")
        return False

    # Déterminer le destinataire
    if notification_type == 'NO_ACTIVE_OFFERS':
        recipient = package.sender
        subject = f"⏰ Aucune offre active pour votre colis '{package.title}'"
    elif notification_type == 'DELIVERY_REMINDER':
        recipient = package.carrier if package.carrier else package.sender
        subject = f"📦 Rappel : Livraison prévue pour '{package.title}'"
    elif notification_type == 'REVIEW_REMINDER':
        recipient = package.sender
        subject = f"⭐ N'oubliez pas d'évaluer le transport de '{package.title}'"
    else:
        logger.error(f"Type de notification invalide: {notification_type}")
        return False

    context = {
        'package': package,
        'notification_type': notification_type,
        'site': Site.objects.get_current(),
        'user': recipient,
    }

    try:
        html_content = render_to_string(f'colis/emails/package_{notification_type.lower()}.html', context)
        text_content = render_to_string(f'colis/emails/package_{notification_type.lower()}.txt', context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
            reply_to=[settings.REPLY_TO_EMAIL]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Notification {notification_type} envoyée pour colis {package_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi notification colis: {e}")
        return False


# ============================================================================
# TÂCHES DE RAPPORT ET ANALYSE
# ============================================================================

@shared_task(name='colis.tasks.generate_package_report')
def generate_package_report(user_id: int, report_type: str, start_date=None, end_date=None):
    """
    Génère un rapport personnalisé pour un utilisateur
    Types: MONTHLY, QUARTERLY, YEARLY, CUSTOM
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"Utilisateur {user_id} non trouvé")
        return None

    # Déterminer la période
    if not end_date:
        end_date = timezone.now()
    if not start_date:
        if report_type == 'MONTHLY':
            start_date = end_date - timedelta(days=30)
        elif report_type == 'QUARTERLY':
            start_date = end_date - timedelta(days=90)
        elif report_type == 'YEARLY':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)  # Par défaut

    # Récupérer les données
    packages = Package.objects.filter(
        sender=user,
        created_at__range=[start_date, end_date]
    )

    offers = TransportOffer.objects.filter(
        carrier=user,
        created_at__range=[start_date, end_date]
    )

    # Calculer les statistiques
    report_data = {
        'user': user.username,
        'report_type': report_type,
        'period': {'start': start_date, 'end': end_date},
        'package_stats': {
            'total': packages.count(),
            'available': packages.filter(status='AVAILABLE').count(),
            'reserved': packages.filter(status='RESERVED').count(),
            'delivered': packages.filter(status='DELIVERED').count(),
            'total_price': packages.aggregate(Sum('price'))['price__sum'] or 0,
            'average_price': packages.aggregate(Avg('price'))['price__avg'] or 0,
        },
        'offer_stats': {
            'total': offers.count(),
            'accepted': offers.filter(status='ACCEPTED').count(),
            'pending': offers.filter(status='PENDING').count(),
            'rejected': offers.filter(status='REJECTED').count(),
            'total_value': offers.aggregate(Sum('price'))['price__sum'] or 0,
            'acceptance_rate': (offers.filter(status='ACCEPTED').count() / max(offers.count(), 1)) * 100,
        },
        'popular_categories': packages.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')[:5],
        'top_destinations': packages.values('country_to', 'city_to').annotate(
            count=Count('id')
        ).order_by('-count')[:5],
    }

    logger.info(f"Rapport généré pour l'utilisateur {user_id}")

    # Option: Envoyer le rapport par email
    # send_report_email.delay(user_id, report_data, report_type)

    return report_data


@shared_task(name='colis.tasks.calculate_carrier_performance')
def calculate_carrier_performance(carrier_id: int = None):
    """
    Calcule les performances d'un transporteur ou de tous les transporteurs
    """
    if carrier_id:
        carriers = Carrier.objects.filter(id=carrier_id)
    else:
        carriers = Carrier.objects.filter(status='APPROVED')

    performance_data = []

    for carrier in carriers:
        # Offres du transporteur
        offers = TransportOffer.objects.filter(carrier=carrier.user)

        # Colis transportés
        packages = Package.objects.filter(carrier=carrier.user)

        # Calcul des métriques
        metrics = {
            'carrier_id': carrier.id,
            'carrier_name': carrier.company_name or carrier.user.username,
            'total_offers': offers.count(),
            'accepted_offers': offers.filter(status='ACCEPTED').count(),
            'offer_acceptance_rate': (offers.filter(status='ACCEPTED').count() / max(offers.count(), 1)) * 100,
            'total_packages': packages.count(),
            'delivered_packages': packages.filter(status='DELIVERED').count(),
            'delivery_success_rate': (packages.filter(status='DELIVERED').count() / max(packages.count(), 1)) * 100,
            'average_rating': carrier.average_rating,
            'total_revenue': offers.filter(status='ACCEPTED').aggregate(
                Sum('price')
            )['price__sum'] or Decimal('0.00'),
            'response_time_avg': None,  # À calculer avec les timestamps
            'last_active': carrier.updated_at,
        }

        performance_data.append(metrics)

        # Mettre à jour les statistiques du transporteur
        carrier.total_missions = metrics['total_packages']
        carrier.completed_missions = metrics['delivered_packages']
        carrier.success_rate = metrics['delivery_success_rate']
        carrier.save(update_fields=['total_missions', 'completed_missions', 'success_rate', 'updated_at'])

    logger.info(f"Performances calculées pour {len(performance_data)} transporteurs")
    return performance_data


# ============================================================================
# TÂCHES DE MAINTENANCE
# ============================================================================

@shared_task(name='colis.tasks.cleanup_old_data')
def cleanup_old_data():
    """
    Nettoie les anciennes données pour optimiser la base
    """
    now = timezone.now()
    cleanup_tasks = []

    # 1. Vues de plus de 30 jours
    old_views = PackageView.objects.filter(
        viewed_at__lt=now - timedelta(days=30)
    )
    views_deleted = old_views.count()
    old_views.delete()

    # 2. Images orphelines (sans package)
    orphan_images = PackageImage.objects.filter(package__isnull=True)
    images_deleted = orphan_images.count()
    orphan_images.delete()

    # 3. Signalements résolus de plus de 90 jours
    old_reports = PackageReport.objects.filter(
        status='RESOLVED',
        resolved_at__lt=now - timedelta(days=90)
    )
    reports_deleted = old_reports.count()
    old_reports.delete()

    # 4. Favoris de colis supprimés
    invalid_favorites = PackageFavorite.objects.filter(
        Q(package__isnull=True) | Q(user__isnull=True)
    )
    favorites_deleted = invalid_favorites.count()
    invalid_favorites.delete()

    results = {
        'views_deleted': views_deleted,
        'images_deleted': images_deleted,
        'reports_deleted': reports_deleted,
        'favorites_deleted': favorites_deleted,
        'total_deleted': views_deleted + images_deleted + reports_deleted + favorites_deleted,
    }

    logger.info(f"Données nettoyées: {results}")
    return results


@shared_task(name='colis.tasks.recalculate_all_volumes')
def recalculate_all_volumes():
    """
    Recalcule les volumes de tous les colis (en cas de bug de calcul)
    """
    packages = Package.objects.filter(
        length__isnull=False,
        width__isnull=False,
        height__isnull=False
    )

    updated_count = 0

    for package in packages:
        # Recalculer le volume
        old_volume = package.volume
        new_volume = (package.length * package.width * package.height) / 1000

        if old_volume != new_volume:
            package.volume = new_volume
            package.save(update_fields=['volume', 'updated_at'])
            updated_count += 1

    logger.info(f"Volumes recalculés: {updated_count}/{packages.count()} mis à jour")
    return {'total': packages.count(), 'updated': updated_count}


@shared_task(name='colis.tasks.update_category_counts')
def update_category_counts():
    """
    Met à jour les compteurs de colis par catégorie
    """
    categories = PackageCategory.objects.all()

    for category in categories:
        # Compter les colis actifs
        active_count = category.packages.filter(status='AVAILABLE').count()

        if category.package_count != active_count:
            category.package_count = active_count
            category.save(update_fields=['package_count', 'updated_at'])

    logger.info(f"Compteurs de catégories mis à jour: {categories.count()} catégories")
    return categories.count()


# ============================================================================
# TÂCHES GROUPÉES ET WORKFLOWS COMPLEXES
# ============================================================================

@shared_task(name='colis.tasks.daily_maintenance_workflow')
def daily_maintenance_workflow():
    """
    Workflow de maintenance quotidienne
    S'exécute une fois par jour
    """
    # Créer un groupe de tâches parallèles
    parallel_tasks = group(
        update_package_statuses.s(),
        process_expired_offers.s(),
        cleanup_old_data.s(),
    )

    # Chaîne de tâches séquentielles après les parallèles
    workflow = chain(
        parallel_tasks,
        calculate_package_statistics.s(),
        update_category_counts.s(),
    )

    result = workflow.apply_async()
    logger.info("Workflow de maintenance quotidienne démarré")
    return result.id


@shared_task(name='colis.tasks.weekly_report_workflow')
def weekly_report_workflow():
    """
    Workflow de rapports hebdomadaires
    """
    # 1. Générer les rapports pour les utilisateurs actifs
    active_users = User.objects.filter(
        is_active=True,
        last_login__gte=timezone.now() - timedelta(days=30)
    ).values_list('id', flat=True)

    # 2. Créer des tâches pour chaque utilisateur (limité aux 100 premiers)
    user_tasks = [generate_package_report.s(user_id, 'WEEKLY') for user_id in active_users[:100]]

    # 3. Exécuter en parallèle
    if user_tasks:
        group(user_tasks).apply_async()

    # 4. Générer les rapports admin
    admin_tasks = chain(
        calculate_carrier_performance.s(),
        calculate_package_statistics.s(),
    )

    admin_tasks.apply_async()

    logger.info(f"Workflow de rapports hebdomadaires démarré pour {len(user_tasks)} utilisateurs")
    return len(user_tasks)


# ============================================================================
# TÂCHES D'INTÉGRATION AVEC AUTRES APPLICATIONS
# ============================================================================

@shared_task(name='colis.tasks.sync_with_carriers_app')
def sync_with_carriers_app():
    """
    Synchronise les données avec l'application carriers
    """
    # Mettre à jour les statistiques des transporteurs basées sur les colis
    carrier_stats = Package.objects.filter(
        carrier__isnull=False,
        status='DELIVERED'
    ).values('carrier').annotate(
        delivered_count=Count('id'),
        total_revenue=Sum('price'),
        avg_rating=Avg('carrier_reviews__rating')
    )

    for stat in carrier_stats:
        carrier_id = stat['carrier']
        try:
            carrier = Carrier.objects.get(user_id=carrier_id)
            carrier.completed_missions = stat['delivered_count']
            # Mettre à jour d'autres champs si nécessaire
            carrier.save(update_fields=['completed_missions', 'updated_at'])
        except Carrier.DoesNotExist:
            continue

    logger.info(f"Données synchronisées avec carriers: {len(carrier_stats)} transporteurs")
    return len(carrier_stats)


@shared_task(name='colis.tasks.create_demo_packages')
def create_demo_packages(count: int = 10, user_id: int = None):
    """
    Crée des colis de démonstration pour le développement
    """
    from faker import Faker
    import random

    fake = Faker('fr_FR')

    # Récupérer l'utilisateur ou le premier admin
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = User.objects.filter(is_staff=True).first()
    else:
        user = User.objects.filter(is_staff=True).first()

    if not user:
        logger.error("Aucun utilisateur trouvé pour créer des colis de démonstration")
        return 0

    # Récupérer des catégories existantes
    categories = PackageCategory.objects.all()[:5]
    if not categories:
        logger.error("Aucune catégorie trouvée")
        return 0

    created_count = 0

    for i in range(count):
        category = random.choice(categories)
        weight = random.uniform(1.0, 100.0)
        price = random.uniform(10.0, 500.0)

        package = Package.objects.create(
            title=fake.sentence(nb_words=6),
            description=fake.paragraph(nb_sentences=3),
            sender=user,
            category=category,
            weight=round(weight, 3),
            length=random.uniform(10.0, 200.0),
            width=random.uniform(10.0, 150.0),
            height=random.uniform(5.0, 100.0),
            price=round(price, 2),
            currency='EUR',
            country_from='FR',
            city_from=fake.city(),
            country_to=random.choice(['MA', 'TN', 'DZ']),
            city_to=fake.city(),
            status=Package.Status.AVAILABLE,
            available_from=timezone.now().date(),
            available_until=timezone.now().date() + timedelta(days=30),
        )

        # Créer quelques images de démonstration
        for j in range(random.randint(1, 3)):
            PackageImage.objects.create(
                package=package,
                image=f"demo/package_{i}_image_{j}.jpg",
                caption=fake.sentence(nb_words=4),
                is_primary=(j == 0),
            )

        created_count += 1

    logger.info(f"Créé {created_count} colis de démonstration")
    return created_count
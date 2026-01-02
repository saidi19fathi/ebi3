"""
Tâches asynchrones Celery pour le traitement des traductions.
"""
import logging
import time
from celery import shared_task, group
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings

from .models import TranslationJob, Translation
from .api import get_api_client

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_translation_job(self, job_id):
    """
    Traite un travail de traduction asynchrone.
    """
    try:
        job = TranslationJob.objects.get(id=job_id)
    except TranslationJob.DoesNotExist:
        logger.error(f"Travail {job_id} introuvable")
        return

    # Vérifie si déjà en cours
    if job.status == 'processing':
        logger.info(f"Travail {job_id} déjà en cours")
        return

    # Marque comme en cours
    job.mark_as_processing()

    try:
        # Récupère l'instance du modèle
        model_class = job.content_type.model_class()
        if not model_class:
            raise ValueError(f"Modèle {job.content_type} introuvable")

        instance = model_class.objects.get(pk=job.object_id)

        # Traduit vers chaque langue cible
        api_client = get_api_client()
        failed_languages = []

        for target_lang in job.target_languages:
            if target_lang in job.completed_languages:
                continue

            try:
                # Appel API
                result = api_client.translate_text(
                    text=job.original_text,
                    source_lang=job.source_language,
                    target_lang=target_lang
                )

                if result.get('success', True):
                    # Sauvegarde la traduction
                    translation = Translation.objects.create(
                        content_type=job.content_type,
                        object_id=job.object_id,
                        field_name=job.field_name,
                        language=target_lang,
                        translated_text=result['translated_text'],
                        source_text=job.original_text,
                        source_language=job.source_language,
                        confidence_score=result.get('confidence_score'),
                        translation_job=job,
                        quality='auto',
                    )

                    job.add_completed_language(target_lang)
                    job.api_calls_count += 1

                    logger.info(f"Traduit {job.source_language}->{target_lang} pour {job}")

                else:
                    failed_languages.append(target_lang)
                    job.add_failed_language(target_lang, result.get('error'))

            except Exception as e:
                logger.error(f"Erreur traduction {target_lang}: {e}")
                failed_languages.append(target_lang)
                job.add_failed_language(target_lang, str(e))

        # Met à jour le statut final
        if failed_languages and job.completed_languages:
            job.status = 'partial'
        elif not job.completed_languages:
            job.status = 'failed'
            job.error_message = "Toutes les traductions ont échoué"
        else:
            job.status = 'completed'

        job.processing_time = timezone.now() - job.started_at
        job.save()

        logger.info(f"Travail {job_id} terminé: {job.status}")

    except Exception as e:
        logger.error(f"Erreur traitement travail {job_id}: {e}")
        job.status = 'failed'
        job.error_message = str(e)[:500]
        job.save()

        # Retry si nécessaire
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = 'pending'
            job.save()

            # Reprogramme la tâche avec backoff
            delay = 60 * (2 ** job.retry_count)  # 2^n minutes
            process_translation_job.apply_async(
                args=[job_id],
                countdown=delay
            )
            logger.info(f"Reprogrammation travail {job_id} dans {delay}s")


@shared_task
def process_batch_translations(job_ids):
    """
    Traite plusieurs travaux de traduction en batch.
    """
    for job_id in job_ids:
        process_translation_job.delay(job_id)


@shared_task
def cleanup_old_jobs(days_old=30):
    """
    Nettoie les anciens travaux de traduction.

    Args:
        days_old: Âge maximum en jours
    """
    cutoff_date = timezone.now() - timezone.timedelta(days=days_old)

    # Archive les anciens travaux terminés
    old_jobs = TranslationJob.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['completed', 'failed']
    )

    count = old_jobs.count()
    old_jobs.delete()

    logger.info(f"Nettoyage: {count} anciens travaux supprimés")
    return count


@shared_task
def retry_failed_jobs(max_retries=3):
    """
    Relance les travaux échoués avec moins de max_retries.
    """
    failed_jobs = TranslationJob.objects.filter(
        status='failed',
        retry_count__lt=max_retries
    )

    count = failed_jobs.count()

    for job in failed_jobs:
        job.status = 'pending'
        job.retry_count += 1
        job.save()
        process_translation_job.delay(job.id)

    logger.info(f"Relance: {count} travaux échoués")
    return count


@shared_task
def update_translation_cache():
    """
    Met à jour le cache des traductions fréquentes.
    """
    from .models import TranslationMemory
    from django.core.cache import cache

    # Récupère les traductions les plus utilisées
    popular_translations = TranslationMemory.objects.order_by('-usage_count')[:100]

    for memory in popular_translations:
        cache_key = f"translation:{memory.source_language}:{memory.target_language}:{memory.source_text_hash}"
        cache.set(cache_key, memory.translated_text, timeout=86400)  # 24h

    logger.info(f"Cache mis à jour: {len(popular_translations)} entrées")
    return len(popular_translations)


def configure_periodic_tasks():
    """
    Configure les tâches périodiques Celery.
    À appeler depuis apps.py.
    """
    try:
        from celery.schedules import crontab

        return {
            'cleanup-old-jobs': {
                'task': 'translations.tasks.cleanup_old_jobs',
                'schedule': crontab(hour=3, minute=0),  # 3h00 chaque jour
                'args': (30,),
            },
            'retry-failed-jobs': {
                'task': 'translations.tasks.retry_failed_jobs',
                'schedule': crontab(hour='*/2', minute=30),  # Toutes les 2h30
            },
            'update-translation-cache': {
                'task': 'translations.tasks.update_translation_cache',
                'schedule': crontab(hour=4, minute=0),  # 4h00 chaque jour
            },
        }
    except ImportError:
        logger.warning("Celery non disponible pour les tâches périodiques")
        return {}
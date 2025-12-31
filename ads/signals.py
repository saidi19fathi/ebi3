# ~/ebi3/ads/signals.py
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Ad, AdImage, Favorite

@receiver(pre_save, sender=Ad)
def update_ad_status(sender, instance, **kwargs):
    """Met à jour les dates lors des changements de statut"""
    if instance.pk:
        old_instance = Ad.objects.get(pk=instance.pk)

        # Si l'annonce devient active et n'était pas active avant
        if instance.status == Ad.Status.ACTIVE and old_instance.status != Ad.Status.ACTIVE:
            instance.published_at = timezone.now()

        # Si l'annonce devient expirée
        if instance.status == Ad.Status.EXPIRED and old_instance.status != Ad.Status.EXPIRED:
            instance.expired_at = timezone.now()

@receiver(post_save, sender=AdImage)
def update_paid_images_count(sender, instance, created, **kwargs):
    """Met à jour le compteur d'images payantes"""
    if instance.is_paid and instance.payment_status == 'PAID':
        ad = instance.ad
        ad.paid_images_used = ad.images.filter(is_paid=True, payment_status='PAID').count()
        ad.save(update_fields=['paid_images_used'])

@receiver(post_delete, sender=AdImage)
def cleanup_image_files(sender, instance, **kwargs):
    """Nettoie les fichiers d'image supprimés"""
    # django-cleanup s'en charge automatiquement
    pass
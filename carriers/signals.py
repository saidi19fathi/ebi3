# carriers/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg
from .models import CarrierReview, Carrier

@receiver(post_save, sender=CarrierReview)
@receiver(post_delete, sender=CarrierReview)
def update_carrier_rating(sender, instance, **kwargs):
    """Met à jour la note moyenne d'un transporteur"""
    carrier = instance.carrier

    reviews = carrier.reviews.filter(is_approved=True, is_visible=True)

    if reviews.exists():
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
        total_reviews = reviews.count()

        carrier.average_rating = avg_rating or 0.00
        carrier.total_reviews = total_reviews
    else:
        carrier.average_rating = 0.00
        carrier.total_reviews = 0

    carrier.save(update_fields=['average_rating', 'total_reviews'])